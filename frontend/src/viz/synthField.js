// Synthetic electrode feed, shaped like the real one, so the renderer can be
// tuned without waiting on the organism. Not a sine wave: every constant below
// was measured off data/readings/test/electrodes_20260820.csv, the first clean
// half-hour after the electrodes were rewired.
//
//   burst amplitude   ch2 1.27 mV  >  ch0 0.64 mV  >  ch1 0.22 mV
//   noise floor       ch2 0.53 mV     ch0 0.19 mV     ch1 0.11 mV
//   periods seen      86 s and 150 s, one per burst, not both at once
//   structure         ~10 min of oscillation, ~10 min of near-flat, repeating
//   drift             +2.0 to +3.6 mV over 30 min, all channels together
//
// ch1 reads low because it was recoated a week ago, not because that strand is
// quiet. Keeping the ranking keeps the visual weighting honest.
//
// NOTE 2026-08-20: the periods above predate the dominant_period fix in
// llm/filters/reducer.py, which finds ~50 s on the same file and shows the
// ~150 s bump in unconnected-electrode data too. Re-measure before trusting.
//
// The emitted frame is the contract with the future server-side feed:
//
//   { t, channels: [ { ch, mv, envelope, phase, polarity, period, bursting } ] }
//
//   mv        raw millivolts, drift included -- for the numeric readout only
//   envelope  band-passed amplitude in mV; this is what brightness reads
//   phase     radians, 0..2pi, position within the current cycle
//   polarity  +1 or -1, the sign of the band-passed signal
//   period    seconds, the cycle length currently in play
//   bursting  whether this channel is in a burst or a quiet stretch

const CHANNELS = [
  { ch: 0, baseline: 34.2, amp: 0.64, noise: 0.19, drift: 2.0 },
  { ch: 1, baseline: 30.3, amp: 0.22, noise: 0.11, drift: 2.0 },
  { ch: 2, baseline: 32.3, amp: 1.27, noise: 0.53, drift: 3.6 },
]

// Both periods the real half-hour showed. A burst picks one and stays near it;
// the next burst picks again. Nothing in the record drifts continuously from
// one to the other, so neither does this.
const PERIODS = [86, 150]

const BURST_CYCLES = [8, 20]        // how long a burst runs, in cycles
const QUIET_SECONDS = [300, 900]    // the flat stretch between bursts
const RAMP_CYCLES = 2               // raised-cosine fade in and out of a burst

const pick = (lo, hi) => lo + Math.random() * (hi - lo)

// Gaussian from two uniforms. The noise floor is measured as a standard
// deviation, so it has to be drawn as one -- uniform noise of the same width
// looks visibly wrong at the tube core, too even and too bounded.
function gaussian() {
  let u = 0
  while (u === 0) u = Math.random()
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * Math.random())
}

class ChannelSynth {
  constructor(spec) {
    this.spec = spec
    this.phase = Math.random() * 2 * Math.PI
    this.elapsed = 0
    // Start mid-burst rather than in a quiet stretch: opening the page on ten
    // minutes of nothing reads as a broken feed, not as a resting organism.
    this.startBurst()
    this.elapsed = pick(0, this.duration * 0.5)
  }

  startBurst() {
    this.bursting = true
    this.period = PERIODS[Math.floor(Math.random() * PERIODS.length)]
    this.period *= pick(0.94, 1.06)
    this.cycles = pick(...BURST_CYCLES)
    this.duration = this.cycles * this.period
    this.elapsed = 0
    // Each burst gets its own strength. The measured amplitudes are a burst
    // average, so bursts have to vary around them or the record is flatter
    // than the organism was.
    this.strength = pick(0.55, 1.45)
  }

  startQuiet() {
    this.bursting = false
    this.duration = pick(...QUIET_SECONDS)
    this.elapsed = 0
  }

  // Raised cosine over the first and last RAMP_CYCLES. A burst that starts at
  // full amplitude on cycle one looks switched on; the real ones swell.
  shape() {
    if (!this.bursting) return 0
    const ramp = RAMP_CYCLES * this.period
    const inFade = Math.min(1, this.elapsed / ramp)
    const outFade = Math.min(1, (this.duration - this.elapsed) / ramp)
    const edge = Math.min(inFade, outFade)
    return 0.5 - 0.5 * Math.cos(Math.PI * Math.max(0, Math.min(1, edge)))
  }

  advance(dt, totalElapsed) {
    this.elapsed += dt
    if (this.elapsed >= this.duration) {
      this.bursting ? this.startQuiet() : this.startBurst()
    }
    if (this.bursting) {
      this.phase = (this.phase + (2 * Math.PI * dt) / this.period) % (2 * Math.PI)
    }

    const { spec } = this
    const envelope = spec.amp * this.strength * this.shape()
    const oscillation = envelope * Math.sin(this.phase)
    // Drift is quoted per 30 min and is shared across channels in the record --
    // it is the electrodes settling, not the organism, which is exactly why the
    // renderer reads `envelope` and never `mv`.
    const drift = (spec.drift * totalElapsed) / 1800
    const noise = gaussian() * spec.noise

    return {
      ch: spec.ch,
      mv: spec.baseline + drift + oscillation + noise,
      envelope,
      phase: this.phase,
      polarity: Math.sin(this.phase) >= 0 ? 1 : -1,
      period: this.period,
      bursting: this.bursting,
    }
  }
}

export function createSynthField() {
  const channels = CHANNELS.map((spec) => new ChannelSynth(spec))
  let elapsed = 0
  return {
    // dt is simulated seconds, so the caller owns the time compression: pass
    // real seconds for 1x, or a multiple of them to run the organism fast
    // while tuning. Nothing downstream knows the difference.
    step(dt) {
      elapsed += dt
      return {
        t: elapsed,
        channels: channels.map((channel) => channel.advance(dt, elapsed)),
      }
    },
    // The renderer scales brightness against this rather than against whatever
    // the last few seconds happened to contain, so a quiet channel stays dark
    // instead of being normalised back up to full.
    ceiling: Math.max(...CHANNELS.map((c) => c.amp)) * 1.45,
  }
}
