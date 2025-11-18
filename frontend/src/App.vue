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
            {{ currentReading.toFixed(4) }} V
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
      <div class="panel">
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
      fallbackInterval: null
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
        this.lastUpdateTime = new Date(data.datetime).toLocaleTimeString()
        this.updateChart(data)
      })
      
      this.socket.on('environment_update', (data) => {
        this.temperature = data.temperature
        this.humidity = data.humidity
        this.hasEnvironmentalData = true
        this.environmentUpdateTime = `Updated: ${new Date(data.datetime).toLocaleTimeString()}`
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
      const ctx = this.$refs.readingsChart.getContext('2d')
      this.chart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: [],
          datasets: [{
            label: 'Voltage (V)',
            data: [],
            borderColor: '#a0d468',
            backgroundColor: 'rgba(160, 212, 104, 0.1)',
            borderWidth: 2,
            tension: 0.4,
            pointRadius: 0
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: false
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
              display: true,
              grid: {
                color: 'rgba(255, 255, 255, 0.1)'
              },
              ticks: {
                color: '#666'
              }
            }
          }
        }
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
      const time = new Date(reading.datetime).toLocaleTimeString()
      
      this.chart.data.labels.push(time)
      this.chart.data.datasets[0].data.push(reading.value)
      
      // Keep only last 50 points
      if (this.chart.data.labels.length > 50) {
        this.chart.data.labels.shift()
        this.chart.data.datasets[0].data.shift()
      }
      
      this.chart.update('none') // No animation for smooth updates
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
          this.environmentUpdateTime = `Updated: ${new Date(status.environment.datetime).toLocaleTimeString()}`
        }
      } catch (error) {
        this.isOnline = false
      }
    }
  }
}
</script>

