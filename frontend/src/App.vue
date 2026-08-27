<template>
  <!-- /logs and /viz are their own views rather than panels on the dashboard.
       No router library: nginx already serves index.html for any path
       (try_files), so matching on the pathname is the whole routing story. -->
  <div v-if="isLogsRoute" class="logs-route">
    <TurnLog :api-url="apiUrl" />
    <PhaseLock :api-url="apiUrl" />
    <AdminPanel :api-url="apiUrl" />
  </div>

  <!-- /viz is deliberately not wired into the dashboard yet. The signal it
       draws is synthetic and the electrode sites are inferred, so it earns a
       place next to the real readings only once both are measured. -->
  <SlimeViz v-else-if="isVizRoute" :api-url="apiUrl" />

  <div v-else>
    <div class="container">
      <div class="masthead">
        <div class="masthead-left">
          <h1>Slime Mould Monitor</h1>
          <span class="dev-note">/// UNDER DEVELOPMENT ///</span>
        </div>
        <!-- Chamber conditions live here rather than in a panel of their own:
             two numbers that move on the scale of hours did not need a third
             of the page, but they do need to be on screen at all times. -->
        <div class="env-readout">
          <div :class="temperatureState">
            <span class="env-figure">{{ temperature !== null ? temperature.toFixed(1) : '--' }}&deg;C</span>
            <span class="env-alt">{{ temperatureF !== null ? temperatureF.toFixed(1) : '--' }}&deg;F</span>
            <span class="env-label">temp</span>
          </div>
          <div :class="humidityState">
            <span class="env-figure">{{ humidity !== null ? humidity.toFixed(1) : '--' }}%</span>
            <span class="env-label">rh</span>
          </div>
          <!-- Inline SVG rather than an emoji: the emoji renders as a colour
               glyph the palette cannot touch, and it is a different picture on
               every platform. Shows the theme it switches TO. -->
          <button
            class="theme-toggle"
            @click="toggleTheme"
            :title="theme === 'dark' ? 'Light mode' : 'Dark mode'"
            :aria-label="theme === 'dark' ? 'Light mode' : 'Dark mode'"
          >
            <svg v-if="theme === 'dark'" viewBox="0 0 24 24" width="15" height="15"
                 fill="none" stroke="currentColor" stroke-width="1.6"
                 stroke-linecap="round">
              <circle cx="12" cy="12" r="4.2" />
              <path d="M12 2.4v2.6M12 19v2.6M2.4 12h2.6M19 12h2.6
                       M5.2 5.2l1.9 1.9M16.9 16.9l1.9 1.9
                       M18.8 5.2l-1.9 1.9M7.1 16.9l-1.9 1.9" />
            </svg>
            <svg v-else viewBox="0 0 24 24" width="15" height="15"
                 fill="none" stroke="currentColor" stroke-width="1.6"
                 stroke-linejoin="round">
              <path d="M20.5 14.6A8.6 8.6 0 0 1 9.4 3.5a8.6 8.6 0 1 0 11.1 11.1z" />
            </svg>
          </button>
        </div>
      </div>

      <div class="grid">
        <!-- Model log, embedded. The same component still serves /logs as a
             full page; `embedded` drops its page furniture (own h1, dashboard
             link, follow toggle) so it reads as a panel here. -->
        <div class="panel log-panel">
          <div class="log-panel-head">
            <h2>Model Log</h2>
            <a href="/logs" class="logs-link" style="position: static;">full log &rarr;</a>
          </div>
          <TurnLog :api-url="apiUrl" embedded />
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
              key="livestream"
              :src="streamUrl"
              class="timelapse-image"
              alt="Live slime mould stream"
              @error="imageError = true"
              @load="imageError = false"
            >
            <!-- Timelapse View -->
            <!-- Keyed on the frame URL, not imageKey. Both branches here are
                 <img>, so Vue patched one long-lived element -- and the
                 livestream branch is an MJPEG multipart response, which keeps
                 painting into the element it owns even after src is reassigned.
                 Playback moved the src and the picture never followed. A key
                 that changes per frame forces a fresh element each time.
                 Frames are preloaded so the swap is a cache hit, and
                 .timelapse-container reserves a 16:9 box so nothing collapses
                 while a new element mounts. -->
            <img
              v-else-if="viewMode === 'timelapse' && currentImage && !imageError"
              :key="currentImage"
              :src="currentImage"
              class="timelapse-image"
              alt="Slime mould timelapse"
              @error="imageError = true"
              @load="imageError = false"
            >
            <div v-else-if="viewMode === 'timelapse'" class="timelapse-empty">
              No images captured yet
            </div>
            <!-- Burned over the frame rather than beside it: the point is what
                 the chamber was doing at that moment, so it has to travel with
                 the picture. Blank rather than nearest-value where the record
                 does not cover the frame -- the camera has been running since
                 November and the sensor only since August. -->
            <div
              v-if="viewMode === 'timelapse' && currentImage"
              class="frame-overlay"
            >
              <span class="frame-time">{{ currentImageTime || '' }}</span>
              <span v-if="frameEnvironment" class="frame-env">
                {{ frameEnvironment.temperature_c.toFixed(1) }}&deg;C
                <span class="frame-alt">{{ frameEnvironment.temperature_f.toFixed(1) }}&deg;F</span>
                &middot; {{ frameEnvironment.humidity_pct.toFixed(1) }}% RH
              </span>
              <span v-else class="frame-env frame-env-missing">no chamber data</span>
            </div>
          </div>
          <!-- Timeline Scrubber + playback (only shown in timelapse mode) -->
          <div
            v-if="viewMode === 'timelapse' && images.length > 0"
            class="timeline-controls"
          >
            <button
              @click="togglePlayback"
              class="play-button"
              :disabled="images.length < 2"
              :title="playButtonLabel"
              :aria-label="playButtonLabel"
            >
              {{ isPreloading ? '■' : (isPlaying ? '❚❚' : '▶') }}
            </button>
            <input
              type="range"
              v-model.number="timelinePosition"
              :max="images.length - 1"
              min="0"
              class="timeline-scrubber"
              @input="onTimelineScrub"
            >
          </div>
          <div v-if="isPreloading || isPlaying" class="preload-status">
            <span v-if="isPreloading">Loading frames… {{ preloadLoaded }} / {{ preloadTotal }}</span>
            <span v-else>Frame {{ timelinePosition + 1 }} / {{ images.length }}</span>
          </div>
          <div class="timeline-footer">
            <div class="timestamp">
              <span v-if="viewMode === 'livestream'">
                Live USB camera feed<br>
                <small class="timestamp">Capturing {{ imagesPerDay }} images/day ({{ estimatedStoragePerDay }})</small>
              </span>
              <span v-else>
                {{ images.length }} of {{ totalImagesOnServer }} images<br>
                <small v-if="currentImageTime" class="timestamp">{{ currentImageTime }}</small>
              </span>
            </div>
            <button
              v-if="cameraAvailable !== false"
              @click="toggleViewMode"
              class="control-button capture-button"
            >
              {{ viewMode === 'livestream' ? 'View Timelapse' : 'View Livestream' }}
            </button>
            <small v-else class="timestamp">No camera connected</small>
          </div>
        </div>
      </div>
      
      <!-- Electrical Readings Panel -->
      <div class="panel chart-panel panel-wide">
        <div class="chart-head">
          <h2>{{ signalMode ? 'Slime Signal' : 'Electrical Activity' }}</h2>
          <!-- Raw is the voltage as recorded, drift and condensation included.
               Signal is the gated 90-200 s trace: flat at zero means no
               organism, and the ghost behind it is the high-passed raw, so a
               flat line is distinguishable from a dead feed. -->
          <span v-if="signalMode && chartView === 'live'" class="chart-note">
            {{ signalCadence }}
          </span>
          <div class="mode-toggle">
            <button
              class="control-button"
              :class="{ active: !signalMode }"
              @click="setSignalMode(false)"
            >raw</button>
            <button
              class="control-button"
              :class="{ active: signalMode }"
              @click="setSignalMode(true)"
            >signal</button>
          </div>
        </div>
        <!-- Three differential channels against the reference electrode, not
             one. The panel used to show channel 0 alone at one decimal, which
             renders a real 0.03 mV sample as "0.0" and looks like dead
             hardware. Surface potentials here are sub-millivolt; the ADC
             resolves 7.8 uV per count at gain 16, so three decimals is real
             precision rather than decoration. -->
        <div class="channel-readout">
          <div
            v-for="channel in channelKeys"
            :key="channel"
            class="channel-metric"
          >
            <div class="value">{{ formatMv(channels[channel]) }}</div>
            <div class="label">ch{{ channel }}&ndash;{{ referenceChannel }} mV</div>
          </div>
          <div v-if="!channelKeys.length" class="value">-- mV</div>
        </div>
        <canvas ref="chart"></canvas>
        <!-- Live follows the socket; the spans read back from the daily CSVs
             so a run going for days can be scrolled through. -->
        <div class="chart-controls">
          <button
            class="control-button"
            :class="{ active: chartView === 'live' }"
            @click="goLive"
          >Live</button>
          <button
            v-for="span in rangeSpans"
            :key="span.seconds"
            class="control-button"
            :class="{ active: chartView === 'range' && rangeSpanS === span.seconds }"
            @click="showRange(span.seconds)"
          >{{ span.label }}</button>
          <span class="chart-controls-gap"></span>
          <!-- Halve or double the window around its centre. The drag gesture
               zooms too, but it needs a mouse and a steady hand; these are
               the version that works on a phone. -->
          <button
            class="control-button"
            :disabled="rangeLoading || !canZoomIn"
            @click="zoomRange(0.5)"
            title="Zoom in"
          >+</button>
          <button
            class="control-button"
            :disabled="rangeLoading || !canZoomOut"
            @click="zoomRange(2)"
            title="Zoom out"
          >&minus;</button>
          <button
            class="control-button"
            :disabled="rangeLoading || !canStepBack"
            @click="stepRange(-1)"
            title="Earlier"
          >&lsaquo;</button>
          <button
            class="control-button"
            :disabled="rangeLoading || !canStepForward"
            @click="stepRange(1)"
            title="Later"
          >&rsaquo;</button>
        </div>
        <div class="timestamp">
          <template v-if="chartView === 'range'">
            {{ rangeLoading ? 'Loading\u2026' : rangeLabel }}
          </template>
          <template v-else>Last update: {{ lastUpdateTime }}</template>
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
import zoomPlugin from 'chartjs-plugin-zoom'
// Registers itself with Chart.js; the time scale below does not work without
// a date adapter of some kind.
import 'chartjs-adapter-date-fns'
import { format as formatDate } from 'date-fns'
import AdminPanel from './components/AdminPanel.vue'
import TurnLog from './components/TurnLog.vue'
import PhaseLock from './components/PhaseLock.vue'
import SlimeViz from './components/SlimeViz.vue'

Chart.register(...registerables)
// Wheel/drag zoom and pan on the electrical chart. Registered globally with
// Chart itself, so it is available to every chart in the app rather than
// configured per instance.
Chart.register(zoomPlugin)

// Live window, shared by both chart modes. 300 samples at 1 Hz -- the span
// trimChart has always used for raw, matched here so the raw/signal toggle
// does not change the timescale.
const LIVE_SPAN_S = 300

// Signal mode refetches rather than appending: the gate needs a server-side
// window. Held low because store.between() scans the whole day's CSV per call
// (~126 ms and growing with the file), not because the DSP is expensive -- the
// chain itself is ~36 ms for three channels. The label reads from this so the
// two cannot drift apart.
const SIGNAL_REFRESH_MS = 10000

// The ghost band is two datasets per channel -- gh<n> upper, gl<n> lower --
// because Chart.js fills between datasets, not within one. They are context,
// not series to read values off, so they stay out of the legend and tooltip.
const isGhost = (label = '') => /^g[hl]\d/.test(label)
// The page is set in a monospace face; the chart is part of the page, not a
// widget dropped into it, so its axes and legend follow.
Chart.defaults.font.family = "ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, monospace"
Chart.defaults.font.size = 11
Chart.defaults.color = '#8f8f8f'

export default {
  name: 'App',
  components: { AdminPanel, TurnLog, SlimeViz, PhaseLock },
  data() {
    return {
      // App version - increment on each deployment
      appVersion: '1.0.26',
      
      // API configuration
      apiUrl: window.location.origin,
      // Paper colour. Persisted, because a dashboard on a wall should come back
      // the way it was left after a reload.
      theme: localStorage.getItem('sllm-theme') === 'light' ? 'light' : 'dark',
      isLogsRoute: window.location.pathname.replace(/\/+$/, '') === '/logs',
      isVizRoute: window.location.pathname.replace(/\/+$/, '') === '/viz',
      socket: null,
      
      // Electrical readings
      currentReading: 0,
      channels: {},              // channel id -> mV, straight from the ADC
      referenceChannel: 3,       // ADS1115 mux: 0,1,2 are read against A3
      lastReadingTimestamp: 0,   // dedupe, see updateChart
      // Raw or slime-attributable. The chain needs a 1 h window and a 10 min
      // high-pass run-in, so it cannot run per-sample in the browser: signal
      // mode always reads the server endpoint, live included.
      signalMode: false,
      gateFraction: {},          // per channel, fraction of the window gated
      signalUpdatedAt: null,     // ms since epoch, last successful refetch
      readingsHistory: [],
      chart: null,
      // 'live' follows the socket, 'range' reads a window back from the daily
      // CSVs. Both cannot drive the chart -- see updateChart.
      // NOT viewMode: that name belongs to the livestream/timelapse switch.
      chartView: 'live',
      rangeSpanS: 3600,
      rangeEnd: 0,               // unix seconds, right edge of the window
      rangeLoading: false,
      // Bumped per range fetch. A zoom press fires while an earlier fetch is
      // still out; without this the slower, wider response lands last and
      // overwrites the window the user actually asked for.
      rangeRequest: 0,
      extent: { earliest: null, latest: null },
      
      // Liveable range for Physarum polycephalum, in the units on screen.
      //   temp  20-28 C grows; slows below ~15, cooks above ~32.
      //   rh    80-99 %. Needs near-saturation, desiccates below ~65. The dish
      //         rests at 98-99, so a ceiling of 97 sat amber permanently.
      envBands: {
        temperature: { good: [20, 28], warn: [15, 32] },
        humidity: { good: [80, 99], warn: [65, 100] }
      },
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
      // Bucketed chamber readings covering the loaded frames, oldest first.
      // Fetched once per image-list load rather than per frame: scrubbing at
      // 20fps would otherwise be 20 requests a second at the Pi.
      frameEnvironment: null,
      environmentTrack: [],
      environmentBucketS: 60,
      imageError: false,
      imageKey: 0, // Used to force img element re-render
      capturingImage: false, // Prevent concurrent captures
      viewMode: 'livestream', // 'livestream' or 'timelapse'
      maxImages: 500, // Max images held in memory at once
      totalImagesOnServer: 0, // Full archive size reported by /api/images
      cameraAvailable: null, // null until /api/status reports; false hides livestream
      viewModeChosenByUser: false, // Don't override an explicit toggle
      isPlaying: false, // Timelapse playback, advances the scrubber on a timer
      playbackTimer: null,
      playbackIntervalMs: 200, // 5 frames/sec -- slow enough to read growth
      // Frames are ~135KB each, so at 200ms the browser cannot fetch them as
      // fast as the timer advances and playback sits on whatever is decoded.
      // They are warmed into the browser cache before play starts.
      loadedUrls: markRaw(new Set()),
      isPreloading: false,
      preloadCancelled: false,
      preloadLoaded: 0,
      preloadTotal: 0,

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
    temperatureState() {
      return this.bandState(this.temperature, this.envBands.temperature)
    },

    humidityState() {
      return this.bandState(this.humidity, this.envBands.humidity)
    },

    rangeSpans() {
      return [
        { label: '1h', seconds: 3600 },
        { label: '6h', seconds: 21600 },
        { label: '24h', seconds: 86400 },
        { label: 'week', seconds: 604800 },
        { label: 'month', seconds: 2592000 },
      ]
    },

    canStepBack() {
      // Always available from Live -- stepping back is how you leave it.
      if (this.chartView !== 'range') return true
      const { earliest } = this.extent
      return earliest === null || this.rangeEnd - this.rangeSpanS > earliest
    },

    canStepForward() {
      // Nothing to step forward to when the view is already at now.
      if (this.chartView !== 'range') return false
      const { latest } = this.extent
      return latest === null || this.rangeEnd < latest
    },

    canZoomIn() {
      // 60s is the floor: a bucket below that holds a single sample, so
      // zooming further only stretches the same points.
      if (this.chartView !== 'range') return true
      return this.rangeSpanS > 60
    },

    canZoomOut() {
      // Nothing to widen into once the window already spans the whole record.
      if (this.chartView !== 'range') return true
      const { earliest, latest } = this.extent
      if (earliest === null || latest === null) return true
      return this.rangeSpanS < latest - earliest
    },

    rangeLabel() {
      if (this.chartView !== 'range' || !this.rangeEnd) return ''
      const start = new Date((this.rangeEnd - this.rangeSpanS) * 1000)
      const end = new Date(this.rangeEnd * 1000)
      return `${this.stampDate(start)} \u2192 ${this.stampDate(end)}`
    },

    channelKeys() {
      // Numeric sort: object key order is insertion order from JSON, which is
      // whatever the ADC dict happened to yield.
      return Object.keys(this.channels).sort((a, b) => Number(a) - Number(b))
    },
    signalCadence() {
      // Cadence plus the last stamp: the first says how often to expect
      // movement, the second says it is still happening.
      const every = `every ${Math.round(SIGNAL_REFRESH_MS / 1000)}s`
      if (!this.signalUpdatedAt) return every
      return `${every} \u00b7 ${this.stampDate(this.signalUpdatedAt, true).slice(-8)}`
    },

    playButtonLabel() {
      if (this.isPreloading) return 'Cancel loading'
      return this.isPlaying ? 'Pause' : 'Play timelapse'
    },
    currentImageTime() {
      const image = this.images[this.timelinePosition]
      if (!image) return null
      return this.stampDate(image.at * 1000, true)
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

    // Same for /viz: SlimeViz owns its own canvas and its own loop, and the
    // dashboard's chart, socket and image archive would all be work done for a
    // view nobody is looking at. The theme is still applied, because the
    // renderer reads --paper and --ink off the root.
    if (this.isVizRoute) {
      console.log('🦠 Field view')
      this.applyTheme()
      return
    }

    this.applyTheme()
    this.initializeChart()
    // Seed before the socket. initializeChart defers to $nextTick, and history
    // must land before any live sample or it draws to the right of it.
    await this.$nextTick()
    await this.loadReadingsHistory()
    this.connectSocket()
    this.loadImages()
    // Resolve camera availability before starting capture, so we don't poll a
    // camera that isn't there (and can open straight into timelapse instead)
    await this.checkStatus()
    this.startImageCapture()
  },
  
  beforeUnmount() {
    clearInterval(this._signalTimer)
    // Clean up
    if (this.socket) {
      this.socket.disconnect()
    }
    if (this.imageInterval) clearInterval(this.imageInterval)
    if (this.fallbackInterval) clearInterval(this.fallbackInterval)
    this.stopPlayback()
    if (this.chart) this.chart.destroy()
  },
  
  watch: {
    // Every path that moves the scrubber -- drag, playback tick, jump to
    // newest -- goes through this one place rather than remembering to call it.
    timelinePosition() {
      this.updateFrameEnvironment()
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
        // The server emits every SOCKET_EMIT_INTERVAL (0.5s) but the ADC only
        // samples at ADC_SAMPLE_RATE (1Hz), so the same sample arrives twice.
        // Charting both halves the real span of the 50-point window and puts a
        // stair-step on every edge. The sample timestamp is the identity.
        if (data.timestamp && data.timestamp === this.lastReadingTimestamp) return
        this.lastReadingTimestamp = data.timestamp

        this.currentReading = data.value ?? 0
        this.channels = data.channels || {}
        const date = new Date(data.datetime)
        this.lastUpdateTime = this.stampDate(date, true)
        this.updateChart(data)
      })
      
      this.socket.on('environment_update', (data) => {
        this.temperature = data.temperature
        this.temperatureF = data.temperature_f
        this.humidity = data.humidity
        this.hasEnvironmentalData = true
        const date = new Date(data.datetime)
        this.environmentUpdateTime = `Last update: ${this.stampDate(date, true)}`
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

        // Chart.js calls option callbacks with its own `this`.
        const self = this

        const chart = new Chart(ctx, {
          type: 'line',
          // Datasets are added per channel as readings arrive -- the ADC's
          // channel set comes from api/config.py (ADC_CHANNELS), so the chart
          // follows the hardware rather than hardcoding three traces.
          data: { labels: [], datasets: [] },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            // Only the zoom buttons animate: every other update passes 'none'
            // and bypasses this. 250ms is short enough that a second press
            // lands before the eye has settled, so holding + still tracks.
            animation: { duration: 250 },
            plugins: {
              legend: {
                display: true,
                // padding is the gap between legend entries; the default 10 packs
                // the dots close enough that the colours read as one swatch strip.
                labels: {
                  color: '#c8c8c8',
                  boxWidth: 22,
                  usePointStyle: true,
                  padding: 26,
                  filter: (item) => !isGhost(item.text)
                }
              },
              tooltip: {
                enabled: true,
                filter: (item) => !isGhost(item.dataset && item.dataset.label),
                callbacks: {
                  label: (item) =>
                    `${item.dataset.label}: ${item.parsed.y.toFixed(3)} mV`,
                  // backgroundColor is transparent so the legend can show the
                  // dash, which left the tooltip swatches blank. Use the border
                  // colour and carry the dash across.
                  labelColor: (item) => ({
                    backgroundColor: item.dataset.borderColor,
                    borderColor: item.dataset.borderColor,
                    borderWidth: 2,
                    borderDash: item.dataset.borderDash || []
                  })
                }
              },
              decimation: {
                enabled: false
              },
              zoom: {
                // Both gestures refetch rather than just rescaling what is
                // already drawn: the points are server-side buckets, so zooming
                // in has to ask for finer ones or it only magnifies the same
                // ~600 samples.
                pan: {
                  // Shift, because a bare drag now selects a zoom region. The
                  // step buttons are the pointer-only way to move sideways.
                  enabled: true,
                  mode: 'x',
                  modifierKey: 'shift',
                  onPanComplete: ({ chart }) => self.onViewChanged(chart)
                },
                zoom: {
                  // Drag a region to zoom into it. This is the primary gesture
                  // because it is the only one that works on every device --
                  // a wheel is not available on a touchpad-only laptop or a
                  // tablet, so zoom cannot depend on it.
                  drag: {
                    enabled: true,
                    backgroundColor: 'rgba(255, 255, 255, 0.10)',
                    borderColor: 'rgba(255, 255, 255, 0.40)',
                    borderWidth: 1
                  },
                  // Both kept as extras for whoever has them.
                  wheel: { enabled: true, modifierKey: 'ctrl' },
                  pinch: { enabled: true },
                  mode: 'x',
                  onZoomComplete: ({ chart }) => self.onViewChanged(chart)
                },
                limits: {
                  // Width floor only, no min/max -- see refreshExtent for why
                  // bounding the axis here shifted drag selections. A minute is
                  // the floor because below that a bucket holds one sample.
                  x: { minRange: 60000 }
                }
              }
            },
            interaction: {
              intersect: false,
              mode: 'index'
            },
            scales: {
              x: {
                // A time scale, not linear over epoch ms: the linear scale
                // rounds bounds to 'nice' numbers, which at 1.787e12 is minutes
                // away, so a 5 min window drew adrift in a much wider axis.
                // `bounds: 'data'` ends the axis at the data, not the next tick.
                type: 'time',
                bounds: 'data',
                display: true,
                time: {
                  // One set of formats covering seconds through months: the
                  // same chart shows a five minute window and a month.
                  displayFormats: {
                    second: 'HH:mm:ss',
                    minute: 'HH:mm',
                    hour: 'HH:mm',
                    day: 'd MMM',
                    week: 'd MMM',
                    month: 'MMM yyyy'
                  },
                  tooltipFormat: 'dd.MM.yyyy HH:mm:ss'
                },
                grid: {
                  color: 'rgba(255, 255, 255, 0.1)'
                },
                ticks: {
                  color: '#8f8f8f',
                  maxTicksLimit: 6,
                  autoSkip: true,
                  // Show the date only once the window crosses a day; inside
                  // 24h every tick repeats it. Regular function: Chart.js calls
                  // tick callbacks with the scale as `this`.
                  callback: function (value) {
                    const span = (this.max - this.min) || 0
                    const at = new Date(value)
                    if (span > 7 * 86400000) return formatDate(at, 'dd.MM.yyyy')
                    if (span > 86400000) return formatDate(at, 'dd.MM.yyyy HH:mm')
                    if (span < 600000) return formatDate(at, 'HH:mm:ss')
                    return formatDate(at, 'HH:mm')
                  }
                },
                title: {
                  color: '#c8c8c8'
                }
              },
              y: {
                display: true,
                // suggestedMin/Max set the resting scale, not a clamp -- the
                // axis still expands for anything larger. +/-5 mV is where
                // surface potentials live (see gpio/adc.py). A hard -10..10
                // drew the noise floor as a flat line on the zero gridline.
                suggestedMin: -5,
                suggestedMax: 5,
                grid: {
                  color: 'rgba(255, 255, 255, 0.1)'
                },
                ticks: {
                  color: '#8f8f8f',
                  callback: (value) => Number(value).toFixed(2)
                },
                title: {
                  color: '#c8c8c8'
                }
              }
            }
          }
        })
        this.chart = markRaw(chart)
      })
    },
    
    updateFrameEnvironment() {
      // Nearest bucket, but only if it is actually near: frames either side of
      // an outage would otherwise borrow a reading from hours away and present
      // it as a measurement.
      this.frameEnvironment = null
      const image = this.images[this.timelinePosition]
      if (!image || !this.environmentTrack.length) return
      const at = image.at
      if (!isFinite(at)) return

      let best = null
      let bestGap = Infinity
      for (const point of this.environmentTrack) {
        const gap = Math.abs(point.t - at)
        if (gap < bestGap) {
          bestGap = gap
          best = point
        }
      }
      // One bucket wide. Months of frames against at most 5000 buckets makes a
      // bucket an hour or more, so a fixed one-minute tolerance rejected every
      // match and read as 'no chamber data'.
      const tolerance = Math.max(60, this.environmentBucketS)
      if (!best || bestGap > tolerance) return
      if (typeof best.temperature_c !== 'number'
          || typeof best.humidity_pct !== 'number') return
      this.frameEnvironment = best
    },

    async loadEnvironmentTrack() {
      // One window covering every loaded frame. Buckets are matched to the
      // frame count so each frame has roughly its own bucket, capped by what
      // the endpoint allows.
      this.environmentTrack = []
      this.frameEnvironment = null
      if (this.images.length < 1) return

      const times = this.images.map(image => image.at).filter(t => isFinite(t))
      if (!times.length) return

      const start = Math.min(...times)
      const end = Math.max(...times)
      const buckets = Math.min(5000, Math.max(1, this.images.length))
      this.environmentBucketS = ((end + 60) - (start - 60)) / buckets
      try {
        const response = await axios.get(`${this.apiUrl}/api/environment/range`, {
          params: {
            start: start - 60,
            end: end + 60,
            buckets
          }
        })
        this.environmentTrack = (response.data || {}).points || []
        this.updateFrameEnvironment()
        console.log(`\ud83c\udf21\ufe0f  Chamber track: ${this.environmentTrack.length} buckets `
          + `from ${response.data.samples} samples`)
      } catch (error) {
        console.warn('Could not load chamber track:', error.message)
      }
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
          timestamp: image.datetime,
          // Unix seconds, not `datetime`: that carries no UTC offset, so
          // new Date() reads it as browser-local. The page is watched nine
          // hours off the rig, which blanked the overlay.
          at: image.timestamp
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
        this.loadEnvironmentTrack()
      } catch (error) {
        console.warn('Could not load image archive:', error.message)
      }
    },

    startImageCapture() {
      // The page is a VIEWER and must never drive a capture on its own.
      // Every capture fires the imaging flash over the organism, so a page-load
      // POST made optical stimulus a function of web traffic. The backend
      // timelapse is the only source; this renders the image_captured event.
      // The Capture Image button still works -- that is a human action.
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
        if (typeof config.adc_reference_channel === 'number') {
          this.referenceChannel = config.adc_reference_channel
        }

      } catch (error) {
        console.warn('Could not fetch config, using defaults')
        this.imageCaptureInterval = 60 * 1000 // Default 1 minute for livestream still captures
        this.maxExposureDuration = 30
      }
    },
    
    chartInk() {
      // Chart.js takes plain colour values, not CSS variables, so the two
      // themes are spelled out here rather than read off the stylesheet.
      return this.theme === 'light'
        ? { axis: '#6a6a6a', legend: '#3a3a3a', grid: 'rgba(0, 0, 0, 0.12)' }
        : { axis: '#8f8f8f', legend: '#c8c8c8', grid: 'rgba(255, 255, 255, 0.1)' }
    },

    applyTheme() {
      document.documentElement.dataset.theme = this.theme
      if (!this.chart) return
      const ink = this.chartInk()
      const scales = this.chart.options.scales
      for (const axis of [scales.x, scales.y]) {
        axis.ticks.color = ink.axis
        axis.grid.color = ink.grid
        axis.title.color = ink.legend
      }
      this.chart.options.plugins.legend.labels.color = ink.legend
      for (const dataset of this.chart.data.datasets) {
        const channel = dataset.label.slice(2)
        const ghost = dataset.label.startsWith('gh') || dataset.label.startsWith('gl')
        const colour = ghost ? this.ghostColour(channel) : this.channelColour(channel)
        dataset.borderColor = colour
        if (ghost && dataset.fill) dataset.backgroundColor = this.ghostColour(channel, 0.13)
      }
      this.chart.update('none')
    },

    toggleTheme() {
      this.theme = this.theme === 'dark' ? 'light' : 'dark'
      localStorage.setItem('sllm-theme', this.theme)
      this.applyTheme()
    },

    channelColour(channel) {
      // Trace colour = the physical colour of that electrode's lead, so the
      // dish and the graph match without a lookup table. The dash pattern says
      // it a second way, for greyscale and for colour-blind readers.
      // ADS input -> lead -> board A row -> Cat6 pair:
      //   A0  yellow  r38L  orange   solid
      //   A1  blue    r40L  blue     dashed
      //   A2  green   r40R  green    dotted
      //   A3  white   r38R  brown    (reference)
      // ch0 follows the Cat6 pair colour (orange), not the ADS lead (yellow).
      // Lightened off pure hues for the black panel. Same hues in both themes;
      // the light set is stepped down to hold contrast on white.
      const palette = this.theme === 'light'
        ? ['#b4560e', '#1f6fb0', '#2f8f45', '#333333']
        : ['#ef9040', '#5aa9e6', '#5ecb6e', '#e8e8e8']
      return palette[Number(channel) % palette.length]
    },

    channelDash(channel) {
      // Chart.js borderDash. Empty = solid.
      const dashes = [[], [7, 4], [2, 3], [1, 5]]
      return dashes[Number(channel) % dashes.length]
    },

    stampDate(value, withSeconds = false) {
      // DD.MM.YYYY everywhere. toLocaleString follows the browser's locale,
      // which renders MM/DD/YYYY for anyone whose machine is set to en-US --
      // and the same reading then reads as a different date depending on who
      // opened the page.
      const at = value instanceof Date ? value : new Date(value)
      if (Number.isNaN(at.getTime())) return ''
      const pad = (n) => String(n).padStart(2, '0')
      const date = `${pad(at.getDate())}.${pad(at.getMonth() + 1)}.${at.getFullYear()}`
      const time = `${pad(at.getHours())}:${pad(at.getMinutes())}`
        + (withSeconds ? `:${pad(at.getSeconds())}` : '')
      return `${date} ${time}`
    },

    bandState(value, band) {
      // Colour only, deliberately: the readout is glanced at from the bench.
      // Costs protanopes the distinction, green and yellow being ~8 dE apart.
      if (typeof value !== 'number' || Number.isNaN(value)) {
        return 'env-metric-unknown'
      }
      const [goodLow, goodHigh] = band.good
      const [warnLow, warnHigh] = band.warn
      if (value >= goodLow && value <= goodHigh) return 'env-metric-good'
      if (value >= warnLow && value <= warnHigh) return 'env-metric-warn'
      return 'env-metric-danger'
    },

    formatMv(value) {
      // Three decimals is 1 uV, and the ADS1115 at gain 16 resolves 7.8 uV per
      // count -- so this shows everything the hardware can actually distinguish
      // and no more.
      return typeof value === 'number' ? value.toFixed(3) : '--'
    },

    datasetFor(channel) {
      const label = `ch${channel}`
      let dataset = this.chart.data.datasets.find(d => d.label === label)
      if (!dataset) {
        const colour = this.channelColour(channel)
        dataset = {
          label,
          // Starts empty: points carry their own x, so a channel appearing
          // late simply begins where it begins.
          data: [],
          borderColor: colour,
          // Transparent, not the trace colour: nothing is filled here, and a
          // solid backgroundColor makes the legend swatch a filled block that
          // hides the dash.
          backgroundColor: 'transparent',
          borderDash: this.channelDash(channel),
          borderWidth: 1.5,
          tension: 0.4,
          pointRadius: 0,
          // A line in the legend rather than a dot, so the swatch shows the
          // dash pattern that identifies the trace.
          pointStyle: 'line',
          spanGaps: true
        }
        this.chart.data.datasets.push(dataset)
      }
      return dataset
    },

    appendSample(reading) {
      // Each point carries its own x, so a channel that starts or stops
      // reporting cannot shift its series relative to the others -- which is
      // what the parallel label and value arrays had to be padded to avoid.
      const channels = reading.channels || {}
      const at = (reading.timestamp || Date.now() / 1000) * 1000
      Object.keys(channels).forEach(channel => this.datasetFor(channel))
      for (const dataset of this.chart.data.datasets) {
        const value = channels[dataset.label.slice(2)]
        if (typeof value === 'number') dataset.data.push({ x: at, y: value })
      }
    },

    trimChart(maxPoints = 300) {
      // 300 samples at 1Hz is five minutes of trace -- enough to see a
      // contraction, since Physarum's period is around 90 to 140 seconds.
      for (const dataset of this.chart.data.datasets) {
        while (dataset.data.length > maxPoints) dataset.data.shift()
      }
    },

    async refreshExtent() {
      try {
        const response = await axios.get(`${this.apiUrl}/api/readings/extent`)
        this.extent = response.data || { earliest: null, latest: null }
        // No min/max limit, deliberately. The plugin does not clip a selection
        // crossing a limit, it slides the whole window back inside it (fixRange
        // in chartjs-plugin-zoom), so a drag past the last-read extent came back
        // shifted into the past. The step and zoom buttons clamp already.
      } catch (error) {
        console.warn('Could not read history extent:', error.message)
      }
    },

    async goLive() {
      this.chartView = 'live'
      clearTimeout(this._viewTimer)
      clearTimeout(this._loadingTimer)
      this.rangeLoading = false
      // Invalidate whatever is in flight. A range fetch resolving after this
      // pins the axis back to the window we just left, and live samples then
      // append outside it. A week fetch takes ~2s.
      this.rangeRequest++
      // Full reset, not just a view switch: drop the scrollback anchor and the
      // zoomed span too, so the next range click starts from now at a whole
      // span rather than resuming the odd 137-second window a drag left behind
      // -- which also puts the span buttons back in step with what is drawn.
      this.rangeEnd = 0
      this.rangeSpanS = 3600
      this.clearChart()
      // Order matters: resetZoom restores the bounds captured at the first
      // gesture -- the pinned window -- so unpin after it. It also fires
      // onZoomComplete, which would flip straight back to range mode; it is
      // synchronous, so a flag around the call is enough.
      this._resettingZoom = true
      if (this.chart.resetZoom) this.chart.resetZoom('none')
      this._resettingZoom = false
      delete this.chart.options.scales.x.min
      delete this.chart.options.scales.x.max
      this.chart.update('none')
      if (this.signalMode) {
        // The chain needs a server-side window, so live here is a trailing
        // refetch rather than a socket append. 10 s: a cold call costs the Pi
        // ~0.3 s and the gate moves on the timescale of a tube arriving, so
        // there is nothing to gain from going faster.
        await this.refreshSignalLive()
        clearInterval(this._signalTimer)
        this._signalTimer = setInterval(() => this.refreshSignalLive(), SIGNAL_REFRESH_MS)
        return
      }
      await this.loadReadingsHistory()
    },

    async refreshSignalLive() {
      if (!this.signalMode || this.chartView !== 'live' || !this.chart) return
      const end = Date.now() / 1000
      // Match raw live exactly. Raw is trimChart(300) -- 300 samples at 1 Hz,
      // five minutes. Anything else and toggling raw/signal silently changes
      // the timescale under you. The span buttons are how you widen it, and
      // they already work in signal mode.
      const start = end - LIVE_SPAN_S
      const seq = ++this.rangeRequest
      try {
        const drawn = await this.loadProcessed(start, end, seq)
        if (drawn === null) return
        this.chart.options.scales.x.min = start * 1000
        this.chart.options.scales.x.max = end * 1000
        this.chart.update('none')
      } catch (error) {
        console.warn('Could not refresh signal:', error.message)
      }
    },

    async showRange(seconds) {
      await this.refreshExtent()
      // Anchor a first scrollback at the newest sample on disk. Switching span
      // while already scrolled back keeps the right edge, so 1h -> 6h zooms out
      // around where you were looking instead of jumping to now.
      if (this.chartView !== 'range' || !this.rangeEnd) {
        this.rangeEnd = this.extent.latest || Date.now() / 1000
      }
      this.rangeSpanS = seconds
      this.chartView = 'range'
      await this.loadRange()
    },

    async stepRange(direction) {
      if (this.chartView !== 'range') {
        // Stepping out of Live: anchor on the newest sample on disk so the
        // arrows work without having to choose a span first.
        await this.refreshExtent()
        this.rangeEnd = this.extent.latest || Date.now() / 1000
        this.chartView = 'range'
      }
      let end = this.rangeEnd + direction * this.rangeSpanS
      const { earliest, latest } = this.extent
      if (latest !== null) end = Math.min(end, latest)
      if (earliest !== null) end = Math.max(end, earliest + this.rangeSpanS)
      this.rangeEnd = end
      this.loadRange()
    },

    async zoomRange(factor) {
      if (this.chartView !== 'range') {
        // Same anchor as the step buttons: zooming out of Live starts from the
        // newest sample on disk rather than from the live window, which is
        // whatever the socket has delivered since the page loaded.
        await this.refreshExtent()
        this.rangeEnd = this.extent.latest || Date.now() / 1000
        this.chartView = 'range'
      }
      const { earliest, latest } = this.extent
      // Around the centre, not the right edge: whatever you are looking at
      // stays in frame instead of sliding off to the left as the window grows.
      const centre = this.rangeEnd - this.rangeSpanS / 2
      let span = this.rangeSpanS * factor
      span = Math.max(60, span)
      if (earliest !== null && latest !== null) {
        span = Math.min(span, latest - earliest)
      }
      let end = centre + span / 2
      if (latest !== null) end = Math.min(end, latest)
      if (earliest !== null) end = Math.max(end, earliest + span)
      this.rangeSpanS = span
      this.rangeEnd = end
      // Rescale what is already on the canvas before asking the server for
      // anything. The refetch is what actually adds resolution -- the points
      // are server-side buckets -- but pinning the axis now means the press
      // reads as instant instead of as a round trip to a Pi reading CSVs.
      this.chart.options.scales.x.min = (end - span) * 1000
      this.chart.options.scales.x.max = end * 1000
      this.chart.update()
      // Debounced: four presses in a row are one fetch at the final width, not
      // four fetches of which three are already stale on arrival.
      clearTimeout(this._viewTimer)
      this._viewTimer = setTimeout(() => this.loadRange(), 200)
    },

    clearChart() {
      if (!this.chart) return
      this.chart.data.labels = []
      for (const dataset of this.chart.data.datasets) dataset.data = []
    },




    onViewChanged(chart) {
      // Fired by our own resetZoom rather than by a pan or a drag.
      if (this._resettingZoom) return
      const scale = chart.scales.x
      if (!scale || !isFinite(scale.min) || !isFinite(scale.max)) return
      // Any manual pan or zoom means the user is looking at a window, not at
      // now; following live would undo the gesture on the next sample.
      this.chartView = 'range'
      this.rangeEnd = scale.max / 1000
      this.rangeSpanS = Math.max(60, (scale.max - scale.min) / 1000)
      // Debounced: a wheel zoom fires this several times a second and each one
      // would otherwise re-read the CSVs.
      clearTimeout(this._viewTimer)
      this._viewTimer = setTimeout(() => this.loadRange(), 250)
    },

    setSignalMode(on) {
      if (this.signalMode === on) return
      this.signalMode = on
      this.gateFraction = {}
      // Datasets differ between modes -- signal adds a two-dataset ghost band
      // per channel and the band's fill targets its partner by position. Empty
      // them and the stale ones persist, so drop them outright.
      this.chart.data.datasets.length = 0
      this.clearChart()
      clearInterval(this._signalTimer)
      this._signalTimer = null
      if (this.chartView === 'range') {
        this.loadRange()
      } else {
        this.goLive()
      }
    },

    // Ghost = high-passed raw, drawn faint behind the gated trace. Its only
    // job is liveness: a flat signal line means no organism, but a frozen
    // feed draws the same picture, and the ghost is never flat while data is
    // arriving.
    // Two adjacent datasets per channel, upper then lower, filled between. A
    // single mean line hides spikes narrower than a bucket -- the same reason
    // the raw endpoint carries min/max -- and plotting only the max drew a
    // one-sided envelope sitting above the flat line instead of straddling it.
    //
    // The fill targets '+1', i.e. the next dataset by position, so the pair
    // must stay adjacent. loadProcessed builds all bands before any signal
    // trace to keep that true.
    ghostBandFor(channel) {
      const upper = `gh${channel}`
      if (this.chart.data.datasets.find(d => d.label === upper)) return
      this.chart.data.datasets.push({
        label: upper,
        data: [],
        borderColor: this.ghostColour(channel),
        backgroundColor: this.ghostColour(channel, 0.13),
        borderWidth: 1,
        borderDash: [],
        pointRadius: 0,
        tension: 0,
        fill: '+1',
        order: 10          // behind the signal trace
      })
      this.chart.data.datasets.push({
        label: `gl${channel}`,
        data: [],
        borderColor: this.ghostColour(channel),
        borderWidth: 1,
        borderDash: [],
        pointRadius: 0,
        tension: 0,
        fill: false,
        order: 10
      })
    },

    ghostColour(channel, alpha = 0.22) {
      const base = this.channelColour(channel)
      const m = base.match(/^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i)
      if (!m) return base
      const [r, g, b] = m.slice(1).map(h => parseInt(h, 16))
      return `rgba(${r}, ${g}, ${b}, ${alpha})`
    },

    async loadProcessed(start, end, seq) {
      // One bucket per sample at most: a five-minute window against the 600
      // buckets a day needs would ask for half-second buckets, and every other
      // one would come back empty.
      const buckets = Math.max(60, Math.min(600, Math.round(end - start)))
      const response = await axios.get(`${this.apiUrl}/api/readings/processed`, {
        params: { start, end, buckets }
      })
      if (seq !== this.rangeRequest) return null
      const { points = [], channels = [] } = response.data || {}
      this.clearChart()
      // Bands first, as a block: the fill targets the next dataset by
      // position, so each upper/lower pair has to stay adjacent.
      for (const channel of channels) this.ghostBandFor(channel)
      for (const channel of channels) this.datasetFor(channel)
      const gated = {}
      const seen = {}
      for (const point of points) {
        const at = point.t * 1000
        for (const dataset of this.chart.data.datasets) {
          const channel = dataset.label.slice(2)
          const stats = (point.channels || {})[channel]
          if (!stats) continue
          if (dataset.label.startsWith('gh')) {
            dataset.data.push({ x: at, y: stats.ghost_max })
          } else if (dataset.label.startsWith('gl')) {
            dataset.data.push({ x: at, y: stats.ghost_min })
          } else {
            dataset.data.push({ x: at, y: stats.signal })
            gated[channel] = (gated[channel] || 0) + stats.gate
            seen[channel] = (seen[channel] || 0) + 1
          }
        }
      }
      const fraction = {}
      for (const channel of Object.keys(seen)) {
        fraction[channel] = gated[channel] / seen[channel]
      }
      this.gateFraction = fraction
      this.signalUpdatedAt = Date.now()   // ms: stampDate feeds new Date()
      return points.length
    },

    async loadRange() {
      if (!this.chart) return
      const end = this.rangeEnd
      const start = end - this.rangeSpanS
      const seq = ++this.rangeRequest
      // Deferred, not immediate: a 1h window comes back in ~60ms and a day in
      // ~300ms, so flipping the label straight away only ever showed a flash
      // of 'Loading' that read as a stall. Week and month really do take a
      // second or two, and those still say so.
      clearTimeout(this._loadingTimer)
      this._loadingTimer = setTimeout(() => {
        if (seq === this.rangeRequest) this.rangeLoading = true
      }, 400)
      try {
        if (this.signalMode) {
          const drawn = await this.loadProcessed(start, end, seq)
          if (drawn === null || this.chartView !== 'range') return
          this.chart.options.scales.x.min = start * 1000
          this.chart.options.scales.x.max = end * 1000
          this.chart.update('none')
          console.log(`\ud83e\uddec Signal: ${drawn} buckets`)
          return
        }
        const response = await axios.get(`${this.apiUrl}/api/readings/range`, {
          // Buckets, not samples: a day at 1 Hz is 86400 points and the canvas
          // is a few hundred pixels wide. The API returns min/max/mean per
          // bucket; the trace draws the mean.
          params: { start, end, buckets: 600 }
        })
        // A newer window was asked for while this was in flight; drawing it
        // now would yank the view back to where it was two clicks ago. Live
        // bumps the same counter, so this covers the switch back as well.
        if (seq !== this.rangeRequest || this.chartView !== 'range') return
        const { points = [], channels = [] } = response.data || {}
        this.clearChart()
        for (const channel of channels) this.datasetFor(channel)
        for (const point of points) {
          const at = point.t * 1000
          for (const dataset of this.chart.data.datasets) {
            const stats = (point.channels || {})[dataset.label.slice(2)]
            if (stats) dataset.data.push({ x: at, y: stats.mean })
          }
        }
        // Pin the axis to what was asked for, not to what came back. Buckets
        // with no samples in them are omitted, so letting the axis autofit
        // would silently crop a window containing a gap.
        this.chart.options.scales.x.min = start * 1000
        this.chart.options.scales.x.max = end * 1000
        this.chart.update('none')
        console.log(`\ud83d\udcc8 Range: ${points.length} buckets from `
          + `${response.data.samples} samples`)
      } catch (error) {
        console.warn('Could not load range:', error.message)
      } finally {
        if (seq === this.rangeRequest) {
          clearTimeout(this._loadingTimer)
          this.rangeLoading = false
        }
      }
    },

    updateChart(reading) {
      if (!this.chart || !this.chart.data) return
      // Signal mode draws server-computed buckets; a raw sample appended here
      // would land on the same axis in different units.
      if (this.signalMode) return
      // Scrolled back into history: appending a live sample here would drag the
      // view back to now on the next tick, which is exactly what makes
      // scrollback unusable. Nothing is lost -- the sample is on disk, and
      // Live re-seeds from the buffer.
      if (this.chartView !== 'live') return

      this.appendSample(reading)
      this.trimChart()

      try {
        this.chart.update('none')
      } catch (error) {
        console.log('Chart update error:', error)
      }
    },

    async loadReadingsHistory() {
      // The chart used to start empty and fill one sample per second, so the
      // first few minutes after a page load showed a near-empty panel whatever
      // the ADC was doing. The API already keeps a rolling buffer; use it.
      try {
        const response = await axios.get(`${this.apiUrl}/api/readings/history`, {
          params: { limit: 300 }
        })
        const samples = response.data
        if (!Array.isArray(samples) || !samples.length || !this.chart) return

        for (const sample of samples) this.appendSample(sample)
        this.trimChart()
        this.chart.update('none')

        const newest = samples[samples.length - 1]
        this.lastReadingTimestamp = newest.timestamp || 0
        this.currentReading = newest.value ?? 0
        this.channels = newest.channels || {}
        console.log(`📈 Seeded chart with ${samples.length} archived samples`)
      } catch (error) {
        console.warn('Could not load readings history:', error.message)
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

      // A frame landing mid-playback must not yank the view to the live end.
      // The backend captures every 300s, so a long timelapse will have several
      // arrive while it plays; jumping each time would make playback unusable.
      // The frame is still appended -- playback simply reaches it in order.
      if (!this.isPlaying) {
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
      }
      
      // Keep only the most recent images to prevent memory issues
      if (this.images.length > this.maxImages) {
        const oldImage = this.images.shift()
        // Revoke blob URLs if they exist
        if (oldImage.url && oldImage.url.startsWith('blob:')) {
          URL.revokeObjectURL(oldImage.url)
        }
        // Every index shifted down by one. Mid-playback the playhead has to
        // follow its frame down rather than snap to the end, or evicting the
        // oldest image would silently skip playback to the newest.
        this.timelinePosition = this.isPlaying
          ? Math.max(0, this.timelinePosition - 1)
          : this.images.length - 1
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
    
    preloadFrame(url) {
      // Resolves once the browser holds the frame, so the <img> swap during
      // playback is a cache hit. An error resolves too: one unreachable frame
      // must not wedge the whole preload.
      if (this.loadedUrls.has(url)) return Promise.resolve()
      return new Promise((resolve) => {
        const img = new Image()
        img.onload = () => { this.loadedUrls.add(url); resolve() }
        img.onerror = () => resolve()
        img.src = url
      })
    },

    async preloadAll(urls) {
      // Browsers cap concurrent connections per host at around six anyway;
      // firing all 100 at once just queues them somewhere less visible.
      const CONCURRENCY = 6
      let cursor = 0
      const worker = async () => {
        while (cursor < urls.length && !this.preloadCancelled) {
          await this.preloadFrame(urls[cursor++])
          this.preloadLoaded++
        }
      }
      const workers = Array.from(
        { length: Math.min(CONCURRENCY, urls.length) }, () => worker()
      )
      await Promise.all(workers)
    },

    async togglePlayback() {
      // A press during either preload or playback means stop.
      if (this.isPlaying || this.isPreloading) {
        this.stopPlayback()
        return
      }
      if (this.images.length < 2) return

      // Pressing play while parked on the last frame replays from the start,
      // rather than appearing to do nothing.
      if (this.timelinePosition >= this.images.length - 1) {
        this.timelinePosition = 0
        this.onTimelineScrub()
      }

      const urls = this.images.map(image => image.url)
      if (urls.some(url => !this.loadedUrls.has(url))) {
        this.preloadCancelled = false
        this.isPreloading = true
        this.preloadLoaded = 0
        this.preloadTotal = urls.length
        await this.preloadAll(urls)
        this.isPreloading = false
        // Stopped by a second press, or the view moved on while we waited.
        if (this.preloadCancelled || this.viewMode !== 'timelapse') return
      }

      this.isPlaying = true
      this.playbackTimer = setInterval(() => {
        const next = this.timelinePosition + 1
        if (next > this.images.length - 1) {
          this.stopPlayback()
          return
        }
        const frame = this.images[next]
        if (!frame) {
          this.stopPlayback()
          return
        }
        // Assigned here rather than through onTimelineScrub. The position was
        // advancing while the frame stayed put, which is what it looks like
        // when the helper throws inside the timer: setInterval swallows the
        // error, so the counter moves and the <img> never hears about it.
        this.timelinePosition = next
        this.currentImage = frame.url
        this.imageError = false
      }, this.playbackIntervalMs)
    },

    stopPlayback() {
      this.preloadCancelled = true
      this.isPreloading = false
      this.isPlaying = false
      if (this.playbackTimer) {
        clearInterval(this.playbackTimer)
        this.playbackTimer = null
      }
    },

    toggleViewMode() {
      this.viewModeChosenByUser = true
      // Leaving timelapse leaves the timer running over a hidden scrubber.
      this.stopPlayback()
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
          this.environmentUpdateTime = `Last update: ${this.stampDate(date, true)}`
        }
      } catch (error) {
        this.isOnline = false
      }
    }
  }
}
</script>

