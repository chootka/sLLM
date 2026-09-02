<template>
  <div class="field" :class="{ object: isObject }" @click="tapField">
    <canvas ref="cv"></canvas>
    <!-- Two targets, and only two: one starts the sound, one opens the log.
         Sound and fullscreen are separate gestures on purpose: a sound button
         should not seize the display. Click the field for fullscreen -- but
         only on the web. The object is already fullscreen under kiosk, it has
         no pointer and no keyboard, and a visitor's stray tap must not be able
         to change what the display is doing. -->
    <button class="sound" @click.stop="toggleSound">
      {{ running ? 'SOUND OFF' : 'SOUND ON' }}
    </button>
    <button class="about" @click.stop="about = !about">
      {{ about ? 'CLOSE' : 'SOUND LOG' }}
    </button>
    <div v-if="about" class="panel" @click.stop>
      <p>You are listening to three oscillators tracking the voltage at
      electrodes a slime mould has grown over, rising and falling about every
      two minutes as its body pulses. They are wired in a circle, so each one
      leans on the next and can pull it off its own note. There is one ring per
      oscillator: bright where the ripples line up, dark where they cancel.</p>

      <p><b>The organism.</b> A slime mould grows in a covered dish. Four metal
      pins are set into the jelly it grows over. When it spreads far enough to
      touch a pin, a very faint electrical signal appears there, and it rises
      and falls roughly every two minutes. It has been doing this for days.</p>

      <p><b>What the organism does.</b> Its slow rhythm decides how hard they
      lean. Push hard and the three notes collapse together into one. Ease off
      and they slide apart and rub against each other, which you hear as a
      wobble. That collapsing and sliding apart, over and over, is the
      organism's two-minute rhythm. Nothing here is sped-up recordings of the
      organism or a sound effect chosen to suit it -- it is the circuit being
      pushed around by the measurements.</p>

      <p><b>Left and right.</b> The three notes come out of the left side. A
      fourth note on the right is a part of the circuit that tries to chase
      them and hold on.</p>

      <dl class="now">
        <dt>playing</dt><dd>{{ sourceLine }}</dd>
        <dt>pin 1</dt><dd>{{ chanLine(0) }}</dd>
        <dt>pin 2</dt><dd>{{ chanLine(1) }}</dd>
        <dt>pin 3</dt><dd>{{ chanLine(2) }}</dd>
      </dl>
    </div>
    <div v-if="err" class="err">{{ err }}</div>
    <!-- The way back to the dashboard, which the object does not have and
         must not offer: there is no API behind it there, so a tap in the
         corner would strand a visitor on a broken page with no route home. -->
    <router-link v-if="!isObject" to="/" class="back" @click.stop>&larr;</router-link>
  </div>
</template>

<script>
import axios from 'axios'

const POLL_MS = 10000
const SPAN_S = 300
const FREE_RUN = 0.12
const DEPTH = 0.62
const SCALE_MV = 2.0
const FLASH_MS = 1800

// The exhibition object ships the recording beside the page and has no API
// behind it. scripts/export_replay.py writes this shape: signal per second,
// gate as index runs, period per minute.
function expand(ch, n) {
  const gate = new Uint8Array(n)
  for (const r of ch.gate_runs || []) gate.fill(1, r[0], r[1])
  const out = new Array(n)
  for (let i = 0; i < n; i++) {
    out[i] = {
      gate: gate[i],
      signal: ch.signal[i] || 0,
      period: ch.period[Math.floor(i / 60)] || 0
    }
  }
  return out
}

export default {
  name: 'Drift',
  data() {
    return {
      running: false,
      err: '',
      about: false,
      // The bundled recording, when the page is running as the object.
      bundled: null,
      // Mirrors state.drives for the panel. state itself is deliberately not
      // reactive -- it is touched every animation frame.
      live: { drives: [FREE_RUN, FREE_RUN, FREE_RUN], gates: [0, 0, 0], period: [0, 0, 0] }
    }
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

    // Query speed applies to the bundled recording too, so one object can be
    // set to real time and another to a timelapse without a rebuild.
    pace() {
      if (this.replay) return this.replay.speed
      const v = Number((this.$route && this.$route.query || {}).speed)
      return Number.isFinite(v) ? Math.max(1, Math.min(240, v)) : 1
    },

    // Running as the sealed exhibition object rather than as the website.
    // The bundled recording is the thing that is actually true about the
    // object, so it decides, rather than a flag on the kiosk URL that can be
    // left off. `?kiosk=1` is for previewing that behaviour on a laptop.
    isObject() {
      const q = (this.$route && this.$route.query) || {}
      return !!this.bundled || String(q.kiosk) === '1'
    },

    sourceLine() {
      if (this.bundled) {
        const d = new Date(this.bundled.t0 * 1000)
        const hours = (this.bundled.n / 3600).toFixed(1)
        const when = d.toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' })
        return this.pace > 1
          ? `a recording from ${when} -- ${hours} hours timelapsed into `
            + `${(this.bundled.n / 60 / this.pace).toFixed(0)} minutes, on a loop`
          : `a recording from ${when} -- ${hours} hours, in real time, on a loop`
      }
      const r = this.replay
      if (!r) return 'the dish, live, the last five minutes'
      const d = new Date(r.from * 1000)
      const span = r.mins >= 120 ? `${(r.mins / 60).toFixed(1)} hours` : `${r.mins} minutes`
      const into = r.mins / r.speed
      const played = into >= 1 ? `${into.toFixed(0)} minutes` : `${(into * 60).toFixed(0)} seconds`
      return `a recording from ${d.toLocaleString()} -- ${span} timelapsed `
        + `into ${played}, on a loop`
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
      flash: [0, 0, 0],
      addr: 0, vcoHz: 0, locked: false
    }
    // Gate as of the previous step, per channel. null until the first sample:
    // a pin already connected when the page opens is a starting condition, not
    // an event, and must not flash.
    this.prevGates = [null, null, null]
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
    this.boot()
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

    // On the object this is deliberately inert -- see the template.
    tapField() {
      if (this.isObject) return
      return this.toggleFull()
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

    // An object with no rig behind it must not depend on an API answering.
    async boot() {
      if (await this.loadBundled()) return
      this.fetch()
      // A replay is a fixed window; refetching would only re-request the same
      // seconds.
      if (!this.replay) this._poll = setInterval(this.fetch, POLL_MS)
    },

    // Tried before the API. A server that answers every path with index.html
    // returns something here, so the shape is what decides, not the status.
    async loadBundled() {
      try {
        const { data } = await axios.get('replay.json')
        if (!data || !data.t0 || !Array.isArray(data.channels)) return false
        for (let c = 0; c < 3; c++) this.buffer[c] = expand(data.channels[c], data.n)
        this.bundled = data
        this.cursor = 0
        return true
      } catch (e) {
        return false
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
            return { gate: s.gate || 0, signal: s.signal || 0, period: s.period || 0 }
          })
        }
        // Live picks up near the newest sample; a replay starts at the top.
        this.cursor = r ? 0 : Math.max(0, this.buffer[0].length - POLL_MS / 1000)
      } catch (e) { /* keep free-running */ }
    },

    // Written for the panel, in the panel's terms: is this channel driving
    // anything, and how hard.
    chanLine(c) {
      if (this.live.gates[c] <= 0.5) return 'not yet connected'
      const push = Math.round((this.live.drives[c] - FREE_RUN) / DEPTH * 100)
      const p = this.live.period[c]
      const rhythm = p > 0 ? `, rhythm every ${(p / 60).toFixed(1)} min` : ''
      return `pushing at ${push}%${rhythm}`
    },

    advance() {
      const buf = this.buffer[0]
      if (!buf || !buf.length) return
      this.cursor += 0.05 * this.pace
      // Replays loop, so one can be left running in a room.
      const loops = this.replay || this.bundled
      if (this.cursor > buf.length - 1) this.cursor = loops ? 0 : buf.length - 1
      const i = Math.floor(this.cursor)
      const drives = []
      for (let c = 0; c < 3; c++) {
        const s = this.buffer[c][i] || { gate: 0, signal: 0 }
        drives.push(s.gate > 0.5
          ? FREE_RUN + DEPTH * Math.max(0, Math.min(1, s.signal / SCALE_MV + 0.5))
          : FREE_RUN)
        // The organism reaching a pin, once, as it happens. Replays loop, so a
        // loop replays the connection too.
        const was = this.prevGates[c]
        if (was !== null && was <= 0.5 && s.gate > 0.5) this.state.flash[c] = performance.now()
        this.prevGates[c] = s.gate
      }
      this.state.drives = drives
      if (this.node) this.node.port.postMessage({ drives })
      if (this.about) {
        this.live = {
          drives,
          gates: [0, 1, 2].map(c => (this.buffer[c][i] || {}).gate || 0),
          period: [0, 1, 2].map(c => (this.buffer[c][i] || {}).period || 0)
        }
      }
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

      // A pin that has just connected blooms yellow at its own source and
      // fades back, once. Most recent wins: two pins connecting inside
      // FLASH_MS is not a case worth another pass over the grid for.
      let flash = null
      for (let i = 0; i < 3; i++) {
        if (!st.flash[i]) continue
        const age = (performance.now() - st.flash[i]) / FLASH_MS
        if (age < 0 || age >= 1) continue
        if (!flash || st.flash[i] > st.flash[flash.i]) {
          flash = { i, env: Math.sin(Math.PI * age) }
        }
      }
      const fr = base * 0.45
      const fl = [[], [], []]

      // Two passes so the field has depth: everything at low brightness, then
      // the top of the ramp again, brighter. Row-at-a-time, because one
      // fillText per character would be tens of thousands of calls a frame.
      const dim = []
      const hot = []
      for (let r = 0; r < rows; r++) {
        let a = '', b = ''
        // Three distance bands, so the bloom falls off outward without needing
        // a fillText per character.
        let f0 = '', f1 = '', f2 = ''
        const y = r * ch
        for (let q = 0; q < cols; q++) {
          const v = this.field(q * cw, y, t, st, src, k, vco)
          let n = Math.round((v * 0.5 + 0.5) * (RAMP.length - 1))
          if (n < 0) n = 0
          if (n > RAMP.length - 1) n = RAMP.length - 1
          const glyph = RAMP[n]
          if (n >= RAMP.length - 2) { a += ' '; b += glyph }
          else { a += glyph; b += ' ' }
          if (flash) {
            const dx = q * cw - src[flash.i][0], dy = y - src[flash.i][1]
            const d = Math.sqrt(dx * dx + dy * dy) / fr
            if (d >= 1 || glyph === ' ') { f0 += ' '; f1 += ' '; f2 += ' ' }
            else if (d < 0.34) { f0 += glyph; f1 += ' '; f2 += ' ' }
            else if (d < 0.67) { f0 += ' '; f1 += glyph; f2 += ' ' }
            else { f0 += ' '; f1 += ' '; f2 += glyph }
          }
        }
        dim.push(a); hot.push(b)
        if (flash) { fl[0].push(f0); fl[1].push(f1); fl[2].push(f2) }
      }

      // The PLL reads as a fourth, tighter set of rings centred on whichever
      // source the mux has selected -- present only while it holds lock.
      g.fillStyle = 'rgba(190,190,190,0.42)'
      for (let r = 0; r < rows; r++) g.fillText(dim[r], 0, r * ch)
      g.fillStyle = `rgba(255,255,255,${(0.62 + 0.3 * lock).toFixed(3)})`
      for (let r = 0; r < rows; r++) g.fillText(hot[r], 0, r * ch)
      if (flash) {
        const band = [0.95, 0.6, 0.28]
        for (let b = 0; b < 3; b++) {
          g.fillStyle = `rgba(255,206,64,${(flash.env * band[b]).toFixed(3)})`
          for (let r = 0; r < rows; r++) g.fillText(fl[b][r], 0, r * ch)
        }
      }
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
  /* Touch panel hardening. Without these a finger gets double-tap zoom, a
     text-selection drag over the field, and a long-press callout menu, none
     of which a sealed object can recover from. */
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
  -webkit-touch-callout: none;
  -webkit-user-select: none;
  user-select: none;
}
/* No mouse is attached to the object, so an arrow parked over the field is
   just a blemish that never moves again. */
.field.object,
.field.object button,
.field.object a { cursor: none; }
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
/* One rule for both, so the two targets cannot drift apart in size. */
.sound, .about {
  position: absolute;
  top: 18px;
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
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
  -webkit-user-select: none;
  user-select: none;
}
.sound { right: 20px; }
.about { left: 20px; }
.sound:hover, .about:hover {
  color: rgba(255, 255, 255, 0.95);
  border-color: rgba(255, 255, 255, 0.55);
}
/* :hover never fires on glass, so it is the only feedback a finger gets that
   the tap landed. Held only while the finger is down. */
.sound:active, .about:active {
  color: #000;
  background: rgba(255, 255, 255, 0.9);
  border-color: rgba(255, 255, 255, 0.9);
}
.panel {
  position: absolute;
  top: 52px; left: 20px;
  width: min(430px, calc(100vw - 40px));
  max-height: calc(100vh - 96px);
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.86);
  border: 1px solid rgba(255, 255, 255, 0.22);
  padding: 16px 18px;
  color: rgba(255, 255, 255, 0.62);
  font-size: 0.62rem;
  line-height: 1.75;
  cursor: default;
}
.panel p { margin: 0 0 12px; }
.panel b { color: rgba(255, 255, 255, 0.9); font-weight: normal; }
.panel .now {
  margin: 0;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.14);
  display: grid;
  grid-template-columns: 5.5em 1fr;
  gap: 2px 10px;
}
.panel dt { color: rgba(255, 255, 255, 0.38); letter-spacing: 0.12em; }
.panel dd { margin: 0; }
/* A finger, not a cursor -- the touch panel on the object, and phones. Keyed
   to the input device rather than to object mode, because the sizes below are
   wrong for a mouse and right for a finger wherever the page is running.
   ~56px is the smallest target that is reliably hit first time; the type goes
   up with it because 0.58rem is unreadable at gallery viewing distance. */
@media (pointer: coarse) {
  .sound, .about {
    top: 24px;
    min-height: 56px;
    min-width: 132px;
    padding: 18px 26px;
    font-size: 0.72rem;
    /* Brighter, because on the object these are the only two things a visitor
       is meant to find. */
    color: rgba(255, 255, 255, 0.72);
    border-color: rgba(255, 255, 255, 0.34);
  }
  .sound { right: 24px; }
  .about { left: 24px; }
  .panel {
    top: 96px;
    left: 24px;
    width: min(560px, calc(100vw - 48px));
    max-height: calc(100vh - 140px);
    padding: 22px 24px;
    font-size: 0.78rem;
    line-height: 1.85;
    -webkit-overflow-scrolling: touch;
  }
  .panel .now { grid-template-columns: 6.5em 1fr; }
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
