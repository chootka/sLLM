# Signal processing

Written 2026-08-27. Describes the chain that turns raw electrode CSV into
slime-attributable drive streams. Validated against run 6 (organism present)
and step 7 (organism removed).

Script: `scripts/slime_signal.py`.

## Plain English

The electrodes record a voltage every second. Most of what they record is not
the organism. It is the agar settling, the chamber warming and cooling, water
condensing, and the electronics themselves. The problem is separating the
organism's contribution from all of that.

The trick that works here is not filtering. It is this: **when the organism
touches an electrode, the recording gets quieter.** Much quieter -- roughly a
hundred times less power in the medium-speed wiggles. The organism forms a
conductive path between the electrode and the reference, and that path is a
better electrical connection than wet agar alone. A better connection carries
less noise.

So the organism announces itself twice over:

1. The noise drops. This is large, obvious, and hard to fake.
2. A rhythm appears at about 2.2 minutes, standing above the surrounding
   speeds.

Requiring both at once gives a switch. Over 11.5 hours of recording with no
organism in the dish, across three electrodes, that switch never turned on --
not once. With the organism present it was on 95% of the time on the electrode
with a good connection.

The switch is deliberately sticky. A connected electrode still dips below the
line for minutes at a time, so a switch that reacted instantly would flicker
on and off while the organism sat there connected. It waits half an hour of
continuous failure before switching off, and it ignores any stretch shorter
than an hour, on the grounds that colonisation takes hours and anything briefer
is noise. Tested against the run where the tube's arrival and departure times
are known from the photographs, this recovers the connected period as a single
38.6 hour stretch against a true 38.7 hours.

When the switch is on, the 2.2-minute rhythm is passed through and can drive
the sound and light. When it is off, nothing is passed through.

The reason for the switch is that the rhythm on its own cannot be trusted. If
you take *any* recording -- including pure noise -- and keep only the part
wiggling between 90 and 200 seconds, what comes out looks like a clean
oscillation. It always does. That is a property of the filter, not of the
recording. The blank run demonstrates this directly: its filtered phase
advances at 2.05 minutes, looking exactly like a signal, while the switch
correctly reads zero the entire time.

## Terms

| term | meaning |
|---|---|
| **PSD** (power spectral density) | how much wiggling occurs at each speed, per unit of speed. Units mV^2/Hz |
| **1/f noise** | noise that grows as you look at slower speeds. Drift. Does not average away |
| **white noise** | noise that is equal at all speeds. Averages away as 1/sqrt(N) |
| **dex** | log10 units. +1.0 dex = ten times |
| **local background** | median PSD over +-0.6 octave in period, centred on the point being tested |
| **excess** | PSD at a point, minus its local background, in dex. The bump above the surroundings |
| **high-pass** | remove everything slower than a cutoff, keep everything faster |
| **analytic signal** | complex-valued version of a real signal. Its angle is phase, its magnitude is envelope |
| **envelope** | the slowly-varying amplitude of an oscillation |
| **per-sample noise** | sd of successive differences / sqrt(2). Measures fast jitter, immune to drift |

## Why the noise, not the signal, is the discriminator

Measured PSD, 20-50 s band, same channels, same dish:

| channel | no organism (step 7) | organism present (run 6) | ratio |
|---|---|---|---|
| ch0 never colonised | 1.79e+01 | 2.46e+01 | 1.4x |
| ch1 | 4.81e+01 | 4.56e-01 | **105x** |
| ch2 | 1.85e+01 | 1.09e+00 | **17x** |

ch0 is the control: never colonised in either run, and it does not change.

Per-sample noise, same windows:

| channel | no organism | organism present |
|---|---|---|
| ch0 | 0.158 mV | 0.193 mV |
| ch1 | 0.283 mV | 0.037 mV |
| ch2 | 0.189 mV | 0.060 mV |

Consequence: **absolute amplitude in the 90-200 s band goes DOWN when the
organism connects** (ch1: 1.20 -> 0.87 mV). Band amplitude measures noise here,
not signal. Any separator built on absolute amplitude fails. This was tested
and discarded.

## Noise colour

Fraction of variance that is white (flat across speeds), all channels, both
runs: 0.03 to 0.18. PSD rises 1700-24000x from the 2-5 s band to the
200-500 s band.

The noise is overwhelmingly 1/f. Consequences:

- Averaging more samples per second does not reduce it. Raising the ADC data
  rate is not a lever.
- The only levers are: remove the drift (high-pass), and measure the bump above
  the local background rather than absolute power.

ADC floor for reference: LSB 0.0156 mV, ideal quantisation noise 0.0045 mV rms.
Connected channels sit at 0.037-0.060 mV, i.e. 8-13x above the ADC floor. The
excess is the electrode/agar interface, not the electronics.

## The chain

Input: `electrodes_YYYYMMDD.csv`, columns `timestamp, ch0_mv, ch1_mv, ch2_mv,
run_id`. Rows are filtered to one `run_id` and resampled onto a 1 Hz grid by
linear interpolation.

### Step 1 -- high-pass, tau = 600 s

Subtract a 600 s moving average. Removes agar settling, chamber thermal drift,
and the bridge transient.

Retains 2-600 s, about 8 octaves. This is deliberately wide. A narrow band
would manufacture the appearance of rhythm; 8 octaves does not.

Validation: the step 7 blank window had the chamber falling 26.3 -> 22.8 C.
No effect on any output. Chamber temperature stabilisation is not required.

### Step 2 -- presence, from per-sample noise

    presence_raw = sd(diff(x)) / sqrt(2), over 60 s windows

Low value = electrode connected through the organism.

Threshold `P_THRESH = 0.0531 mV`, set as the 5th percentile of all per-minute
windows from the step 7 blank, pooled across all three channels.

### Step 3 -- activity, from sliding spectral excess

1 h Hann-windowed periodogram, stepped every 60 s. Within it:

- PSD computed over 45-1800 s
- local background = median log10 PSD over +-0.6 octave in period
- excess = log10 PSD - background, in dex
- take the largest excess falling in the 90-200 s band

This is the run 6 estimator unchanged, computed on a sliding window instead of
a fixed one.

Threshold `D_THRESH = 1.01 dex`, set as the 95th percentile of all blank
windows, pooled across all three channels.

### Step 4 -- gate, with hysteresis and a minimum run

    raw   = (presence_raw < 0.0531) AND (activity > 1.01)
    held  = raw, but shut only after HOLD = 1800 s of continuous failure
    gate  = held, with runs shorter than MIN_RUN = 3600 s discarded

The first hour of any run is forced to 0 -- the sliding window is not yet full
and extrapolating it would be an invention.

Why the two extra stages, measured on run 6 where the truth is known from the
timelapse:

| | ch1 recovered | blank false positives |
|---|---|---|
| raw condition only | 38.7 h fragmented into 10 runs, longest 9.4 h | ch0 0.7% |
| + hysteresis | **one 38.6 h run** | ch0 8.7% |
| + minimum run | one 38.6 h run | **ch0 0.0%** |

ch1's true connected period was 38.7 h. Hysteresis is what recovers it as one
run instead of ten; without it the display chatters. Opening stays
instantaneous -- a late open is honest, a late close is not -- so the minimum-run
filter is what removes the short spurious opens hysteresis would otherwise
stretch.

### Step 5 -- phase and envelope

Band-limited analytic signal: FFT, zero everything outside 90-200 s and all
negative frequencies, double the survivors, inverse FFT. Angle = phase,
magnitude = envelope.

Emitted at the native 1 Hz. **This rate matters.** A 2.2 min oscillation
sampled once per minute gives 2.2 samples per cycle -- at Nyquist, and the
phase aliases into nonsense. An earlier per-minute version of this script was
wrong for exactly this reason.

## Output

`t_s, channel, presence, activity_dex, gate, phase_rad, amp_mv` at 1 Hz.

`presence` is rescaled to 0-1 for use as a continuous control. `gate` is the
binary decision. `phase_rad` and `amp_mv` are only meaningful while `gate` = 1.

## Validation

### False positives, full step 7 blank, 22.3 h

| ch0 | ch1 | ch2 |
|---|---|---|
| **0.0%** | **0.0%** | **0.0%** |

### Against the timelapse, run 6, full 66.6 h record

| channel | truth | gate |
|---|---|---|
| ch0 | never colonised | 2 runs, 3.9% of record |
| ch1 | bridged 13:24 08-24, retracted 04:05 08-26 (38.7 h) | one run 14:20 -> 04:59, **38.6 h** |
| ch2 | bridged 23:15 08-24, held | 00:09 -> 04:52 (28.7 h) + 7.7 h |

**Duration on ch1 matches to 0.1 h.** Both edges land ~55 min late, which is
the 3600 s window fill: the statistic cannot respond until the window contains
post-bridge data.

### Consequences

1. **Bridge time is recoverable from the electrodes, but lagged by about one
   window.** Not to the minute. Subtract ~1 h, or read the timelapse if the
   exact minute matters. ch2 was 54 min late on the same basis.
2. **ch0 gates 3.9% during run 6 while gating 0.0% in the blank.** ch0 was never
   colonised, so those are false positives. Candidate mechanism, not
   established: cross-talk through the shared reference. ch0's first-difference
   correlation with the bridged channels was +0.27 and +0.29 in run 6 against
   roughly zero in the blank.
3. Recovered period while gated: 2.26 min ch1, 2.25 min ch2. Matches run 6.

## Limits -- state these in any writeup

1. **The gate detects electrode connection, not biology.** It fires when a
   conductive path exists between electrode and reference and a 90-200 s line
   stands above background. Organism-driven ion transport and interface
   electrochemistry at a colonised electrode both produce this. The chain does
   not separate them; nothing recorded to date does. A stimulus-response test
   would.
2. **n = 1.** One dish, one organism, one blank.
3. **Thresholds are fitted to one blank run.** 11.5 h, three channels. They are
   not independent of the data they were set on. A second blank would make them
   so.
4. **Phase is only defined while gated.** The blank's filtered phase advances at
   2.05 min and looks identical to signal. Any figure showing a filtered trace
   must show the gate alongside it or it is misleading.
5. **The 30-40 min band remains absent.** 0.16-0.19 mV in both runs.

## On the dashboard

`GET /api/readings/processed?start=&end=&buckets=` returns the chain bucketed
for display. Per bucket per channel: `signal` (mean, plus min/max), `ghost`
(min/max), `gate`, `provisional`, `presence`, `activity`, `period`.

The endpoint reads WARMUP = 4200 s **before** `start`. Without the lead-in the
high-pass has no run-in and the periodogram no full window, so the first hour
of every view would draw a false gate = 0.

The chart has a raw/signal toggle in its header. In signal mode it draws the
gated trace solid over a faint ghost band, and live becomes a 10 s refetch
rather than a socket append -- the chain needs a server-side window and cannot
run per-sample in the browser.

**The ghost is not decoration.** A flat signal line means no organism; a frozen
feed draws the same picture. The ghost is never flat while data is arriving, so
it is what distinguishes the two.

The ghost is drawn as a filled `ghost_min`..`ghost_max` band, not a single
line. A mean would average out spikes narrower than one bucket -- the reason
the raw endpoint carries min/max as well -- and plotting only the max, as the
first version did, drew a one-sided envelope sitting above the flat line
instead of straddling it.

The ghost is high-passed, so it will not match the raw view: everything slower
than 600 s has been removed from it.

### Cost

`slide_dex` is ~90% of the chain. It is vectorised across windows -- computing
the background per window meant ~100k `np.median` calls for a day of data,
where numpy's per-call overhead rather than the arithmetic was 91% of total
runtime. Stacking the periodograms first makes it 79 median calls on 2-D
arrays: 7.5x faster, bit-identical output.

Measured, three channels, 60 s step: 22.3 h in 1.09 s, the full 66.6 h record
in 2.97 s. `step_for()` additionally coarsens the step to match display
resolution on wide windows; the gate is invariant to it within 0.21 pp.

## Running it

    ./scripts/py scripts/slime_signal.py RUN_ID FILE.csv [FILE.csv ...] > drive.csv

Example:

    ./scripts/py scripts/slime_signal.py 20260826T191540Z-test \
        data/readings/test/electrodes_20260826.csv \
        data/readings/test/electrodes_20260827.csv > blank.csv
