<template>
  <div class="viz-root">
    <div class="viz-stage">
      <!-- Markers are positioned in percentages of the canvas, so they have to
           live in a box that is exactly the canvas, not the stage. -->
      <div class="viz-field">
        <canvas ref="canvas"></canvas>

        <!-- Electrode identity is carried by position and label. Brightness in
             this view means one thing only -- whether a point is carrying
             signal right now -- and tinting territories by channel would make
             it mean two. -->
        <div
          v-for="probe in probes"
          :key="probe.ch"
          class="viz-probe"
          :style="{ left: probe.left, top: probe.top }"
        >
          <span class="viz-probe-mark" :class="{ 'is-live': probe.bursting }"></span>
          <span class="viz-probe-label">ch{{ probe.ch }}</span>
        </div>
      </div>

      <p v-if="error" class="viz-note viz-note-error">{{ error }}</p>
      <p v-else-if="provenance" class="viz-note">{{ provenance }}</p>
    </div>

    <div class="viz-readout">
      <div v-for="channel in readout" :key="channel.ch" class="viz-channel">
        <span class="viz-channel-name">ch{{ channel.ch }}</span>
        <span class="viz-bar"><span class="viz-bar-fill" :style="{ width: channel.width }"></span></span>
        <span class="viz-channel-value">{{ channel.envelope }}</span>
        <span class="viz-channel-unit">mV</span>
        <span class="viz-channel-period">{{ channel.period }}</span>
      </div>

      <div class="viz-speed">
        <button
          v-for="option in speeds"
          :key="option"
          :class="{ 'is-on': option === speed }"
          @click="speed = option"
        >{{ option }}&times;</button>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
import { buildField, sampleDots } from '../viz/skeletonGraph'
import { createSynthField } from '../viz/synthField'

const INSET = 0.9        // keeps the body off the edge of the stage
const SPACING = 0.016    // dish units between dots along a tube

// The travelling signal is a head plus three dots of tail, and these are the
// only brightnesses it can take. Discrete on purpose: the head jumps from dot
// to dot rather than sliding, which is what makes it read as something moving
// through a network instead of a gradient sweeping across a picture.
const TRAIL = [1, 0.5, 0.26, 0.12]

// Resting dots. Dim enough to sit back, bright enough that the morphology is
// legible when every channel is quiet -- which is most of the time.
const REST_TUBE = 0.17
const REST_OUTLINE = 0.09

export default {
  name: 'SlimeViz',
  props: {
    apiUrl: { type: String, default: '' },
    // How far signal carries from its electrode, as a fraction of the longest
    // path in that territory. Lower is a more conservative picture.
    falloff: { type: Number, default: 0.5 },
  },
  data() {
    return {
      error: null,
      provenance: '',
      speed: 10,
      speeds: [1, 10, 60],
      probes: [],
      readout: [],
    }
  },
  async mounted() {
    this.ctx = this.$refs.canvas?.getContext('2d')
    if (!this.ctx) {
      this.error = 'canvas is not available in this browser'
      return
    }
    await this.loadSkeleton()
    this.synth = createSynthField()
    this.last = 0
    this.frame = requestAnimationFrame(this.draw)
    window.addEventListener('resize', this.resize)
  },
  beforeUnmount() {
    cancelAnimationFrame(this.frame)
    window.removeEventListener('resize', this.resize)
  },
  methods: {
    async loadSkeleton() {
      try {
        const { data } = await axios.get(`${this.apiUrl}/api/slime/skeleton`)
        this.field = buildField(data, 3)
        this.dots = sampleDots(this.field, SPACING)
        this.probes = this.field.electrodes.map((point, ch) => ({
          ch,
          bursting: false,
          left: `${50 + point[0] * INSET * 50}%`,
          top: `${50 + point[1] * INSET * 50}%`,
        }))
        // Say plainly what is real and what is standing in. Three separate
        // claims, because they will stop being false at three different times.
        const shape = this.field.placeholder
          ? 'placeholder geometry' : 'geometry from the dish'
        const sites = this.field.measured
          ? 'recorded electrode sites' : 'electrode sites inferred'
        this.provenance = `${shape} · ${sites} · synthetic signal`
      } catch (exc) {
        this.error = exc.response?.data?.error || 'no skeleton available'
      }
    },

    resize() {
      const canvas = this.$refs.canvas
      if (!canvas || !canvas.clientWidth) return
      const ratio = Math.min(window.devicePixelRatio || 1, 2)
      canvas.width = Math.round(canvas.clientWidth * ratio)
      canvas.height = Math.round(canvas.clientHeight * ratio)
    },

    // One traverse of the territory per half cycle, reversing at each turn.
    // Not decoration: shuttle streaming physically reverses on this timescale,
    // so the signal running out and coming back is the organism's own motion.
    wavefront(phase, reach) {
      const outward = phase < Math.PI
      const along = outward ? phase / Math.PI : 1 - (phase - Math.PI) / Math.PI
      return { at: along * reach, direction: outward ? 1 : -1 }
    },

    draw(now) {
      this.frame = requestAnimationFrame(this.draw)
      const canvas = this.$refs.canvas
      const ctx = this.ctx
      if (!ctx || !this.field || !canvas) return

      const ratio = Math.min(window.devicePixelRatio || 1, 2)
      if (canvas.clientWidth &&
          canvas.width !== Math.round(canvas.clientWidth * ratio)) this.resize()

      const seconds = this.last ? Math.min(0.25, (now - this.last) / 1000) : 0
      this.last = now
      const frame = this.synth.step(seconds * this.speed)

      const size = canvas.width
      ctx.fillStyle = '#000'
      ctx.fillRect(0, 0, size, canvas.height)

      const half = size / 2
      const scale = half * INSET
      const px = (v) => half + v * scale
      const reaches = this.field.reachByOwner

      // Square root rather than the raw ratio. Absolute scaling is the honest
      // choice -- a quiet channel should look quiet -- but ch1 runs at a fifth
      // of ch2 because it was recoated, and on a linear ramp it would sit at
      // 12% and read as broken. The root keeps the ranking and still shows it.
      const activity = frame.channels.map(
        (c) => Math.sqrt(Math.min(1, c.envelope / this.synth.ceiling)))
      // Each channel sweeps its own territory, so all three finish a traverse
      // in the same cycle regardless of how much body they own.
      const fronts = frame.channels.map((c, ch) => this.wavefront(c.phase, reaches[ch]))

      const dotScale = size / 900
      for (const dot of this.dots) {
        const outline = dot.kind === 'outline'
        let level = outline ? REST_OUTLINE : REST_TUBE

        if (!outline && dot.owner >= 0) {
          const front = fronts[dot.owner]
          // Which dot of the tail this is: 0 is the head, then one step per
          // spacing behind it, in whichever direction the front is moving.
          const step = Math.round(((front.at - dot.d) * front.direction) / SPACING)
          if (step >= 0 && step < TRAIL.length) {
            // Confidence decays with distance from the electrode that owns this
            // dot, so the seam between two territories -- far from both -- stays
            // dim on its own, and no boundary value has to be invented.
            const confidence = Math.exp(-dot.d / (reaches[dot.owner] * this.falloff))
            const lit = TRAIL[step] * activity[dot.owner] * confidence
            level = level + lit * (1 - level)
          }
        }

        const radius = outline
          ? 0.9 * dotScale
          : (1.1 + 1.9 * dot.girth) * dotScale
        const shade = Math.round(level * 255)
        ctx.fillStyle = `rgb(${shade},${shade},${shade})`
        ctx.beginPath()
        ctx.arc(px(dot.x), px(dot.y), radius, 0, Math.PI * 2)
        ctx.fill()
      }

      // Electrodes last so they sit on top of their own territory. A hollow
      // ring, one hairline wide -- the same weight as every rule on the page.
      ctx.lineWidth = Math.max(1, dotScale)
      for (let ch = 0; ch < this.field.electrodes.length; ch++) {
        const [x, y] = this.field.electrodes[ch]
        const shade = Math.round((0.45 + 0.55 * activity[ch]) * 255)
        ctx.strokeStyle = `rgb(${shade},${shade},${shade})`
        ctx.beginPath()
        ctx.arc(px(x), px(y), 6 * dotScale, 0, Math.PI * 2)
        ctx.stroke()
      }

      this.publish(frame, now)
    },

    publish(frame, now) {
      // Wall-clock, not simulated seconds: throttling on frame.t meant that at
      // 60x the gap was always exceeded and the readout retyped every frame.
      if (this.published && now - this.published < 250) return
      this.published = now
      this.readout = frame.channels.map((channel) => ({
        ch: channel.ch,
        envelope: channel.envelope.toFixed(2),
        width: `${Math.min(100, (channel.envelope / this.synth.ceiling) * 100).toFixed(1)}%`,
        period: channel.bursting ? `${channel.period.toFixed(0)} s` : 'quiet',
      }))
      for (const probe of this.probes) {
        probe.bursting = frame.channels[probe.ch]?.bursting || false
      }
    },
  },
}
</script>

<style scoped>
/* Full bleed, flat, no depth. This route is the organism and nothing else --
   no panel chrome, no headings, nothing rounded, nothing that glows. */
.viz-root {
    position: fixed;
    inset: 0;
    background: var(--paper);
    display: flex;
    flex-direction: column;
}

.viz-stage {
    position: relative;
    flex: 1;
    min-height: 0;
    display: flex;
    align-items: center;
    justify-content: center;
}

.viz-field {
    position: relative;
    aspect-ratio: 1 / 1;
    max-width: 100%;
    max-height: 100%;
    width: 100%;
}

.viz-field canvas {
    width: 100%;
    height: 100%;
    display: block;
}

.viz-probe {
    position: absolute;
    transform: translate(-50%, -50%);
    display: flex;
    align-items: center;
    gap: 16px;
    pointer-events: none;
}

/* Spacer that pushes the label clear of the ring the canvas draws. The ring
   itself is on the canvas so it scales with the dots rather than against them. */
.viz-probe-mark {
    width: 12px;
    flex: none;
}

.viz-probe-label {
    font-family: var(--mono);
    font-size: 0.62rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--ink-ghost);
    transition: color 300ms linear;
}

/* The label brightens while that channel is oscillating -- the same fact the
   dots are showing, repeated at the name, so which electrode is active
   survives a glance that never leaves the label. */
.viz-probe-mark.is-live + .viz-probe-label { color: var(--ink); }

.viz-note {
    position: absolute;
    left: 18px;
    bottom: 14px;
    margin: 0;
    font-family: var(--mono);
    font-size: 0.62rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--ink-ghost);
}

.viz-note-error { color: var(--state-danger); }

/* A strip, not a panel: three envelopes and a speed control, sized so it never
   competes with the stage above it. */
.viz-readout {
    flex: none;
    display: flex;
    align-items: center;
    gap: 28px;
    padding: 12px 18px;
    border-top: 1px solid var(--rule);
    font-family: var(--mono);
    font-size: 0.68rem;
}

.viz-channel { display: flex; align-items: center; gap: 8px; }

.viz-channel-name {
    color: var(--ink-faint);
    letter-spacing: 0.16em;
    text-transform: uppercase;
}

/* Envelope as a bar as well as a number: the bar is what you read across the
   room, the number is what you read when you care about the value. */
.viz-bar {
    width: 74px;
    height: 3px;
    background: rgba(255, 255, 255, 0.12);
    display: block;
}

.viz-bar-fill {
    display: block;
    height: 100%;
    background: var(--ink);
    transition: width 220ms linear;
}

.viz-channel-value { color: var(--ink); min-width: 34px; text-align: right; }
.viz-channel-unit { color: var(--ink-ghost); }
.viz-channel-period { color: var(--ink-faint); min-width: 46px; }

.viz-speed { margin-left: auto; display: flex; gap: 1px; }

/* Time compression. At 1x a cycle takes 86 to 150 seconds, which is the truth
   and unwatchable while tuning -- so the multiplier is a control, and it says
   on screen which one is running. */
.viz-speed button {
    font-family: var(--mono);
    font-size: 0.62rem;
    letter-spacing: 0.1em;
    padding: 4px 10px;
    background: transparent;
    color: var(--ink-faint);
    border: 1px solid var(--rule);
    cursor: pointer;
}

.viz-speed button.is-on {
    color: var(--paper);
    background: var(--ink);
    border-color: var(--ink);
}

@media (max-width: 620px) {
    .viz-readout { flex-wrap: wrap; gap: 12px 18px; }
    .viz-bar { width: 48px; }
}
</style>
