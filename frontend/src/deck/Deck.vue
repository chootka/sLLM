<template>
  <!-- Two overlaid line fields. Identical spacing and angle means they sit on
       top of each other and there is no beat; separating them produces one.
       Registration is per slide, and it is drawn once, never animated. -->
  <canvas ref="field" id="field" aria-hidden="true"></canvas>
  <div id="focus" :style="{ '--fx': slide.meta.fx + '%', '--fy': slide.meta.fy + '%' }"></div>

  <main id="stage" @click="onStageClick">
    <section
      v-for="(s, i) in slides"
      :key="i"
      class="slide"
      :class="s.meta.classes"
      :hidden="i !== cur"
    >
      <component :is="s" />
    </section>
  </main>

  <div id="bar" :style="{ width: ((cur + 1) / slides.length * 100) + '%' }"></div>

  <div id="nav">
    <button type="button" aria-label="Previous slide" @click="go(-1)">&larr;</button>
    <button type="button" aria-label="Next slide" @click="go(1)">&rarr;</button>
    <button type="button" @click="gridOpen = !gridOpen">All</button>
  </div>

  <div id="hud"><span v-if="showClock" id="clock"><b>{{ elapsed }}</b> / 10:00</span></div>

  <div id="grid" v-show="gridOpen">
    <button
      v-for="(s, i) in slides"
      :key="i"
      type="button"
      :data-cur="i === cur ? '1' : '0'"
      @click="gridOpen = false; show(i)"
    >
      <span class="gn">{{ i + 1 }} · {{ s.meta.section || 'Title' }}</span>
      <span class="gt">{{ headings[i] }}</span>
    </button>
  </div>
</template>

<script>
import './deck.css'

// One file per slide, ordered by filename. Adding a slide means adding a file.
const modules = import.meta.glob('./slides/*.vue', { eager: true })
const slides = Object.keys(modules).sort().map(k => modules[k].default)

export default {
  name: 'Deck',
  data() {
    return {
      slides,
      cur: 0,
      gridOpen: false,
      showClock: false,
      startedAt: null,
      now: Date.now(),
      headings: [],
      tick: null
    }
  },
  computed: {
    slide() { return this.slides[this.cur] },
    elapsed() {
      const s = this.startedAt ? Math.round((this.now - this.startedAt) / 1000) : 0
      return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0')
    }
  },
  mounted() {
    document.title = 'sLLM Slides'
    window.addEventListener('keydown', this.onKey)
    window.addEventListener('resize', this.onResize)
    // Clicking an embedded piece moves focus into its frame and the deck stops
    // hearing arrow keys. Take focus back once the click has landed.
    window.addEventListener('blur', this.refocus)
    this.themeWatcher = new MutationObserver(this.draw)
    this.themeWatcher.observe(document.documentElement, {
      attributes: true, attributeFilter: ['data-theme']
    })
    this.media = matchMedia('(prefers-color-scheme: dark)')
    this.media.addEventListener('change', this.onScheme)
    this.tick = setInterval(() => { this.now = Date.now() }, 1000)
    // Redraw whenever the canvas box actually changes, which covers the
    // stylesheet landing, fullscreen, and the dashboard's lightbox opening.
    if (window.ResizeObserver) {
      this.boxWatcher = new ResizeObserver(() => this.draw())
      this.boxWatcher.observe(this.$refs.field)
    }
    this.show(0)
    this.$nextTick(this.readHeadings)
  },
  beforeUnmount() {
    window.removeEventListener('keydown', this.onKey)
    window.removeEventListener('resize', this.onResize)
    window.removeEventListener('blur', this.refocus)
    if (this.themeWatcher) this.themeWatcher.disconnect()
    if (this.boxWatcher) this.boxWatcher.disconnect()
    if (this.media) this.media.removeEventListener('change', this.onScheme)
    clearInterval(this.tick)
  },
  methods: {
    show(i) {
      this.cur = Math.max(0, Math.min(this.slides.length - 1, i))
      this.$nextTick(() => {
        this.draw()
        this.frameSync()
        const hold = document.querySelector('.slide:not([hidden]) .hold')
        if (hold) hold.scrollTop = 0
      })
    },
    go(d) {
      if (this.startedAt === null && d > 0) this.startedAt = Date.now()
      this.show(this.cur + d)
    },
    onStageClick(e) {
      if (e.target.closest('a,button,audio,video,iframe')) return
      this.go(e.clientX < window.innerWidth * 0.26 ? -1 : 1)
    },
    onKey(e) {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const k = e.key
      if (this.gridOpen && k !== 'g' && k !== 'G' && k !== 'Escape') return
      if (k === 'ArrowRight' || k === ' ' || k === 'PageDown' || k === 'Enter') {
        e.preventDefault(); this.go(1)
      } else if (k === 'ArrowLeft' || k === 'PageUp' || k === 'Backspace') {
        e.preventDefault(); this.go(-1)
      } else if (k === 'Home') { e.preventDefault(); this.show(0) }
      else if (k === 'End') { e.preventDefault(); this.show(this.slides.length - 1) }
      else if (k === 't' || k === 'T') {
        this.showClock = !this.showClock
        if (this.showClock && this.startedAt === null) this.startedAt = Date.now()
      } else if (k === 'r' || k === 'R') { this.startedAt = Date.now() }
      else if (k === 'f' || k === 'F') {
        if (document.fullscreenElement) document.exitFullscreen()
        else if (document.documentElement.requestFullscreen) {
          document.documentElement.requestFullscreen().catch(() => {})
        }
      } else if (k === 'g' || k === 'G' || (k === 'Escape' && this.gridOpen)) {
        this.gridOpen = !this.gridOpen
      }
    },
    refocus() {
      setTimeout(() => {
        const el = document.activeElement
        if (el && el.tagName === 'IFRAME') window.focus()
      }, 400)
    },
    // Embedded pieces load when their slide comes up and are torn down when it
    // leaves, so nothing plays behind the rest of the deck.
    frameSync() {
      const active = document.querySelector('.slide:not([hidden])')
      document.querySelectorAll('iframe[data-src]').forEach(f => {
        const on = active && active.contains(f)
        if (on && !f.getAttribute('src')) f.setAttribute('src', f.dataset.src)
        else if (!on && f.getAttribute('src')) f.removeAttribute('src')
      })
    },
    readHeadings() {
      this.headings = this.slides.map(() => '')
      const sections = document.querySelectorAll('#stage .slide')
      sections.forEach((sec, i) => {
        const h = sec.querySelector('h1, h2')
        if (h) this.headings[i] = h.textContent
      })
    },
    onScheme() { setTimeout(this.draw, 30) },
    onResize() { this.draw() },
    draw() {
      const cv = this.$refs.field
      if (!cv) return
      const ctx = cv.getContext('2d')
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      // The stylesheet can arrive after the first draw, and an unstyled canvas
      // reports its default 300x150. The viewport is the honest measure.
      const r = cv.getBoundingClientRect()
      const w = Math.round(r.width) || window.innerWidth
      const h = Math.round(r.height) || window.innerHeight
      if (!w || !h) return
      if (cv.width !== w * dpr || cv.height !== h * dpr) {
        cv.width = w * dpr; cv.height = h * dpr
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, w, h)
      const col = getComputedStyle(document.documentElement)
        .getPropertyValue('--line').trim() || 'rgba(0,0,0,.35)'
      const r = this.slide.meta.reg
      const diag = Math.hypot(w, h), p = 7.4, a = -7 * Math.PI / 180

      const field = (spacing, angle) => {
        ctx.save()
        ctx.translate(w / 2, h / 2)
        ctx.rotate(angle)
        ctx.beginPath()
        for (let x = -diag; x <= diag; x += spacing) {
          ctx.moveTo(x, -diag); ctx.lineTo(x, diag)
        }
        ctx.strokeStyle = col; ctx.lineWidth = 1; ctx.stroke()
        ctx.restore()
      }
      field(p, a)
      field(p * (1 + r * 0.052), a + r * 2.7 * Math.PI / 180)
      document.documentElement.style.setProperty('--regpx', (r * 7).toFixed(2))
    }
  }
}
</script>
