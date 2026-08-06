<template>
  <!-- /logs is its own view rather than a panel on the dashboard. No router
       library: nginx already serves index.html for any path (try_files), so
       matching on the pathname is the whole routing story. -->
  <div v-if="isLogsRoute" class="logs-route">
    <TurnLog :api-url="apiUrl" />
    <AdminPanel :api-url="apiUrl" />
  </div>

  <div v-else>
    <div class="video-background-container">
      <iframe 
        src="https://player.vimeo.com/video/1134023587?autoplay=1&loop=1&muted=1&controls=0&background=1&autopause=0&responsive=1"
        frameborder="0"
        allow="autoplay; fullscreen; picture-in-picture"
        allowfullscreen
        style="width: 100vw;
          height: 100vh;
          top: 0;
          left: 0;
          position: fixed;
          transform: scale(1.5);"
        class="video-background-iframe"
        >
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
          <canvas ref="chart"></canvas>
          <div class="timestamp">
            Last update: {{ lastUpdateTime }}
          </div>
        </div>
        
        <!-- Live Stream / Timelapse Panel -->
        <div class="panel timeline-panel">
          <div class="timeline-header">
            <h2>{{ viewMode === 'livestream' ? 'Live Stream' : 'Timelapse' }}</h2>
            <div class="status-indicator-wrapper">
              <span :class="['status-indicator', isOnline ? 'online' : 'offline']"></span>
              <span class="status-text">{{ isOnline ? 'Connected' : 'Disconnected' }}</span>
            </div>
          </div>
          <div class="timelapse-container">
            <!-- Live Stream View -->
            <img 
              v-if="viewMode === 'livestream'"
              :src="streamUrl" 
              class="timelapse-image"
              alt="Live slime mould stream"
              @error="imageError = true"
              @load="imageError = false"
            >
            <!-- Timelapse View -->
            <img 
              v-else-if="viewMode === 'timelapse' && currentImage && !imageError" 
              :key="imageKey"
              :src="currentImage"
              class="timelapse-image"
              alt="Slime mould timelapse"
              @error="imageError = true"
              @load="imageError = false"
            >
            <div v-else-if="viewMode === 'timelapse'" style="height: 100%; display: flex; align-items: center; justify-content: center;">
              <p style="font-size: 1.2em; color: #ecddb1;">No images captured yet</p>
            </div>
          </div>
          <!-- Timeline Scrubber (only shown in timelapse mode) -->
          <input 
            v-if="viewMode === 'timelapse' && images.length > 0"
            type="range" 
            v-model.number="timelinePosition" 
            :max="images.length - 1" 
            min="0" 
            class="timeline-scrubber"
            @input="onTimelineScrub"
          >
          <div class="timeline-footer">
            <div class="timestamp">
              <span v-if="viewMode === 'livestream'">
                Live USB camera feed<br>
                <small style="color: #666;">Capturing {{ imagesPerDay }} images/day ({{ estimatedStoragePerDay }})</small>
              </span>
              <span v-else>
                {{ images.length }} of {{ totalImagesOnServer }} images<br>
                <small v-if="currentImageTime" style="color: #666;">{{ currentImageTime }}</small>
              </span>
            </div>
            <button
              v-if="cameraAvailable !== false"
              @click="toggleViewMode"
              class="control-button capture-button"
            >
              {{ viewMode === 'livestream' ? 'View Timelapse' : 'View Livestream' }}
            </button>
            <small v-else style="color: #666;">No camera connected</small>
          </div>
        </div>
      </div>
      
      <!-- Environmental Monitoring Panel -->
      <div class="panel">
        <h2>Environmental Conditions</h2>
        <div class="environment-display">
          <div class="env-metric">
            <div class="value">{{ temperature !== null ? temperature.toFixed(1) : '--' }}°C</div>
            <div class="sub-value">{{ temperatureF !== null ? temperatureF.toFixed(1) : '--' }}°F</div>
            <div class="label">Temperature</div>
          </div>
          <div class="env-metric">
            <div class="value">{{ humidity !== null ? humidity.toFixed(1) : '--' }}%</div>
            <div class="label">Humidity</div>
          </div>
        </div>
        <div class="timestamp">
          {{ environmentUpdateTime || 'No data yet' }}
        </div>
      </div>

    </div>

    <AdminPanel :api-url="apiUrl" />
  </div>
</template>

<script>
import { markRaw } from 'vue'
import { io } from 'socket.io-client'
import axios from 'axios'
import { Chart, registerables } from 'chart.js'
import AdminPanel from './components/AdminPanel.vue'
import TurnLog from './components/TurnLog.vue'

Chart.register(...registerables)

export default {
  name: 'App',
  components: { AdminPanel, TurnLog },
  data() {
    return {
      // App version - increment on each deployment
      appVersion: '1.0.13',
      
      // API configuration
      apiUrl: window.location.origin,
      isLogsRoute: window.location.pathname.replace(/\/+$/, '') === '/logs',
      socket: null,
      
      // Electrical readings
      currentReading: 0,
      readingsHistory: [],
      chart: null,
      
      // Environmental data
      temperature: null,
      temperatureF: null,
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
      imageKey: 0, // Used to force img element re-render
      capturingImage: false, // Prevent concurrent captures
      viewMode: 'livestream', // 'livestream' or 'timelapse'
      maxImages: 100, // Max images held in memory at once
      totalImagesOnServer: 0, // Full archive size reported by /api/images
      cameraAvailable: null, // null until /api/status reports; false hides livestream
      viewModeChosenByUser: false, // Don't override an explicit toggle
      
      // System status
      isOnline: false,
      exposureLightOn: false,
      lastUpdateTime: 'Never',
      
      // Configuration from server
      imageCaptureInterval: 60000,  // Default 1 minute in ms (for livestream still captures)
      maxExposureDuration: 30,
      
      // Intervals
      imageInterval: null,
      fallbackInterval: null
    }
  },
  
  computed: {
    streamUrl() {
      return `${this.apiUrl}/api/stream`
    },
    imagesPerDay() {
      // Calculate images per day: 24 hours * 60 minutes = 1440 images/day
      const minutesPerDay = 24 * 60
      const intervalMinutes = this.imageCaptureInterval / 60000
      return Math.floor(minutesPerDay / intervalMinutes)
    },
    currentImageTime() {
      const image = this.images[this.timelinePosition]
      if (!image) return null
      return new Date(image.timestamp).toLocaleString()
    },
    estimatedStoragePerDay() {
      // Estimate storage: assume ~500KB per image (1920x1080 JPEG)
      const avgImageSizeKB = 500
      const totalMB = (this.imagesPerDay * avgImageSizeKB) / 1024
      const totalGB = totalMB / 1024
      if (totalGB >= 1) {
        return `${totalGB.toFixed(2)} GB/day`
      }
      return `${totalMB.toFixed(1)} MB/day`
    }
  },
  
  async mounted() {
    console.log(`🦠 sLLM Frontend v${this.appVersion}`)

    // /logs renders TurnLog instead of the dashboard, so none of the dashboard
    // machinery should start: there is no canvas to attach a chart to, and the
    // socket and image archive would be work done for a view nobody is looking
    // at. TurnLog polls /api/turns on its own.
    if (this.isLogsRoute) {
      console.log('📜 Log view')
      return
    }

    this.initializeChart()
    this.connectSocket()
    this.loadImages()
    // Resolve camera availability before starting capture, so we don't poll a
    // camera that isn't there (and can open straight into timelapse instead)
    await this.checkStatus()
    this.startImageCapture()
  },
  
  beforeUnmount() {
    // Clean up
    if (this.socket) {
      this.socket.disconnect()
    }
    if (this.imageInterval) clearInterval(this.imageInterval)
    if (this.fallbackInterval) clearInterval(this.fallbackInterval)
    if (this.chart) this.chart.destroy()
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
        this.temperatureF = data.temperature_f
        this.humidity = data.humidity
        this.hasEnvironmentalData = true
        const date = new Date(data.datetime)
        this.environmentUpdateTime = `Last update: ${date.getDate().toString().padStart(2, '0')}.${(date.getMonth() + 1).toString().padStart(2, '0')}.${date.getFullYear()} ${date.toLocaleTimeString()}`
      })
      
      this.socket.on('status_update', (data) => {
        this.exposureLightOn = data.exposure_light
      })
      
      this.socket.on('light_changed', (data) => {
        this.exposureLightOn = data.exposure_light
      })
      
      // Listen for image capture events
      this.socket.on('image_captured', (data) => {
        console.log('📸 Image captured event received:', data)
        // Update display with the new image
        if (data.filename) {
          // Use both timestamp and random number to ensure unique URL
          const imageUrl = `${this.apiUrl}/api/images/${data.filename}?t=${Date.now()}&r=${Math.random()}`
          this.addImageToTimeline(imageUrl, data.filename)
        }
      })
      
      // Fallback polling for initial data
      this.fallbackInterval = setInterval(() => {
        this.checkStatus()
      }, 5000)
    },
    
    initializeChart() {
      this.$nextTick(() => {
        const canvas = this.$refs.chart
        if (!canvas) return
        
        const ctx = canvas.getContext('2d')
        if (!ctx) return
        
        if (this.chart) this.chart.destroy()
        
        const chart = new Chart(ctx, {
          type: 'line',
          data: {
            labels: [],
            datasets: [{
              label: 'Voltage (mV)',
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
              },
              tooltip: {
                enabled: false
              },
              decimation: {
                enabled: false
              }
            },
            interaction: {
              intersect: false,
              mode: 'index'
            },
            scales: {
              x: {
                display: true,
                grid: {
                  color: 'rgba(255, 255, 255, 0.1)'
                },
                ticks: {
                  color: '#aaa',
                  maxTicksLimit: 6
                },
                title: {
                  color: '#ddd'
                }
              },
              y: {
                display: true,
                min: -10,
                max: 10,
                grid: {
                  color: 'rgba(255, 255, 255, 0.1)'
                },
                ticks: {
                  color: '#aaa'
                },
                title: {
                  color: '#ddd'
                }
              }
            }
          }
        })
        this.chart = markRaw(chart)
      })
    },
    
    async loadImages() {
      // Populate the timeline with images already on disk, so the timelapse
      // isn't limited to whatever this browser session happens to capture
      try {
        const response = await axios.get(`${this.apiUrl}/api/images`, {
          params: { page: 1, per_page: this.maxImages, order: 'desc' }
        })

        // Server returns newest first; reverse so the timeline runs oldest → newest
        this.images = response.data.images.reverse().map(image => ({
          url: `${this.apiUrl}${image.url}`,
          filename: image.filename,
          timestamp: image.datetime
        }))
        this.totalImagesOnServer = response.data.total

        if (this.images.length > 0) {
          // Park the scrubber on the newest frame and show it, so timelapse mode
          // has something to display without waiting for a fresh capture
          this.timelinePosition = this.images.length - 1
          this.currentImage = this.images[this.timelinePosition].url
          this.imageError = false
        }
        console.log(`🎞️  Loaded ${this.images.length} of ${this.totalImagesOnServer} archived images`)
      } catch (error) {
        console.warn('Could not load image archive:', error.message)
      }
    },

    startImageCapture() {
      // The page is a VIEWER. It must never drive a capture on its own.
      //
      // It used to POST /api/capture-image on page load and then on its own
      // timer, so the real capture rate was one stream per open browser tab on
      // top of the backend timelapse. Every capture fires the red imaging flash
      // over the organism, which means uncontrolled optical stimulus timed by
      // human web traffic -- and the model is never told a flash happened. The
      // backend timelapse is the single source of captures; this listens for
      // the image_captured socket event and renders what arrives.
      //
      // The Capture Image button still works: that is a deliberate human
      // action, not a side effect of loading a web page.
      this.fetchConfig()

      if (this.cameraAvailable === false) {
        console.log('📷 No camera detected - showing archive only')
        return
      }
      console.log('👁️  Viewer mode: frames arrive from the backend timelapse')
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
        this.imageCaptureInterval = 60 * 1000 // Default 1 minute for livestream still captures
        this.maxExposureDuration = 30
      }
    },
    
    updateChart(reading) {
      if (!this.chart || !this.chart.data || !this.chart.data.datasets || !this.chart.data.datasets[0]) return
      
      const time = new Date(reading.datetime).toLocaleTimeString()
      this.chart.data.labels.push(time)
      this.chart.data.datasets[0].data.push(reading.value)
      
      // Keep only last 50 points
      if (this.chart.data.labels.length > 50) {
        this.chart.data.labels.shift()
        this.chart.data.datasets[0].data.shift()
      }
      
      try {
        this.chart.update('none')
      } catch (error) {
        console.log('Chart update error:', error)
      }
    },
    
    async captureImage(isManual = false) {
      // Prevent concurrent captures
      if (this.capturingImage) {
        console.log('⏸️  Capture already in progress, skipping...')
        return
      }
      
      if (isManual) {
        console.log('🦠 Capture Image button clicked (MANUAL)')
      } else {
        console.log('📸 Automatic image capture')
      }
      console.log('API URL:', this.apiUrl)
      
      this.capturingImage = true
      
      try {
        // Add cache-busting timestamp to ensure we get a fresh response
        const timestamp = Date.now()
        console.log('Sending POST request to /api/capture-image...')
        const response = await axios.post(`${this.apiUrl}/api/capture-image?t=${timestamp}`, {}, {
          headers: {
            'Cache-Control': 'no-cache'
          }
        })
        
        console.log('Response received:', response.data)
        
        if (!response.data || !response.data.success) {
          throw new Error(response.data?.error || 'Capture failed')
        }
        
        // Use the filename from the response to construct the image URL
        // Add both timestamp and random number to ensure completely unique URL
        const imageUrl = `${this.apiUrl}${response.data.url}?t=${Date.now()}&r=${Math.random()}`
        console.log('Image URL:', imageUrl)
        
        // Add image to timeline immediately
        this.addImageToTimeline(imageUrl, response.data.filename)
        
      } catch (error) {
        console.error('❌ Error capturing image:', error)
        console.error('Error details:', {
          message: error.message,
          response: error.response?.data,
          status: error.response?.status,
          statusText: error.response?.statusText
        })
        this.imageError = true
        this.currentImage = null
      } finally {
        this.capturingImage = false
      }
    },
    
    addImageToTimeline(imageUrl, filename) {
      // A manual capture arrives twice: once as the POST response, once as the
      // image_captured socket event for the same file. Without this the same
      // frame is appended twice, which double-counts the archive and evicts a
      // real frame off the front of the 100-image window.
      if (filename && this.images.some(image => image.filename === filename)) {
        return
      }

      // Revoke old blob URLs if they exist (cleanup)
      if (this.currentImage && this.currentImage.startsWith('blob:')) {
        URL.revokeObjectURL(this.currentImage)
      }
      
      // Ensure URL has unique cache-busting parameters
      const uniqueUrl = imageUrl.includes('?') 
        ? `${imageUrl}&_=${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
        : `${imageUrl}?_=${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
      
      const imageData = {
        url: uniqueUrl,
        filename: filename,
        timestamp: new Date().toISOString()
      }
      
      this.images.push(imageData)
      this.totalImagesOnServer++
      // Update timeline position
      this.timelinePosition = this.images.length - 1
      
      // Force complete re-render by clearing image first, then setting it
      this.currentImage = null
      this.imageError = false
      this.imageKey++ // Increment key to force Vue to create new img element
      
      // Use nextTick to ensure DOM updates after clearing
      this.$nextTick(() => {
        // Now set the new image - Vue will create a fresh img element
        this.currentImage = uniqueUrl
        console.log('✅ Image displayed. Total images:', this.images.length, 'Position:', this.timelinePosition, 'Key:', this.imageKey, 'Filename:', filename, 'URL:', uniqueUrl.substring(0, 80) + '...')
      })
      
      // Keep only the most recent images to prevent memory issues
      if (this.images.length > this.maxImages) {
        const oldImage = this.images.shift()
        // Revoke blob URLs if they exist
        if (oldImage.url && oldImage.url.startsWith('blob:')) {
          URL.revokeObjectURL(oldImage.url)
        }
        this.timelinePosition = this.images.length - 1
        console.log(`Removed oldest image (keeping max ${this.maxImages})`)
      }
    },
    
    onTimelineScrub() {
      if (this.images.length > 0 && this.timelinePosition < this.images.length) {
        // Swap the src without touching imageKey: recreating the <img> element
        // would blank it out and collapse the container until the new frame
        // loads. Scrubbed frames always have distinct filenames, so the
        // cache-busting re-render that live captures need doesn't apply here.
        this.currentImage = this.images[this.timelinePosition].url
        this.imageError = false
      }
    },
    
    toggleViewMode() {
      this.viewModeChosenByUser = true
      if (this.viewMode === 'livestream') {
        // Switch to timelapse mode
        this.viewMode = 'timelapse'
        // Show the current image from timeline if available
        if (this.images.length > 0) {
          this.timelinePosition = this.images.length - 1 // Go to latest image
          this.currentImage = this.images[this.timelinePosition].url
          this.imageError = false
        }
      } else {
        // Switch back to livestream mode
        this.viewMode = 'livestream'
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

        // With no camera the livestream is a dead image, so open into timelapse
        this.cameraAvailable = status.sensors?.camera === true
        if (!this.cameraAvailable && !this.viewModeChosenByUser) {
          this.viewMode = 'timelapse'
        }

        // Update environmental data if available
        if (status.environment) {
          this.temperature = status.environment.temperature
          this.temperatureF = status.environment.temperature_f
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

