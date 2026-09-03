// Three 40106 relaxation oscillators in a vactrol-coupled ring, osc1->2->3->1.
//
// Models the circuit rather than approximating its output: each voice is an RC
// integrator against a Schmitt trigger, and coupling is an LDR injecting
// current from one oscillator's output into the next one's timing capacitor.
// An OscillatorNode would give the pitch and none of the character -- the ramp
// shape and the threshold crossings are the sound.
//
// Board values, osc1 4.7k+100k, osc2/osc3 100k+100k, 47n throughout.

// CD40106 at 9 V: Vt+ typ 5.9 V, Vt- typ 2.9 V. Using the datasheet hysteresis
// rather than a guess -- the threshold gap sets the period, so inventing it
// puts every voice at the wrong pitch.
const VT_HI = 0.66        // Schmitt upper threshold, fraction of VDD
const VT_LO = 0.32        // lower
const R_DARK = 10e6       // LDR resistance unlit
const R_LIT = 5e3         // fully lit

// Board 2. 4046 VCO: R1 100k on pin 11, C1 1n across 6/7. The part's own
// relation is f_max ~ 1/(R1*(C1+32pF)), and with no R2 the low end runs to
// zero, so the VCO range covers the bank's 75-260 Hz comfortably.
const PLL_R1 = 100e3
// The board has C1 = 1n, which puts the VCO centre near 4.8 kHz against a bank
// running 75-260 Hz -- roughly 30x above it, and out of any comparator's reach.
// 33n centres it at ~150 Hz, inside the bank. Change on the board, or change
// here to 1e-9 to hear why it will not lock as built.
const PLL_C1 = 33e-9
const PLL_FMAX = 1 / (PLL_R1 * (PLL_C1 + 32e-12))
const LOOP_TAU = 10e3 * 100e-9    // loop filter, 10k + 100n
const LOCK_TAU = 1e6 * 1e-6       // lock detect, 1M + 1uF
// The 10k/10n stage after the passive mixer -- on the board's plan, not yet
// built. A square wave carries every odd harmonic with no rolloff, so the
// harshness is the waveform, not the pitch; this is what tames it.
const OUT_TAU = 10e3 * 10e-9
// 4040 #2, the feedback divider between VCO OUT and the comparator.
//
// 1 is FB jumpered straight from the VCO, which is the schematic's setting for
// audio-rate references, and it is what the mux mostly carries. /4096 is the
// other case on the drawing: it would let the VCO phase-lock to the organism's
// own ~0.011 Hz rhythm on Y5.
//
// Measured, and the reason this is 1: at /16 the loop parks on SLIME 69-93% of
// the time and the VCO sits at 0.3 Hz, which is silence on the right channel.
// At /1 it stays audible throughout and, on run 6, chases 51-144 Hz.
const PLL_FBDIV = 1
// Lock detect: a spare 40106 wired as a relaxation oscillator, 1M from its own
// output back to its input, 1u to ground. Free-running it clocks the 4040 about
// every 1.4 s. 4046 pin 1 (PCP_OUT, the phase pulses) clamps that input while
// the loop is locked, which stops it. So the mux walks only while the PLL is
// failing to hold, and parks when it finds something it can keep.
//
// The gating is the mechanism, not the node. A plain RC on pin 1 never clocks:
// averaging any of these nodes gives a DC once locked. It has to be an
// oscillator that lock switches off.
const LOCKOSC_TAU = 1e6 * 1e-6

// Everything below is constant for the life of the processor, and every one of
// them used to be recomputed inside the per-sample loop. At 48 kHz that is a
// few hundred thousand transcendental calls a second in the audio thread.
const DT = 1 / sampleRate
// A long tail. 5 ms/50 ms passed every wobble in the data straight through to
// pitch, which is what made this restless rather than hypnotic. Real LDR
// vactrols decay over hundreds of milliseconds, so this is closer to the part
// as well as calmer: the ring drifts between states instead of twitching.
const A_UP = 1 - Math.exp(-DT / 0.05)      // vactrol light rising
const A_DN = 1 - Math.exp(-DT / 0.60)      // and falling, slowly
const K_COH = 1 - Math.exp(-DT / 0.30)
const K_LOOP = 1 - Math.exp(-DT / LOOP_TAU)
const K_LOCK = 1 - Math.exp(-DT / LOCKOSC_TAU)
const K_OUT = 1 - Math.exp(-DT / OUT_TAU)

// The piece sits back while nothing is connected and comes forward when the
// organism reaches an electrode. With no contact there is no bio signal, only
// the oscillators idling -- that is a bed, not a foreground, and hours of it
// at full level is wearing. REST is what fraction of full level the bed sits
// at; the swell is keyed to the vactrol drive, so it follows whatever the data
// actually does rather than any assumption about which pin connects when.
// KNEE is the drive at which the piece is fully forward. Both are set by ear.
// Most of the contrast is tone, not level. A square wave at full brightness
// for hours is what makes a listener dizzy, so with nothing connected the bank
// is rolled off to a rumble -- the harmonics that do the damage are gone, the
// body of it stays. Contact opens the filter and the piece steps forward.
// Level still moves, but far less than it did: the bed is not meant to be
// quiet, it is meant to be behind something.
const REST_LEVEL = 0.60
// Filtering a square down to its first harmonics throws away most of its
// energy, so the bed reads far quieter than its level says. That is a loss to
// compensate, not a dynamic. Makeup rises as the filter closes, so soft stays
// soft in character without becoming inaudible.
const BED_MAKEUP = 1.9
// A low-passed square is a muffled square: narrowband and dull. Thunder is the
// opposite -- broadband and smooth -- so no cutoff setting gets there from a
// filtered square. The bed gets its body from brown noise instead, which has
// energy everywhere but no edges and no pitch, and the oscillators sit under it
// rather than being the whole of it. The noise breathes with the bank, so the
// rumble still follows what the organism is doing.
// Off. Brown noise is road noise -- that is literally what a car on a freeway
// sounds like -- and it fought the pad the whole way: scrapy, then noisy, then
// freeway. The bed is the three detuned triangles, nothing else. Left wired up
// because a trace of it may sit well under a fuller pad later.
const NOISE_LEVEL = 0.0                 // brown noise in the bed
const TONE_IN_BED = 1.0                 // how much of the pad stays in the bed
const BED_DRIVE = 1.15                  // saturation: thickness, not brightness
// Two poles at ~90 Hz. The previous version used coefficients that did not sum
// to one, giving 10x gain into the saturator -- that was the scrape -- and a
// second stage at 2.7 kHz, which is hiss rather than rumble.
const NZ_K = 0.012                      // ~90 Hz per pole
const NZ_GAIN = 14                      // makeup: two poles leave very little
// The comparator output is a hard square: instantaneous edges, which alias at
// 48 kHz, and aliased partials fold down BELOW the cutoff where no filter can
// reach them. That inharmonic metallic content is the tin-across-concrete, and
// it is why filtering only ever made this duller without making it smoother.
// The capacitor node is the same oscillator without the edges -- it ramps
// between the two Schmitt thresholds, which is a triangle and has almost no
// high harmonics to alias. That is the pad. Some square comes back as contact
// arrives, because the foreground wants the bite.
const VT_MID = (VT_HI + VT_LO) / 2
const VT_SPAN = VT_HI - VT_LO
const TRI_FWD = 0.35                    // triangle fraction fully foregrounded
const FC_BED = 420                      // Hz, cutoff with nothing connected
// No raw signal in the bed. A square's edges are instantaneous and full
// bandwidth, so even 15% of it dry reads as crunch -- an 8-bit engine idling.
// The dry blend was there to stop the bed sounding muffled when the bank sat
// at 200 Hz and the cutoff was below its fundamental; with the bank two octaves
// down the fundamental is well inside the passband and the blend only adds
// grit. 220 Hz against a 50 Hz fundamental leaves the first few harmonics and
// nothing sharp.
const BED_DRY = 0.0
// Filtering could never fix the bed, because what makes it painful is not the
// harmonics but the three fundamentals themselves. At 200/204/209 Hz they beat
// at 4-9 Hz, which is squarely in the range the ear reads as roughness, and it
// never stops. Two octaves down puts them at 50/51/52 Hz beating at 1-2 Hz: a
// slow swell rather than a buzz, and genuinely a rumble instead of a filtered
// square. Contact brings the bank back up to pitch. On the board this is the
// timing caps -- 47n against something four times larger.
const BED_DROP = 4                      // x capacitance at rest: two octaves
const FC_OPEN = 9000                    // Hz, cutoff fully foregrounded
// The drive does not rest at zero: with nothing connected the vactrols sit at
// the free-run floor, and the contact signal is what rises above it. Keying the
// swell off the raw drive meant "rest" computed a third of the way open -- the
// filter at ~590 Hz instead of 150 and the bank only 1.3 octaves down, which is
// why the bed stayed thin and gritty however the numbers were tuned. Same
// normalisation the page uses to report how hard a pin is pushing.
const FREE_RUN = 0.12
const DEPTH = 0.62
const SWELL_KNEE = 0.35                 // fraction of full push to be forward
// Fast up, slow down. Six seconds in both directions smeared the moment of
// contact across six seconds of audio while the visual bloom was instant,
// which reads as the sound lagging the picture even when they are locked. The
// piece should arrive with the bloom and leave slowly.
const SWELL_UP = 1.5                    // seconds to come forward
const SWELL_DN = 18.0                   // seconds to fall back to the bed
// Linear below the knee, so the dynamics that survive to here are untouched;
// only the peaks bend. A tanh across the whole range was tried on this signal
// before and flattened everything, because a square is already at full scale
// most of the time.
const KNEE = 0.80
function soft (x) {
  if (x > KNEE) return KNEE + (1 - KNEE) * Math.tanh((x - KNEE) / (1 - KNEE))
  if (x < -KNEE) return -KNEE - (1 - KNEE) * Math.tanh((-x - KNEE) / (1 - KNEE))
  return x
}
const K_SWELL_UP = 1 - Math.exp(-DT / SWELL_UP)
const K_SWELL_DN = 1 - Math.exp(-DT / SWELL_DN)

// LDR conductance against light, interpolated in log resistance. This was a
// Math.pow per vactrol per sample. The curve is exponential in lum, so a
// linear index over 0..1 gives a constant ratio per step -- 0.74% at 1024
// entries -- and interpolating between entries keeps it smooth enough not to
// zipper as the light moves.
const G_N = 1024
const G_LUT = new Float64Array(G_N + 1)
for (let i = 0; i <= G_N; i++) {
  G_LUT[i] = 1 / (R_DARK * Math.pow(R_LIT / R_DARK, i / G_N))
}
function conductance(lum) {
  const x = lum * G_N
  if (x <= 0) return G_LUT[0]
  if (x >= G_N) return G_LUT[G_N]
  const i = x | 0
  const f = x - i
  return G_LUT[i] + (G_LUT[i + 1] - G_LUT[i]) * f
}

class RingProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    const C = 47e-9
    // out is the inverter output: HIGH charges the cap, and crossing the upper
    // threshold flips it. Staggered start so they do not begin in lockstep.
    this.osc = [
      // osc2 and osc3 are both 100k+100k on the board, but real parts are not
      // identical -- 5% resistors and 10% caps. Modelled dead equal they land
      // on the same pitch and sum into one thick voice instead of beating
      // against each other, which is most of what made the mix feel like a
      // single block. A few percent apart is both truer and audibly better.
      { v: 0.10, out: 1, r: 104.7e3, c: C },
      { v: 0.45, out: 1, r: 197e3, c: C },
      { v: 0.80, out: 0, r: 206e3, c: C }
    ]
    // Vactrols A, B, C -- each couples osc[from] into osc[to], the ring as
    // jumpered on the board.
    this.vac = [
      { from: 0, to: 1, lum: 0, drive: 0 },
      { from: 1, to: 2, lum: 0, drive: 0 },
      { from: 2, to: 0, lum: 0, drive: 0 }
    ]
    this.gain = 0.42
    this.swell = REST_LEVEL   // master level, follows contact
    // Two poles per channel for the screen. Cascaded one-poles: gentle, no
    // resonance, nothing that rings on a square edge.
    this.sc1 = 0; this.sc2 = 0
    this.sd1 = 0; this.sd2 = 0
    this.nz = 0               // brown noise state
    this.nzf = 0
    this.env = 0              // slow envelope of the bank, breathes the noise
    this.dc = 0
    this.lp = 0               // 10k/10n output stage
    this.lp2 = 0
    // Off by default. The square wave is the sound; this stage exists only
    // because the board plans one, and it is not used.
    this.tone = 0
    this.capScale = 1         // multiplies every timing cap: 2 = an octave down
    // Passive mixer weights, one per voice. On the board these ARE the mixer
    // resistors: 100k each as built, so equal. 220k on a voice roughly halves
    // it. Kept as ratios so the numbers mean the same thing at the bench.
    // osc1 sits an octave above the pair, so it never beats with them -- a
    // lone square has constant RMS whatever its pitch does, and level movement
    // comes only from voices interfering. At equal weight it lays a fixed slab
    // under everything the contraction is doing. Measured against real run-6
    // drives, 0.45 maximises the level range (5.8 -> 6.8 dB) while keeping it
    // audible. On the board that is a 220k mixer resistor instead of 100k.
    this.mix = [0.45, 1, 1]
    // The VCO is a square at constant amplitude that only ever tracks pitch --
    // it takes no part in the fusing, so it reads as a fixed slab under the
    // bank's movement. Its own level, independent of the mixer.
    this.vcoLevel = 0.18
    this.running = true

    // Reported to the main thread for the visual. The oscillators run at
    // 75-260 Hz, far too fast to watch, so nothing raw goes out. What is
    // visible at human rate is the *beat* between voices: the product of two
    // square waves, low-passed, sits still when they are locked and swings at
    // the difference frequency when they are not. Seconds, not milliseconds.
    // --- board 2 -------------------------------------------------------
    // 4046 phase comparator -> loop filter -> VCO, VCO fed straight back to
    // the comparator (pin 4 to pin 3, no divider yet), so it locks 1:1.
    this.pc = 0.5             // comparator state: 1 up, 0 down, 0.5 idle
    this.up = 0
    this.dn = 0
    this.sigPrev = 0
    this.vcoPrev = 0
    this.cap = 0.35           // 100n, the integrating half of the loop filter
    this.pumpF = 0            // through the 10k, the proportional half
    this.loop = 0.35          // control voltage into pin 9
    this.vcoPhase = 0
    this.vcoOut = 0
    // 4051: Y0..Y2 carry osc1..osc3, Y3..Y7 are grounded on the board, so
    // those addresses feed the comparator silence and it never locks there.
    this.addr = 0
    // 4013 (or the spare 4040) dividing OSC1 for the Y3/Y4 sub-octave taps,
    // and the 4040 #2 feedback divider.
    this.d0Prev = 0
    this.d2 = 0
    this.d4 = 0
    this.fbCnt = 0
    this.fb = 0
    // Y5. The three measuring electrodes summed through the unity buffer and
    // biased to Vdd/2, squared up by the 4046's own input comparator. This is
    // the organism's rhythm as a logic level, and it is the only reference on
    // the mux the loop cannot simply lock and hold.
    this.slimeIn = 0
    // Lock detect: 1M + 1uF off the comparator node into a spare 40106 gate.
    // Locked, the average sits still and never crosses the Schmitt; unlocked,
    // it swings at the beat rate and clocks the counter, which walks the mux
    // to the next source. Hunt until locked, entirely in the passives.
    // Relaxation-oscillator state for the lock detector above.
    this.lockV = 0.5
    this.lockOut = 1
    // 4046 pin 1. The phase-frequency detector runs whichever comparator
    // drives the loop, and its pulses are wide when hunting, vanishing when
    // locked.
    this.up = 0
    this.dn = 0
    this.pcp = 1
    this.count = 0            // 4040, Q1..Q3 drive the address lines

    // Reused every sample. Allocating here instead of in the loop is the
    // difference between no garbage in the audio thread and 48000 short-lived
    // arrays a second, which the collector eventually stops to clean up and
    // which is heard as sporadic clicking.
    this.g = [0, 0, 0]
    this.coh = [0, 0, 0]      // ring pairs 0-1, 1-2, 2-0
    this.freq = [0, 0, 0]     // smoothed instantaneous, Hz
    this.lastEdge = [0, 0, 0]
    this.clock = 0
    this.reportAt = 0

    this.port.onmessage = (e) => {
      const d = e.data || {}
      if (Array.isArray(d.drives)) {
        for (let i = 0; i < 3 && i < d.drives.length; i++) {
          this.vac[i].drive = Math.max(0, Math.min(1, d.drives[i]))
        }
      }
      if (typeof d.gain === 'number') this.gain = Math.max(0, Math.min(1, d.gain))
      if (typeof d.tone === 'number') this.tone = Math.max(0, Math.min(1, d.tone))
      if (typeof d.vco === 'number') this.vcoLevel = Math.max(0, Math.min(1, d.vco))
      if (Array.isArray(d.mix)) {
        for (let i = 0; i < 3 && i < d.mix.length; i++) {
          this.mix[i] = Math.max(0, Math.min(1, d.mix[i]))
        }
      }
      // Changing the timing caps is how you drop the whole bank an octave on
      // the real board; 47n -> 100n is capScale 2.13.
      if (typeof d.capScale === 'number') {
        this.capScale = Math.max(0.5, Math.min(4, d.capScale))
        for (const o of this.osc) o.c = 47e-9 * this.capScale
      }
      // Sign of the summed electrode signal: the SLIME net, already squared.
      if (typeof d.slime === 'number') this.slimeIn = d.slime > 0 ? 1 : 0
      if (typeof d.running === 'boolean') this.running = d.running
    }
  }

  process(inputs, outputs) {
    const out = outputs[0][0]
    const out2 = outputs[0][1]
    if (!out) return true
    if (!this.running) { out.fill(0); if (out2) out2.fill(0); return true }

    // Where the strongest coupling drive sits right now. Once per block: the
    // drives move on the organism's timescale, not the sample rate.
    let raw = this.vac[0].drive
    if (this.vac[1].drive > raw) raw = this.vac[1].drive
    if (this.vac[2].drive > raw) raw = this.vac[2].drive
    let act = (raw - FREE_RUN) / DEPTH
    if (act < 0) act = 0
    else if (act > 1) act = 1
    const swellTo = REST_LEVEL + (1 - REST_LEVEL) *
                    (act < SWELL_KNEE ? act / SWELL_KNEE : 1)

    // Cutoff follows the swell, exponentially in frequency so the sweep sounds
    // even rather than bunched at the top. Per block: 2.7 ms is far finer than
    // the swell moves, and an exp() per sample is not worth it here.
    const norm = (this.swell - REST_LEVEL) / (1 - REST_LEVEL)
    const fc = FC_BED * Math.pow(FC_OPEN / FC_BED, norm < 0 ? 0 : norm > 1 ? 1 : norm)
    const kf = 1 - Math.exp(-2 * Math.PI * fc * DT)
    const nn = norm < 0 ? 0 : norm > 1 ? 1 : norm
    const dry = BED_DRY + (1 - BED_DRY) * nn
    // Effective timing capacitance: BED_DROP at rest, 1 fully forward. Applied
    // per block so the bank glides up rather than jumping.
    const bedMul = Math.pow(BED_DROP, 1 - nn)
    const triAmt = 1 - (1 - TRI_FWD) * nn
    const makeup = 1 + (BED_MAKEUP - 1) * (1 - nn)

    const dt = DT
    // Vactrol lag: light comes up in milliseconds and falls over tens of them.
    // That asymmetry is what makes the ring fuse to one tone under drive
    // instead of just sounding frequency-modulated.
    const g = this.g

    for (let n = 0; n < out.length; n++) {
      for (let k = 0; k < 3; k++) {
        const v = this.vac[k]
        const target = v.drive
        v.lum += (target - v.lum) * (target > v.lum ? A_UP : A_DN)
        g[k] = conductance(v.lum)
      }

      let mix = 0
      for (let i = 0; i < 3; i++) {
        const o = this.osc[i]
        const cEff = o.c * bedMul
        let dv = (o.out - o.v) / (o.r * cEff)
        for (let k = 0; k < 3; k++) {
          if (this.vac[k].to === i) {
            dv += (this.osc[this.vac[k].from].out - o.v) * g[k] / cEff
          }
        }
        o.v += dv * dt
        if (o.v > 1.2) o.v = 1.2
        if (o.v < -0.2) o.v = -0.2
        const was = o.out
        if (o.out === 1 && o.v > VT_HI) o.out = 0
        else if (o.out === 0 && o.v < VT_LO) o.out = 1
        if (was === 0 && o.out === 1) {
          const gap = this.clock - this.lastEdge[i]
          if (gap > 0) {
            const f = sampleRate / gap
            this.freq[i] += (f - this.freq[i]) * 0.15
          }
          this.lastEdge[i] = this.clock
        }
        // Capacitor voltage as a 0..1 ramp, blended against the comparator.
        const tri = (o.v - VT_MID) / VT_SPAN + 0.5
        mix += (tri * triAmt + o.out * (1 - triAmt)) * this.mix[i]
      }

      // Pairwise coherence around the ring, low-passed hard enough that only
      // the beat survives.
      const kCoh = K_COH
      for (let k = 0; k < 3; k++) {
        const a = this.osc[k].out, b = this.osc[(k + 1) % 3].out
        const prod = (a - 0.5) * (b - 0.5) * 4      // +1 in phase, -1 anti
        this.coh[k] += (prod - this.coh[k]) * kCoh
      }
      this.clock++

      // --- 4051 -> 4046 -> 4040 ---------------------------------------
      // 4013 (or spare 4040): D2 = OSC1/2, D4 = OSC1/4.
      if (this.osc[0].out === 1 && this.d0Prev === 0) {
        this.d2 ^= 1
        if (this.d2 === 1) this.d4 ^= 1
      }
      this.d0Prev = this.osc[0].out
      const x12 = this.osc[0].out ^ this.osc[1].out          // 4070 XOR
      // 4051 as wired: Y0-Y2 the oscillators, Y3 D2, Y4 D4, Y5 SLIME, Y6 X12,
      // Y7 n/c -- the schematic's "hunts vs nothing".
      const muxIn = [this.osc[0].out, this.osc[1].out, this.osc[2].out,
                     this.d2, this.d4, this.slimeIn, x12, 0]
      const sigIn = muxIn[this.addr]

      // 4040 #2: the divided VCO is what the comparator actually sees.
      if (this.vcoOut === 1 && this.vcoPrev === 0) {
        this.fbCnt = (this.fbCnt + 1) % PLL_FBDIV
        if (this.fbCnt === 0) this.fb ^= 1
      }
      this.vcoPrev = this.vcoOut

      // Phase comparator I -- the 4046's XOR on pin 2, which is what the
      // schematic calls for. PC2 locks cleanly and holds, and its output mean
      // sits at half rail whatever happens, so the lock detector downstream can
      // never see anything. PC1's mean is the signal: 0.5 while locked at 90
      // degrees, sweeping the rail when it is hunting.
      const pcOut = sigIn ^ this.fb
      const err = pcOut - 0.5
      this.cap += err * dt * 4.0
      if (this.cap < 0.001) this.cap = 0.001
      if (this.cap > 1) this.cap = 1
      this.pumpF += (err - this.pumpF) * K_LOOP
      this.loop = Math.max(0.001, Math.min(1, this.cap + 0.06 * this.pumpF))
      this.pc = pcOut
      const vcoF = Math.max(0, Math.min(1, this.loop)) * PLL_FMAX
      this.vcoPhase += vcoF * dt
      if (this.vcoPhase >= 1) this.vcoPhase -= 1
      this.vcoOut = this.vcoPhase < 0.5 ? 1 : 0

      // 4046 pin 1, PHASE PULSES. The chip's PFD runs alongside PC1: two
      // edge-set flags that cancel. While the loop hunts they are set a long
      // time each cycle; locked, they cancel almost immediately.
      if (sigIn === 1 && this.sigPrev === 0) this.up = 1
      if (this.fb === 1 && this.fbPrev === 0) this.dn = 1
      if (this.up && this.dn) { this.up = 0; this.dn = 0 }
      this.sigPrev = sigIn
      this.fbPrev = this.fb
      this.pcp = (this.up || this.dn) ? 1 : 0

      // The spare 40106 as a gated relaxation oscillator. Its input charges
      // toward its own output through the 1M; pin 1 holds that node down while
      // the loop is locked, so it only runs when the PLL is failing.
      // One time constant, both directions. An earlier version discharged ten
      // times faster than it charged, which was invented rather than taken
      // from the circuit: pin 1 is pulses, not a level, and against a 25% duty
      // a 10x pull-down wins every time. The node then topped out at 0.487
      // against a 0.66 threshold and the counter never clocked on any window.
      const k = K_LOCK
      this.lockV += ((this.pcp === 1 ? this.lockOut : 0) - this.lockV) * k
      const prevLock = this.lockOut
      if (this.lockOut === 1 && this.lockV > VT_HI) this.lockOut = 0
      else if (this.lockOut === 0 && this.lockV < VT_LO) this.lockOut = 1
      // 4040 #1: Q1..Q3 to the address lines, so it advances every 2 clocks.
      if (prevLock === 0 && this.lockOut === 1) {
        this.count = (this.count + 1) & 0xfff
        this.addr = (this.count >> 1) & 7
      }

      // Passive mixer into a coupling cap: centre it, then soft-limit so a
      // fused ring cannot clip the output. ch1 is the bank, ch2 the VCO --
      // the two interface channels the board actually feeds.
      // Three 100k into a node and a 10uF coupling cap -- a passive mixer, and
      // nothing else. There was a tanh(x*3) here, which is not on the board:
      // on a signal that is already square it acts as a brick wall and flattens
      // the dynamics the contraction is supposed to drive. The sum cannot
      // exceed +-0.5 anyway, so nothing needed limiting.
      const wsum = this.mix[0] + this.mix[1] + this.mix[2] || 1
      let s = mix / wsum - 0.5
      this.dc += (s - this.dc) * 0.0005
      s = (s - this.dc) * 2
      // Two poles of the 10k/10n stage: one is barely audible against a square
      // this dense, two rolls the upper harmonics off properly.
      const aOut = K_OUT
      this.lp += (s - this.lp) * aOut
      this.lp2 += (this.lp - this.lp2) * aOut
      // Smoothed per sample so the swell is a slow rise and fall, never a
      // step -- a jump in master level is exactly the click we spent so long
      // chasing out of this thing.
      this.swell += (swellTo - this.swell) *
                    (swellTo > this.swell ? K_SWELL_UP : K_SWELL_DN)
      const gn = this.gain * this.swell * makeup
      const v = s * (1 - this.tone) + this.lp2 * this.tone
      this.sc1 += (v - this.sc1) * kf
      this.sc2 += (this.sc1 - this.sc2) * kf
      // Brown noise: white through a leaky integrator, so energy falls with
      // frequency and it sits as bass rather than hiss. Gently rolled off on
      // top of that so nothing up there is sharp.
      this.nz += ((Math.random() * 2 - 1) - this.nz) * NZ_K
      this.nzf += (this.nz - this.nzf) * NZ_K
      // Breathe with the bank, so the rumble follows the beating rather than
      // sitting flat under it.
      const mag = v < 0 ? -v : v
      this.env += (mag - this.env) * 0.0004
      const breathe = 0.80 + 0.35 * this.env

      const bed = this.nzf * NZ_GAIN * NOISE_LEVEL * breathe +
                  this.sc2 * TONE_IN_BED
      const fwd = this.sc2 * (1 - dry) + v * dry
      // Crossfade bed to foreground as contact comes in, then saturate: even
      // harmonics read as thickness where the raw ones read as tinny.
      const mixed = bed * (1 - nn) + fwd * nn
      out[n] = soft(Math.tanh(mixed * BED_DRIVE) * gn)
      if (out2) {
        const w = (this.vcoOut - 0.5) * this.vcoLevel
        this.sd1 += (w - this.sd1) * kf
        this.sd2 += (this.sd1 - this.sd2) * kf
        out2[n] = soft((this.sd2 * (1 - dry) + w * dry) * gn * nn)
      }
    }

    // ~30 Hz is plenty for the visual and keeps the message queue quiet.
    if (this.clock - this.reportAt > sampleRate / 30) {
      this.reportAt = this.clock
      this.port.postMessage({
        coh: this.coh.slice(),
        freq: this.freq.slice(),
        lum: this.vac.map(v => v.lum),
        addr: this.addr,
        vcoHz: Math.round(Math.max(0, Math.min(1, this.loop)) * PLL_FMAX),
        locked: this.addr < 3 && Math.abs(this.lockV - this.loop) < 0.05
      })
    }
    return true
  }
}

registerProcessor('ring-processor', RingProcessor)
