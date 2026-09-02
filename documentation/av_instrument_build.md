# A/V instrument — build notes

Written 2026-08-27. Covers the software instrument at `/drift` and what was
learned about the physical CMOS board while modelling it. Direction and
principles are in `av_instrument.md`; the signal chain is in
`signal_processing.md`.

## Plain English

There are two instruments now. One is the physical circuit on breadboards. The
other is a copy of it in software, running in a browser page, driven by the
electrode data.

The software copy is not a synthesiser imitating the circuit. It is the
circuit's physics written out as arithmetic: each oscillator is a capacitor
charging through a resistor until a threshold flips it, exactly as the chip
does. That is why it can be used to answer questions about the real board.

Doing that turned up three things about the board that are worth checking at
the bench. None of them were observed on the hardware — they fall out of the
component values, so they are hypotheses, not findings.

The page plays the live electrodes by default. Add a start time to the address
and it replays a stored stretch instead: where to start, how many minutes of
recording to play, and how many times faster than real time. Those three, and
three more that change the sound, are listed under URL parameters below.

The visuals are a field of terminal block characters. Interference between the
oscillators makes the pattern; where they agree it goes bright, where they
disagree it goes dark. Nothing is drawn as a chart or a readout.

## Where it lives

| | |
|---|---|
| page | `/drift`. Live with no parameters, replay with `from`. Parameters below |
| audio engine | `frontend/public/ring-processor.js`, one AudioWorkletProcessor |
| page | `frontend/src/views/Drift.vue` |
| route | `frontend/src/router.js` (vue-router 4; v5 needs vite >= 7) |

No synthesis library and no `OscillatorNode`. Plain JS per-sample at 48 kHz.

## URL parameters

All optional. Out-of-range values are clamped, not rejected. Parsed in
`Drift.vue`.

| parameter | unit | default | range | what it does |
|---|---|---|---|---|
| `from` | unix seconds | none | — | start of the replay window. Absent means live |
| `mins` | minutes of recording | 24 | 1-240 | length of the window played |
| `speed` | multiplier | 24 | 1-240 | recorded seconds per wall-clock second |
| `cap` | multiplier on the 47n timing caps | 2.13 | 0.5-4 | pitch of the bank. 2.13 is 100n, an octave down |
| `mix` | three weights, comma separated | `0.45,1,1` | 0-1 each | mixer resistor ratios, osc1/osc2/osc3 |
| `vco` | level | 0.35 | 0-1 | PLL channel, right output. `vco=0` silences it |
| `mux` | three oscillator indices | `0,1,2` | perms of 0-2 | which oscillator each 4051 address selects |

Playback length is `mins / speed` minutes: `mins=180&speed=12` is 15 minutes.
Replays loop.

`from` needs 2.17 h of record before it, since the endpoint reads WARMUP
seconds ahead of the window.

## How a channel drives its vactrol

Per channel, from `/api/readings/processed`. `gate` and `signal` are defined in
`signal_processing.md`.

    drive = gate > 0.5 ? 0.12 + 0.62 * clamp(signal / 2.0 + 0.5, 0, 1)
                       : 0.12

- 0.12 is the free-run floor: LED dark, oscillators uncoupled. 0.74 is the
  ceiling the formula can reach.
- ch0 drives vactrol A, ch1 B, ch2 C.
- A shut gate forces the floor, so a channel with no organism cannot modulate
  anything however large its raw trace is.

The page requests `buckets = min(2000, span_seconds)`, so a 180 min replay
steps every 5.4 s of recording. Live reads the last 300 s and refetches every
10 s.

**Test it headless.** The same file runs in Node by stubbing three globals.
Every number below was measured this way, without a browser:

    global.AudioWorkletProcessor = class { constructor(){ this.port =
      { onmessage: null, postMessage(){} } } }
    global.registerProcessor = (n, c) => { global.__P = c }
    global.sampleRate = 48000
    new Function(fs.readFileSync('public/ring-processor.js','utf8'))()

## What is modelled

| board | model |
|---|---|
| 40106 x3 | RC integrator vs Schmitt, Euler per sample. Datasheet thresholds 0.66/0.32 |
| vactrols A/B/C | LDR injecting current into the next timing cap; asymmetric lag 5 ms up, 50 ms down; resistance log-interpolated 10M dark to 5k lit |
| ring | osc1 -> osc2 -> osc3 -> osc1, as jumpered |
| passive mixer | weighted sum, 10uF coupling cap as a DC blocker |
| 4046 | PC2 phase-frequency detector, series 10k+100n loop filter, VCO |
| 4051 | array index; Y3..Y7 grounded, so those addresses feed silence |
| 4040 | counter, Q1..Q3 to the address lines, so it advances every 2 clocks |
| outputs | ch1 the bank (left), ch2 the VCO (right) |

Not modelled: 4070, 4040 #3, the unbuilt 10k pot and 10k/10n stage.

## Bench hypotheses — unverified against hardware

1. **C1 = 1n puts the VCO out of reach.** R1 100k with C1 1n centres the VCO
   near 4.8 kHz; the bank runs 75-260 Hz. No comparator acquires across 30x.
   C1 ~33n centres it in the bank. The model uses 33n.
2. **PC1 cannot acquire, only hold.** An XOR comparator has a narrow capture
   range. PC2 (pin 13) discriminates frequency and pulls in from anywhere.
   Measured: PC2 locks to 0.0% error, PC1 to 8%. Worth confirming which pin the
   loop filter actually hangs off, since the row mapping was flagged unverified.
3. **The lock detector cannot trip as built — unresolved.** See below.

## Open: making the mux re-point

The 4040 only advances when the lock detector produces an edge, which needs the
1M/1uF node to go above the 40106's upper threshold (~0.66 of rail) and back
below the lower (~0.32). Measured against real run-6 drives:

| configuration | node range | swing | clocks |
|---|---|---|---|
| as built, direct feedback | 0.12 - 0.22 | 0.10 | 0 |
| + one 4040 stage (divide by 2), C1 33n | 0.47 - 0.89 | 0.42 | 0 |
| + divide by 2, C1 27n | 0.39 - 0.73 | 0.34 | 0 |
| + divide by 2, C1 22n | 0.31 - 0.59 | 0.28 | 0 |
| + divide by 2, C1 18n | 0.26 - 0.48 | 0.22 | 0 |

Direct feedback leaves the swing far too narrow. A divider widens it enough,
but no C1 tested both clears 0.66 and returns under 0.32 -- the hysteresis band
is 0.34 wide and the swing only exceeds that at 27n, where it sits too high.

**Not yet tried:** divide by 4 (wider swing), R2 on pin 12 to offset and
compress the VCO range independently of the span, or biasing the lock-detect
node with a divider so it straddles the band. Do this before concluding the
topology needs changing.

**Divider sweep, 2026-09-01: not the answer.** Measured headless against the
shipped 3 h window, feedback dividers of 2, 4 and 8 all give 0 clocks. The
lock-detect node still never reaches 0.66. The reason is arithmetic rather than
component choice: the node tracks the control voltage, which is proportional to
frequency, so clocking needs the tracked voice to swing by at least
0.66 / 0.32 = 2.06x. The bank swings 33.2 -> 67.5 Hz, a ratio of 2.03. It is
short, and no divider changes a ratio. Widening it needs gain on that node, or
a narrower Schmitt band, and neither is on the board.

So the PLL stays latched on one address forever. That part is unresolved and
this note does not resolve it.

**What was audible, and was fixed separately.** Latched is survivable; latched
onto the *wrong voice* is not. Y0 carried osc1, and osc1 is modulated only by
vactrol C. On the shipped window that channel never connects, so its coupling
sits at the free-run floor all the way through and the right output was a bare
square at a fixed pitch for fifteen minutes.

Measured over that window, after lock settles:

| 4051 Y0 carries | VCO range | spread | sd | clocks |
|---|---|---|---|---|
| osc1, as built | 62.9-71.1 Hz | 8.2 | 0.76 | 0 |
| osc2 | 13.1-82.0 Hz | 68.9 | 15.82 | 0 |
| osc3 | 16.9-88.7 Hz | 71.8 | 13.06 | 0 |

`?mux=` sets which oscillator each 4051 address selects, defaulting to the
board as jumpered, `0,1,2`. On the board it is which oscillator output goes to
which 4051 input pin -- a jumper, not a new part. The mux still never moves;
the setting only decides where it is parked.

**This is a per-export choice, not a correction.** ch2 having no connection in
run 8 is a result -- the organism did not grow to that electrode -- and it is
represented honestly: vactrol C's drive sits at the free-run floor throughout,
exactly as it should. Nothing fills that silence in. What `?mux=1,2,0` does is
point the PLL at osc2, which moves because ch0 and ch1 *are* driving it. The
movement is real signal from electrodes the organism did reach.

Leaving the default is equally defensible: a right channel that sits still is a
true statement about an electrode nothing arrived at. Decide per export, and on
a run 6 window, where ch1 and ch2 both connect, the default is the right answer
anyway.

The bright off-centre point in the field is the mux selection, and it still
never moves -- it now sits on osc2's source.

## Sound decisions, with the measurement behind each

- **No limiter.** A `tanh(x*3)` on the mix was removed: it is not on the board,
  and on an already-square signal it flattens the contraction dynamics. Level
  range over real run-6 drives went 2.0 -> 5.9 dB, crest 4.9 -> 7.4 dB.
- **osc2/osc3 detuned 197k/206k.** Both are 100k+100k on the board, but modelled
  dead equal they land on one pitch and sum into a single thick voice instead of
  beating. A few percent apart is truer to real parts.
- **osc1 mixer weight 0.45.** A lone square has constant RMS whatever its pitch
  does; level movement comes only from voices beating. osc1 sits an octave above
  the pair and never beats with them, so at equal weight it lays a fixed slab
  under the dynamics. 0.45 maximised level range, 5.8 -> 6.8 dB. **On the board
  that is a 220k mixer resistor instead of 100k.**
- **Timing caps 100n (capScale 2.13).** Drops the bank to 35-65 Hz uncoupled.
- **VCO level 0.35.** It tracks pitch but never participates in the fusing, so
  it reads as a fixed slab too.
- The square wave is deliberate and stays. The 10k/10n stage is implemented but
  defaults off.

## What the organism does to it

Measured by feeding real run-6 drives through the model. ch1's oscillation
swings vactrol B from 0.32 to 0.57, which crosses the fusing threshold, so osc1
drops from 143 Hz to 75 Hz and back on the 2.2 min rhythm. The three field
sources converge and separate on the same cycle.

With no organism every drive sits pinned at the 0.12 free-run floor and none of
this happens.

## Useful replay windows

| | |
|---|---|
| ch1 bridges | `/drift?from=1787570670&mins=180&speed=12` |
| ch2 bridges | `/drift?from=1787606130&mins=180&speed=12` |
| both driving | `/drift?from=1787609358&mins=24&speed=24` |
| ch1 retracts | `/drift?from=1787709900&mins=120&speed=12` |
| run 8, ch0 driving | `/drift?from=1787889600&mins=180&speed=12` |
| run 7 blank, nothing driving | `/drift?from=1787810400&mins=180&speed=12` |

Run 8 measured over its window: ch0 drive 0.12-0.74, at the floor in 159 of
2000 steps; ch1 0.12-0.74, at the floor in 764; ch2 pinned at 0.12, never
bridged in run 8. The run 7 blank: all three pinned at 0.12 for all 2000 steps.

Recorded range 2026-08-05 06:48 to now. `from` needs 2.17 h of record ahead of
it, since the endpoint reads WARMUP before the window.

## Next

1. Resolve the mux re-pointing: try divide-by-4, R2 on pin 12, or biasing the
   lock-detect node.
2. Decide whether `ring-processor.js` should be renamed -- "ring" here means the
   coupling topology, not a ring oscillator, and the filename reads as the
   latter.
3. Image renders: `scripts/render_images.py` has `colour` and `trails` modes,
   written and working, not yet used for anything.
