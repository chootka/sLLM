<template>
  <div>
    <div class="video-background">
      <iframe 
        src="https://player.vimeo.com/video/1134023587?autoplay=1&loop=1&muted=1&controls=0&background=1&autopause=0&responsive=1" 
        frameborder="0" 
        allow="autoplay; fullscreen; picture-in-picture" 
        allowfullscreen>
      </iframe>
    </div>
    <div class="container">
      <h1>🦠 Slime Mould Monitor</h1>
      
      <div class="grid">
        <!-- Electrical Readings Panel -->
        <div class="panel">
          <h2>Electrical Activity</h2>
          <div class="readings-display">
            {{ currentReading.toFixed(1) }} mV
          </div>
          <canvas ref="readingsChart"></canvas>
          <div class="timestamp">
            Last update: {{ lastUpdateTime }}
          </div>
        </div>
        
        <!-- Timelapse Viewer Panel -->
        <div class="panel">
          <h2>Visual Timeline</h2>
          <div class="timelapse-container">
            <img 
              v-if="currentImage && !imageError" 
              :src="currentImage" 
              class="timelapse-image"
              alt="Slime mould"
              @error="imageError = true"
            >
            <div v-else style="height: 300px; display: flex; align-items: center; justify-content: center;">
              <p style="font-size: 1.2em; color: #ecddb1;">Slimes are offline!</p>
            </div>
          </div>
          <input 
            type="range" 
            v-model.number="timelinePosition" 
            :max="images.length - 1" 
            min="0" 
            class="timeline-scrubber"
            @input="onTimelineScrub"
            v-if="images.length > 0"
          >
          <div class="timestamp">
            {{ images.length }} images captured
          </div>
        </div>
      </div>
      
      <!-- Environmental Monitoring Panel -->
      <div class="panel" v-if="hasEnvironmentalData">
        <h2>Environmental Conditions</h2>
        <div class="environment-display">
          <div class="env-metric">
            <div class="value">{{ temperature ? temperature.toFixed(1) : '--' }}°C</div>
            <div class="label">Temperature</div>
          </div>
          <div class="env-metric">
            <div class="value">{{ humidity ? humidity.toFixed(1) : '--' }}%</div>
            <div class="label">Humidity</div>
          </div>
        </div>
        <div class="timestamp">
          {{ environmentUpdateTime }}
        </div>
      </div>
      
      <!-- Control Panel -->
      <div class="panel" style="margin-top: 30px;">
        <h2>Controls</h2>
        <div style="display: flex; align-items: center; gap: 20px;">
          <button @click="captureImage" class="control-button">
            Capture Image
          </button>
          <button 
            @click="toggleLight" 
            :class="['control-button', exposureLightOn ? 'danger' : '']"
          >
            {{ exposureLightOn ? 'Turn Off' : 'Turn On' }} Exposure Light
          </button>
          <div>
            <span :class="['status-indicator', isOnline ? 'online' : 'offline']"></span>
            {{ isOnline ? 'Connected' : 'Disconnected' }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { io } from 'socket.io-client'
import axios from 'axios'
import { Chart, registerables } from 'chart.js'

Chart.register(...registerables)

export default {
  name: 'App',
  data() {
    return {
      // API configuration
      apiUrl: window.location.origin,
      socket: null,
      
      // Electrical readings
      currentReading: 0,
      readingsHistory: [],
      chart: null,
      
      // Environmental data
      temperature: null,
      humidity: null,
      temperatureHistory: [],
      humidityHistory: [],
      hasEnvironmentalData: false,
      environmentUpdateTime: 'No data',
      
      // Timelapse
      images: [],
      timelinePosition: 0,
      currentImage: null,
      imageError: false,
      
      // System status
      isOnline: false,
      exposureLightOn: false,
      lastUpdateTime: 'Never',
      
      // Configuration from server
      imageCaptureInterval: 300000,  // Default 5 minutes in ms
      maxExposureDuration: 30,
      
      // Intervals
      imageInterval: null,
      fallbackInterval: null,
      chartUpdateTimeout: null,
      chartReady: false,
      chartUpdating: false,
      chartErrorCount: 0
    }
  },
  
  mounted() {
    this.initializeChart()
    this.connectSocket()
    this.startImageCapture()
  },
  
  beforeUnmount() {
    // Clean up
    if (this.socket) {
      this.socket.disconnect()
    }
    if (this.imageInterval) clearInterval(this.imageInterval)
    if (this.fallbackInterval) clearInterval(this.fallbackInterval)
    if (this.chartUpdateTimeout) clearTimeout(this.chartUpdateTimeout)
    if (this.chart) {
      this.chart.destroy()
    }
  },
  
  methods: {
    connectSocket() {
      // Connect to Socket.IO server
      this.socket = io(this.apiUrl)
      
      // Connection events
      this.socket.on('connect', () => {
        console.log('Connected to Socket.IO server')
        this.isOnline = true
      })
      
      this.socket.on('disconnect', () => {
        console.log('Disconnected from Socket.IO server')
        this.isOnline = false
      })
      
      // Real-time data events
      this.socket.on('reading_update', (data) => {
        this.currentReading = data.value
        const date = new Date(data.datetime)
        this.lastUpdateTime = `${date.getDate().toString().padStart(2, '0')}.${(date.getMonth() + 1).toString().padStart(2, '0')}.${date.getFullYear()} ${date.toLocaleTimeString()}`
        this.updateChart(data)
      })
      
      this.socket.on('environment_update', (data) => {
        this.temperature = data.temperature
        this.humidity = data.humidity
        this.hasEnvironmentalData = true
        const date = new Date(data.datetime)
        this.environmentUpdateTime = `Last Update: ${date.getDate().toString().padStart(2, '0')}.${(date.getMonth() + 1).toString().padStart(2, '0')}.${date.getFullYear()} ${date.toLocaleTimeString()}`
        this.updateEnvironmentChart(data)
      })
      
      this.socket.on('status_update', (data) => {
        this.exposureLightOn = data.exposure_light
      })
      
      this.socket.on('light_changed', (data) => {
        this.exposureLightOn = data.exposure_light
      })
      
      // Fallback polling for initial data
      this.fallbackInterval = setInterval(() => {
        this.checkStatus()
      }, 5000)
    },
    
    initializeChart() {
      // Wait for next tick to ensure canvas is rendered
      this.$nextTick(() => {
        const canvas = this.$refs.readingsChart
        if (!canvas) {
          console.error('Chart canvas not found')
          return
        }
        
        const ctx = canvas.getContext('2d')
        if (!ctx) {
          console.error('Could not get 2d context')
          return
        }
        
        // Destroy existing chart if any
        if (this.chart) {
          this.chart.destroy()
        }
        
        this.chart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'Voltage (in mV)',
              data: [],
              borderColor: '#a0d468',
              backgroundColor: 'rgba(160, 212, 104, 0.1)',
              borderWidth: 2,
              tension: 0.4,
              pointRadius: 0,
              yAxisID: 'y'
            },
            {
              label: 'Temperature (°C)',
              data: [],
              borderColor: '#ff6b6b',
              backgroundColor: 'rgba(255, 107, 107, 0.1)',
              borderWidth: 2,
              tension: 0.4,
              pointRadius: 0,
              yAxisID: 'y1'
            },
            {
              label: 'Humidity (%)',
              data: [],
              borderColor: '#4ecdc4',
              backgroundColor: 'rgba(78, 205, 196, 0.1)',
              borderWidth: 2,
              tension: 0.4,
              pointRadius: 0,
              yAxisID: 'y1'
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          plugins: {
            legend: {
              display: true,
              position: 'top',
              labels: {
                color: '#ecddb1'
              }
            },
            tooltip: {
              enabled: true
            }
          },
          scales: {
            x: {
              display: true,
              grid: {
                color: 'rgba(255, 255, 255, 0.1)'
              },
              ticks: {
                color: '#666',
                maxTicksLimit: 6
              }
            },
            y: {
              type: 'linear',
              display: true,
              position: 'left',
              title: {
                display: true,
                text: 'Voltage (in mV)',
                color: '#a0d468'
              },
              grid: {
                color: 'rgba(255, 255, 255, 0.05)'
              },
              ticks: {
                color: '#a0d468'
              }
            },
            y1: {
              type: 'linear',
              display: true,
              position: 'right',
              title: {
                display: true,
                text: 'Temp (°C) / Humidity (%)',
                color: '#ecddb1'
              },
              grid: {
                drawOnChartArea: false
              },
              ticks: {
                color: '#ecddb1'
              }
            }
          }
        }
        })
        // Mark chart as ready immediately after creation
        this.chartReady = true
      })
    },
    
    startImageCapture() {
      // Get capture interval from API config
      this.fetchConfig().then(() => {
        // Capture image at configured interval
        this.imageInterval = setInterval(() => {
          this.captureImage()
        }, this.imageCaptureInterval)
        
        // Initial capture
        this.captureImage()
      })
    },
    
    async fetchConfig() {
      try {
        const response = await axios.get(`${this.apiUrl}/api/config`)
        const config = response.data
        
        // Update local settings from server config
        this.imageCaptureInterval = config.image_capture_interval * 1000 // Convert to ms
        this.maxExposureDuration = config.max_exposure_duration
        
      } catch (error) {
        console.warn('Could not fetch config, using defaults')
        this.imageCaptureInterval = 5 * 60 * 1000 // Default 5 minutes
        this.maxExposureDuration = 30
      }
    },
    
    updateChart(reading) {
      if (!this.chart || !this.chart.data) return
      
      const time = new Date(reading.datetime).toLocaleTimeString()
      this.chart.data.labels.push(time)
      this.chart.data.datasets[0].data.push(reading.value)
      
      // Keep datasets in sync
      if (this.chart.data.datasets[1]) {
        this.chart.data.datasets[1].data.push(null)
      }
      if (this.chart.data.datasets[2]) {
        this.chart.data.datasets[2].data.push(null)
      }
      
      // Keep only last 50 points
      if (this.chart.data.labels.length > 50) {
        this.chart.data.labels.shift()
        this.chart.data.datasets[0].data.shift()
        if (this.chart.data.datasets[1]) this.chart.data.datasets[1].data.shift()
        if (this.chart.data.datasets[2]) this.chart.data.datasets[2].data.shift()
      }
      
      this.debouncedChartUpdate()
    },
    
    updateEnvironmentChart(envData) {
      if (!this.chart || !this.chart.data) return
      
      const time = new Date(envData.datetime).toLocaleTimeString()
      const lastIndex = this.chart.data.labels.length - 1
      
      if (lastIndex >= 0 && this.chart.data.labels[lastIndex] === time) {
        // Update existing point
        if (this.chart.data.datasets[1]) {
          this.chart.data.datasets[1].data[lastIndex] = envData.temperature
        }
        if (this.chart.data.datasets[2]) {
          this.chart.data.datasets[2].data[lastIndex] = envData.humidity
        }
      } else {
        // Add new point
        this.chart.data.labels.push(time)
        if (this.chart.data.datasets[0]) {
          this.chart.data.datasets[0].data.push(null)
        }
        if (this.chart.data.datasets[1]) {
          this.chart.data.datasets[1].data.push(envData.temperature)
        }
        if (this.chart.data.datasets[2]) {
          this.chart.data.datasets[2].data.push(envData.humidity)
        }
      }
      
      // Keep only last 50 points
      if (this.chart.data.labels.length > 50) {
        this.chart.data.labels.shift()
        if (this.chart.data.datasets[0]) this.chart.data.datasets[0].data.shift()
        if (this.chart.data.datasets[1]) this.chart.data.datasets[1].data.shift()
        if (this.chart.data.datasets[2]) this.chart.data.datasets[2].data.shift()
      }
      
      this.debouncedChartUpdate()
    },
    
    debouncedChartUpdate() {
      if (!this.chart || this.chartUpdating) return
      
      // Clear any pending update
      if (this.chartUpdateTimeout) {
        clearTimeout(this.chartUpdateTimeout)
      }
      
      // Schedule update after a delay to batch multiple updates
      this.chartUpdateTimeout = setTimeout(() => {
        if (this.chart && !this.chartUpdating) {
          this.chartUpdating = true
          // Use requestAnimationFrame to ensure update happens in next frame
          requestAnimationFrame(() => {
            if (this.chart) {
              try {
                this.chart.update('none')
              } catch (e) {
                console.error('Chart update error:', e)
              } finally {
                this.chartUpdating = false
              }
            }
          })
        }
      }, 150)
    },
    
    async captureImage() {
      try {
        const response = await axios.post(`${this.apiUrl}/api/capture-image`, {}, {
          responseType: 'blob'
        })
        
        const imageUrl = URL.createObjectURL(response.data)
        const imageData = {
          url: imageUrl,
          timestamp: new Date().toISOString()
        }
        
        this.images.push(imageData)
        this.currentImage = imageUrl
        this.imageError = false
        this.timelinePosition = this.images.length - 1
        
        // Keep only last 100 images to prevent memory issues
        if (this.images.length > 100) {
          URL.revokeObjectURL(this.images[0].url)
          this.images.shift()
        }
      } catch (error) {
        console.error('Error capturing image:', error)
        this.imageError = true
        this.currentImage = null
      }
    },
    
    onTimelineScrub() {
      if (this.images.length > 0 && this.timelinePosition < this.images.length) {
        this.currentImage = this.images[this.timelinePosition].url
        this.imageError = false
      }
    },
    
    async toggleLight() {
      try {
        const response = await axios.post(`${this.apiUrl}/api/trigger-light`, {
          state: 'toggle'
        })
        
        this.exposureLightOn = response.data.light_state === 'on'
      } catch (error) {
        console.error('Error toggling light:', error)
      }
    },
    
    async checkStatus() {
      try {
        const response = await axios.get(`${this.apiUrl}/api/status`)
        const status = response.data
        
        this.isOnline = true
        this.exposureLightOn = status.exposure_light === 'on'
        
        // Update environmental data if available
        if (status.environment) {
          this.temperature = status.environment.temperature
          this.humidity = status.environment.humidity
          this.hasEnvironmentalData = true
          const date = new Date(status.environment.datetime)
          this.environmentUpdateTime = `Last update: ${date.getDate().toString().padStart(2, '0')}.${(date.getMonth() + 1).toString().padStart(2, '0')}.${date.getFullYear()} ${date.toLocaleTimeString()}`
        }
      } catch (error) {
        this.isOnline = false
      }
    }
  }
}
</script>

