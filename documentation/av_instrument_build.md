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

## The circuit in plain English

**1 — three oscillators that lean on each other.** A 40106 gate flips when its
input crosses a threshold. Wire a resistor from its output back to its input
with a capacitor to ground and it can never settle: the cap charges until the
gate flips, then discharges until it flips back. That is one oscillator, and
its speed is set by that R and that C. There are three, trimmed a few Hz apart.

Then the ring. Each oscillator's output drives an LED shining at a
light-dependent resistor -- the vactrol -- and that LDR sits in the *next*
oscillator's timing path. So oscillator 1 bleeds current into oscillator 2's
capacitor and nudges when it crosses its threshold. 1 to 2, 2 to 3, 3 to 1,
closed.

The organism sets how brightly each LED shines. Dim, the three run
independently and you hear them beating against each other. Bright, each drags
the next hard enough that they snap into step and become one tone. The piece
lives on that edge, trimmed to sit just below locking so small changes tip it
in and out.

**2 — the passive mixer.** Three 100k resistors into one node, 10uF to block
DC. That is the left channel: three square waves summed, nothing active.

**3 — the multiplexer.** The 4051 is an eight-way switch; three address pins
pick which input reaches the output. It is fed the three oscillators, two
divided-down copies of oscillator 1, an XOR of oscillators 1 and 2, the
electrode signal, and one empty input.

**4 — the phase-locked loop.** The 4046 holds a comparator, which reports
whether its two inputs are in step, and a VCO, whose pitch follows a voltage.
Feed the VCO's output back to the comparator and the loop hunts until the VCO
matches whatever the mux selected, then holds. The 10k/100n between them
smooths the correction so it settles instead of jittering. The VCO's output is
the right channel: a fourth voice chasing one of the others.

**5 — reconfiguration on failure.** The design wants the piece to rewire itself
when it cannot cohere: if the loop will not lock, move the switch and try a
different reference.

That needs a signal meaning "not locked". Averaging the VCO control voltage
does not work -- once locked that is a steady DC, so it never moves and nothing
ever fires. Averaging *any* node in the loop has the same flaw, PC1's output
included: its mean sits at half rail whether the loop is holding or wildly off.

4046 pin 1, PCP_OUT, is the phase-pulse output, and it pulses whenever the loop
is struggling. It gates a spare 40106 wired as its own slow relaxation
oscillator -- 1M from that gate's output back to its input, 1u to ground. While
the loop fails, the oscillator runs and clocks the 4040; the counter's outputs
are the mux address lines, so the switch steps on. The moment the loop locks,
pin 1 clamps the oscillator's input and the stepping stops.

Failure makes it move, success makes it stay. It searches until it finds
something it can hold, and holds until the organism pushes the bank far enough
to break the lock.

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
run 8 export, feedback dividers of 2, 4 and 8 all give 0 clocks.

The reason is arithmetic, not component choice. The lock-detect node tracks the
VCO control voltage, which is proportional to frequency, so clocking needs the
tracked voice to swing by at least 0.66 / 0.32 = **2.06x**. Measured across the
window, the widest-moving voices swing:

| voice | range | ratio |
|---|---|---|
| osc1 | 65.2-67.5 Hz | 1.03x |
| osc2 | 33.4-67.3 Hz | 2.02x |
| osc3 | 33.2-67.3 Hz | 2.03x |

No divider changes a ratio, which is why none of them helped. The gap is about
1.5%: even the fullest organism drive this data produces lands just under what
the Schmitt band demands.

**So is the lock detector broken, or is this the data?** Neither exactly.

- On osc1, which is what the mux is parked on as built, there is no swing to
  speak of because ch2 never connected in run 8 -- the organism did not grow to
  that electrode. Vactrol C's drive sits at the free-run floor throughout. That
  is a result, correctly represented, and not a thing to fix.
- On osc2 and osc3, which the organism *does* drive hard through ch0 and ch1,
  the swing is real and still 1.5% short of tripping the detector. That part is
  the circuit, not the data. A stronger signal would trip it; this organism's
  does not.

Widening the margin means gain on the lock-detect node, a narrower Schmitt band,
or a wider drive range -- board changes, none of them tried. Until then the mux
stays parked wherever it powers up, and on a run 8 export that means the right
output holds a near-constant pitch for the whole loop. `vco=0` silences that
channel if it is unwanted for a particular export.

The instrument is left exactly as jumpered. An earlier attempt here moved osc2
onto Y0 to give the right channel movement; it was reverted, because which
oscillator is worth listening to depends on which electrodes a given run
reached, and that does not belong baked into the circuit.

The bright off-centre point in the field is the mux selection, and it never
moves.

## Model vs schematic — known deviations

Checked 2026-09-01 against `schematics/sllm-cmos-stage-schematic.svg`. The
software model is not the schematic. These are the differences, worst first.

| | schematic | model |
|---|---|---|
| mux Y5 | **SLIME** — the electrode signal through a unity buffer, biased to Vdd/2 | tied to 0 |
| mux Y3, Y4, Y6 | D2 (OSC1/2), D4 (OSC1/4), X12 (4070 XOR of OSC1/OSC2) | tied to 0 |
| phase comparator | **PC1**, the XOR on pin 2 | PC2, the phase-frequency detector |
| lock detect taps | PC1 OUT (2), through 1M/1u | the loop-filter node |
| 4040 #2 | ÷N feedback divider; ÷4096 puts a 0.011 Hz rhythm at a ~45 Hz VCO | absent, feedback is direct |
| bank | ≈200 / 204 / 209 Hz on 47n, a few Hz apart | 67.3 / 35.8 / 34.2 Hz on 100n, an octave apart |
| C1 | 1n | 33n |
| R2 (12) | n/c, no offset | n/c — agrees |

**Open, not being worked on: the SLIME buffer is unity gain.** Confirmed with
the user 2026-09-01. The electrodes give ~1.4 mV; the 4046's SIG IN needs
roughly 100-400 mV p-p to switch. So as built, Y5 hands the comparator a flat
line and behaves like Y7 -- the mux lands on it, finds nothing, walks off. It
fails silently, and the software model will not show it, because the model
squares the summed signal with what is effectively an ideal comparator. Fixing
it means gain of ~100x or more between the buffer and the mux, or a comparator
there. Deliberately deferred; the piece runs without it, since the organism
still drives the ring through the vactrols.

**Y5 is the important one.** It is a missing signal path, not a tuning value:
the PLL is supposed to be able to lock to the organism's own signal, and in the
model that input is grounded. Per the user: all three measuring *electrodes*
feed the unity buffer, one op-amp section each, converging on the single SLIME
net. Not the DAC channels -- the electrode signals themselves, ch0/ch1/ch2.

**The lock detector, restated.** Earlier notes here concluded the detector
could not trip as built and blamed the topology. That conclusion was drawn from
this model, not from the schematic, so it does not stand. What is measured, on
the model with PC1 and the detector moved to PC1 OUT: the node sits at 0.500
while locked, which is exactly the designed behaviour -- STEP is meant to fire
on *losing* lock. Slowing the loop (Trim 2) makes it swing 0.40-0.81, crossing
the upper threshold but never returning under 0.32, so STEP still gets no
rising edge. Slower still and the VCO cannot reach the reference at all and the
beat averages back to 0.5. Unresolved, and not to be re-diagnosed until Y5 and
PC1 are in.

**Bank tuning as it stands**, for the record, so the retune is a deliberate
step and not a silent drift:

| | R | C | free-run |
|---|---|---|---|
| osc1 | 104.7k | 100.1n | 67.3 Hz |
| osc2 | 197k | 100.1n | 35.8 Hz |
| osc3 | 206k | 100.1n | 34.2 Hz |

C is 47n x the `?cap=` default of 2.13. To reach the schematic's figures on 47n
the trims are 75.1k / 73.6k / 71.8k. That is a different instrument -- a bank a
few Hz apart beats and fuses, a bank an octave apart cannot -- so it is a
deliberate change to make once the loop works, not before.

**Order of work.** Y5 and the other mux sources, then PC1 with the detector on
PC1 OUT, then re-measure the hunt. Retune the bank after that, not before:
changing the tuning and the loop together makes the result uninterpretable.

## No hardware is in this loop

`/drift` is entirely software. The AudioWorklet is a numerical model of the
CMOS stage; nothing in this repo drives the physical breadboard. There is no
MCP4728 code anywhere in the tree -- the DAC exists on the schematic and on the
bench, and the path from the session log through it into the real circuit is
not built here. (`DAC` in `exhibit_object.md` is the exhibition object's audio
output, an unrelated part.)

What `/drift` reads:

| address | source |
|---|---|
| `/drift` | live, the API's last 300 s, refetched every 10 s |
| `/drift?from=...` | the session log, that stored window, from the API |
| the exhibition object | neither -- `replay.json` beside the page, no API at all |

So the live / session-log distinction holds on the website, as intended. The
object is a third case: `loadBundled()` returns early, and `from` and `mins` are
ignored there.

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
