<template>
  <div class="field" @click="toggleFull">
    <canvas ref="cv"></canvas>
    <!-- Sound and fullscreen are separate gestures on purpose: a sound button
         should not seize the display. Click the field for fullscreen. -->
    <button class="sound" @click.stop="toggleSound">
      {{ running ? 'SOUND OFF' : 'SOUND ON' }}
    </button>
    <div v-if="err" class="err">{{ err }}</div>
    <router-link to="/" class="back" @click.stop>&larr;</router-link>
  </div>
</template>

<script>
import axios from 'axios'

const POLL_MS = 10000
const SPAN_S = 300
const FREE_RUN = 0.12
const DEPTH = 0.62
const SCALE_MV = 2.0

export default {
  name: 'Drift',
  data() {
    return { running: false, err: '' }
  },
  computed: {
    // ?from=<unix seconds>&mins=<window>&speed=<multiplier>
    // Replays a stored stretch instead of following the live dish. Without
    // `from` this is the live instrument and nothing below changes.
    replay() {
      const q = (this.$route && this.$route.query) || {}
      const from = Number(q.from)
      if (!from) return null
      return {
        from,
        mins: Math.max(1, Math.min(240, Number(q.mins) || 24)),
        speed: Math.max(1, Math.min(240, Number(q.speed) || 24))
      }
    },

    // ?cap=<multiplier on the 47n timing caps>. 2.13 is 100n, an octave down.
    // Lowering pitch on the real board means a bigger cap, so that is the knob
    // here too rather than an abstract tuning number.
    capScale() {
      const q = (this.$route && this.$route.query) || {}
      return Math.max(0.5, Math.min(4, Number(q.cap) || 2.13))
    },

    // ?mix=1,0.4,0.4 -- one weight per voice. Equal by default, which is the
    // board as built (100k each). These are mixer resistor ratios, so a value
    // that sounds right here is a resistor value at the bench.
    // ?vco=0 silences the PLL channel entirely.
    vcoLevel() {
      const q = (this.$route && this.$route.query) || {}
      const v = Number(q.vco)
      return Number.isFinite(v) ? Math.max(0, Math.min(1, v)) : 0.35
    },

    mixWeights() {
      const q = (this.$route && this.$route.query) || {}
      if (!q.mix) return [0.45, 1, 1]
      const parts = String(q.mix).split(',').map(Number)
      return [0, 1, 2].map(i => {
        const v = parts[i]
        return Number.isFinite(v) ? Math.max(0, Math.min(1, v)) : 1
      })
    }
  },
  mounted() {
    this.state = {
      coh: [0, 0, 0],
      freq: [140, 75, 75],
      lum: [0, 0, 0],
      drives: [FREE_RUN, FREE_RUN, FREE_RUN],
      addr: 0, vcoHz: 0, locked: false
    }
    this.buffer = [[], [], []]
    this.cursor = 0
    this.t0 = performance.now()
    document.body.classList.add('bare')
    this.resize()
    // Layout is not final on mount, and fullscreen changes the box without
    // always firing a window resize.
    requestAnimationFrame(this.resize)
    window.addEventListener('resize', this.resize)
    document.addEventListener('fullscreenchange', this.resize)
    if (window.ResizeObserver) {
      this.ro = new ResizeObserver(this.resize)
      this.ro.observe(this.$refs.cv)
    }
    this.raf = requestAnimationFrame(this.draw)
    this.fetch()
    // A replay is a fixed window; refetching would only re-request the same
    // seconds.
    if (!this.replay) this._poll = setInterval(this.fetch, POLL_MS)
    this._tick = setInterval(this.advance, 50)
  },
  beforeUnmount() {
    document.body.classList.remove('bare')
    cancelAnimationFrame(this.raf)
    window.removeEventListener('resize', this.resize)
    document.removeEventListener('fullscreenchange', this.resize)
    if (this.ro) this.ro.disconnect()
    clearInterval(this._poll)
    clearInterval(this._tick)
    if (this.node) this.node.disconnect()
    if (this.ctx) this.ctx.close()
  },
  methods: {
    // Measured off the element, not off window.innerHeight. The two disagree
    // in more cases than is worth tracking -- browser UI, scrollbars, entering
    // fullscreen, a mount that runs before layout settles -- and every
    // disagreement showed up as the field covering only part of the screen.
    resize() {
      const c = this.$refs.cv
      if (!c) return
      // The canvas's own client box, which is whatever CSS actually gave it.
      // JS must not set style.width/height here: doing so made the element's
      // size a function of a measurement, so a single bad reading pinned a bad
      // size that could never correct itself. CSS owns layout; JS only matches
      // the backing store to it.
      const w = c.clientWidth
      const h = c.clientHeight
      if (!w || !h) return
      if (w === this.w && h === this.h) return
      // Grid stays in CSS pixels so the character count and the field cost do
      // not change with the display; only the backing store scales, which is
      // what keeps glyph edges sharp on a HiDPI panel or a projector.
      const dpr = Math.min(2, window.devicePixelRatio || 1)
      this.w = w
      this.h = h
      c.width = Math.round(w * dpr)
      c.height = Math.round(h * dpr)
      // Setting canvas.width resets context state, so the transform goes on
      // after it, never before.
      c.getContext('2d').setTransform(dpr, 0, 0, dpr, 0, 0)
    },

    async toggleFull() {
      // Must ride a gesture; browsers grant fullscreen no other way.
      try {
        if (document.fullscreenElement) await document.exitFullscreen()
        else await document.documentElement.requestFullscreen({ navigationUI: 'hide' })
      } catch (e) { /* fine without */ }
    },

    async toggleSound() {
      if (this.running) {
        if (this.node) { this.node.disconnect(); this.node = null }
        if (this.ctx) { this.ctx.close(); this.ctx = null }
        this.running = false
        return
      }
      try {
        this.ctx = new (window.AudioContext || window.webkitAudioContext)()
        await this.ctx.audioWorklet.addModule('/ring-processor.js')
        this.node = new AudioWorkletNode(this.ctx, 'ring-processor', {
          // Two outputs, as the board has: ch1 the oscillator bank, ch2 the
          // PLL's VCO. Panned apart rather than summed so they stay legible.
          numberOfInputs: 0, numberOfOutputs: 1, outputChannelCount: [2]
        })
        this.node.port.onmessage = (e) => {
          const d = e.data || {}
          if (d.coh) this.state.coh = d.coh
          if (d.freq) this.state.freq = d.freq
          if (d.lum) this.state.lum = d.lum
          if (typeof d.addr === 'number') this.state.addr = d.addr
          if (typeof d.vcoHz === 'number') this.state.vcoHz = d.vcoHz
          if (typeof d.locked === 'boolean') this.state.locked = d.locked
        }
        this.node.connect(this.ctx.destination)
        this.node.port.postMessage({
          gain: 0.22, running: true, drives: this.state.drives,
          capScale: this.capScale, mix: this.mixWeights, vco: this.vcoLevel
        })
        await this.ctx.resume()
        this.running = true
        this.err = ''
      } catch (e) {
        this.err = e.message
      }
    },

    async fetch() {
      const r = this.replay
      const end = r ? r.from + r.mins * 60 : Date.now() / 1000
      const start = r ? r.from : end - SPAN_S
      const span = Math.round(end - start)
      try {
        const { data } = await axios.get('/api/readings/processed', {
          params: { start, end, buckets: Math.min(2000, span) }
        })
        const pts = data.points || []
        if (!pts.length) return
        for (let c = 0; c < 3; c++) {
          this.buffer[c] = pts.map(p => {
            const s = (p.channels || {})[String(c)] || {}
            return { gate: s.gate || 0, signal: s.signal || 0 }
          })
        }
        // Live picks up near the newest sample; a replay starts at the top.
        this.cursor = r ? 0 : Math.max(0, this.buffer[0].length - POLL_MS / 1000)
      } catch (e) { /* keep free-running */ }
    },

    advance() {
      const buf = this.buffer[0]
      if (!buf || !buf.length) return
      this.cursor += 0.05 * (this.replay ? this.replay.speed : 1)
      // Replays loop, so one can be left running in a room.
      if (this.cursor > buf.length - 1) this.cursor = this.replay ? 0 : buf.length - 1
      const i = Math.floor(this.cursor)
      const drives = []
      for (let c = 0; c < 3; c++) {
        const s = this.buffer[c][i] || { gate: 0, signal: 0 }
        drives.push(s.gate > 0.5
          ? FREE_RUN + DEPTH * Math.max(0, Math.min(1, s.signal / SCALE_MV + 0.5))
          : FREE_RUN)
      }
      this.state.drives = drives
      if (this.node) this.node.port.postMessage({ drives })
    },

    field(x, y, t, st, src, k, vco) {
      let v = 0
      for (let i = 0; i < 3; i++) {
        const dx = x - src[i][0], dy = y - src[i][1]
        const d = Math.sqrt(dx * dx + dy * dy)
        v += Math.sin(d * k[i] - t * (0.30 + 0.10 * i) + st.coh[i] * 2.2)
      }
      // The VCO is a fourth oscillator, so it is a fourth source -- not a
      // readout bolted on. Its rings sit on whichever input the 4051 selected.
      // Locked, its spacing matches that source's and the two reinforce into
      // one pattern; hunting, the spacings differ and they beat. The lock is
      // the thing you watch resolve.
      if (vco) {
        const dx = x - vco.x, dy = y - vco.y
        v += vco.amp * Math.sin(Math.sqrt(dx * dx + dy * dy) * vco.k - t * 0.45)
      }
      return v / (3 + (vco ? vco.amp : 0))
    },

    // Character grid, not pixels. The ramp quantises the field into a handful
    // of levels, and the moire falls out of that quantisation rather than
    // being drawn -- which is the whole reason it reads the way it does.
    // U+2591..2593 and U+2588 are full-width in any monospace face; the two
    // light marks extend the ramp at the dark end without breaking the grid.
    draw() {
      this.raf = requestAnimationFrame(this.draw)
      const c = this.$refs.cv
      if (!c) return
      this.resize()
      const g = c.getContext('2d')
      const { w, h } = this
      if (!w || !h) return
      const t = (performance.now() - this.t0) / 1000
      const st = this.state

      g.fillStyle = '#000'
      g.fillRect(0, 0, w, h)

      const RAMP = ' \u00b7:\u2591\u2592\u2593\u2588'
      const size = 13
      g.font = `${size}px ui-monospace, "SF Mono", Menlo, Consolas, monospace`
      g.textBaseline = 'top'
      const cw = g.measureText('\u2588').width || size * 0.6
      const ch = size * 1.02
      const cols = Math.ceil(w / cw)
      const rows = Math.ceil(h / ch)

      const cx = w / 2, cy = h / 2
      const base = Math.min(w, h)
      const lock = st.coh.reduce((a, b) => a + Math.abs(b), 0) / 3

      // Sources converge as the ring locks: three interfering voices collapse
      // into one set of rings, the same thing the ear hears happen.
      const src = []
      for (let i = 0; i < 3; i++) {
        const ang = (i / 3) * Math.PI * 2 - Math.PI / 2 + t * 0.02
        const spread = base * 0.34 * (1 - 0.9 * lock)
        src.push([cx + Math.cos(ang) * spread, cy + Math.sin(ang) * spread])
      }
      // Spatial frequency per source follows its oscillator's pitch: the higher
      // the voice, the tighter its rings.
      const k = st.freq.map(f => {
        const n = (Math.max(40, Math.min(400, f || 75)) - 40) / 360
        return (0.055 + 0.085 * n) * (base / 540)
      })

      // 4051 + 4046 + 4040. On a grounded address the comparator sees nothing,
      // so the VCO has no target: it drifts off on its own arc until the lock
      // detector clocks the 4040 and the whole ring jumps to the next input.
      let vco = null
      if (st.vcoHz > 0) {
        const n = (Math.max(40, Math.min(400, st.vcoHz)) - 40) / 360
        const vk = (0.055 + 0.085 * n) * (base / 540)
        let vx, vy
        if (st.addr < 3) {
          vx = src[st.addr][0]; vy = src[st.addr][1]
        } else {
          const a = t * 0.23 + st.addr
          vx = cx + Math.cos(a) * base * 0.40
          vy = cy + Math.sin(a) * base * 0.40
        }
        vco = { x: vx, y: vy, k: vk, amp: st.locked ? 1.15 : 0.55 }
      }

      // Two passes so the field has depth: everything at low brightness, then
      // the top of the ramp again, brighter. Row-at-a-time, because one
      // fillText per character would be tens of thousands of calls a frame.
      const dim = []
      const hot = []
      for (let r = 0; r < rows; r++) {
        let a = '', b = ''
        const y = r * ch
        for (let q = 0; q < cols; q++) {
          const v = this.field(q * cw, y, t, st, src, k, vco)
          let n = Math.round((v * 0.5 + 0.5) * (RAMP.length - 1))
          if (n < 0) n = 0
          if (n > RAMP.length - 1) n = RAMP.length - 1
          const glyph = RAMP[n]
          if (n >= RAMP.length - 2) { a += ' '; b += glyph }
          else { a += glyph; b += ' ' }
        }
        dim.push(a); hot.push(b)
      }

      // The PLL reads as a fourth, tighter set of rings centred on whichever
      // source the mux has selected -- present only while it holds lock.
      g.fillStyle = 'rgba(190,190,190,0.42)'
      for (let r = 0; r < rows; r++) g.fillText(dim[r], 0, r * ch)
      g.fillStyle = `rgba(255,255,255,${(0.62 + 0.3 * lock).toFixed(3)})`
      for (let r = 0; r < rows; r++) g.fillText(hot[r], 0, r * ch)
    }
  }
}
</script>

<style scoped>
.field {
  position: fixed;
  inset: 0;
  background: #000;
  cursor: pointer;
  overflow: hidden;
}
/* CSS is the only thing that sizes the canvas. JS reads this back and matches
   the backing store to it. */
canvas {
  display: block;
  width: 100%;
  height: 100%;
  /* style.css caps every canvas at 340px (220px under its mobile query) for the
     dashboard chart. max-height beats height:100%, so without these the field
     is 340px tall on any screen and the rest of the page stays black. The
     scoped attribute selector outranks the bare `canvas` rule. */
  max-height: none;
  max-width: none;
}
.sound {
  position: absolute;
  top: 18px; right: 20px;
  background: none;
  border: 1px solid rgba(255, 255, 255, 0.22);
  /* Explicit: some platforms round native buttons by default. */
  border-radius: 0;
  -webkit-appearance: none;
  appearance: none;
  color: rgba(255, 255, 255, 0.55);
  font-family: inherit;
  font-size: 0.58rem;
  letter-spacing: 0.28em;
  padding: 7px 12px;
  cursor: pointer;
}
.sound:hover {
  color: rgba(255, 255, 255, 0.95);
  border-color: rgba(255, 255, 255, 0.55);
}
.err {
  position: absolute;
  top: 52px; right: 20px;
  color: rgba(255, 255, 255, 0.4);
  font-size: 0.55rem;
}
.back {
  position: absolute;
  left: 18px; bottom: 16px;
  color: rgba(255, 255, 255, 0.18);
  text-decoration: none;
  font-size: 0.8rem;
}
.back:hover { color: rgba(255, 255, 255, 0.5); }
</style>
