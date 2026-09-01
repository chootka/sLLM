# Status

Updated 2026-09-01 22:40 CEST. This is the only current-state document. If
another file disagrees with this one, this one is right.

## In plain language

Three metal probes sit in small blocks of agar in a petri dish. A fourth probe
sits in a fourth block and is the reference. A chip measures the voltage of
each probe against the reference once a second and writes it to a file. A
camera photographs the dish every five minutes.

The slime mould starts on the reference block and grows outward. When it
reaches a probe, it connects that probe to the reference, and that site can
then be measured.

All three probes have now been reached, ch1 and ch2 in run 6 and ch0 in run 8.
Each one, once reached, shows the voltage rising and falling about every two
minutes, by up to 1.8 thousandths of a volt. Probes the organism has not
reached do not. The same rhythm at the same speed and size is reported in the
published work.

Runs 7 and 8 were the same dish twice: one day with no organism and fresh agar,
then the organism back in on the same blocks and the same probes. The two-minute
bump is absent for all 14 hours of the empty day on every probe, present in 19
of 21 hours on ch0 with the organism in, and absent again after removal. That
is the organism-in / organism-out difference, and it holds.

It does not yet say which biological thing makes it. Two candidates fit
everything measured: the organism's own electrical rhythm, or chemistry at the
metal surface where the organism is touching it. Removing the organism removes
both at once, so a removal blank cannot separate them. The test that does is
stimulus and response -- change something the organism cares about, blue light,
with it still connected, and see whether the rhythm changes. Surface chemistry
has no reason to respond to a light.

The half-hour rhythm this rig was designed around is not present. It is ten
times smaller than expected.

## What the evidence terms mean

**Spectrum.** The recording sorted by wiggling speed: how much wiggling occurs
at a two-second rhythm, a ten-second rhythm, a two-minute rhythm, and so on.

**Background.** Every recording wiggles somewhat at every speed. The background
is that baseline. It slopes -- there is more slow wiggling than fast.

**Peak above background.** Much more wiggling at one specific speed than at the
speeds either side. This run has roughly ten times more wiggling at a
2.2 min rhythm than at 1.8 min or 2.8 min. The finding is the bump, not the
presence of wiggling.

**p < 0.005.** A sloping background can produce a bump by chance. Test: generate
200 fake recordings with the same background shape and no real rhythm, measure
the largest bump in each. Fewer than 1 in 200 reached the size of the observed
bump.

**dex.** Log10 units. +1.0 dex = ten times the background at that speed.

**The retraction result.** The ch1 tube retracted 2026-08-26 04:05. ch1's bump
measured +1.20 to +1.90 dex in the six hours before and +0.48, +0.89, +0.77 in
the three hours after -- all three below every prior hour. ch2 kept its tube and
stayed in its normal range. Exact rank test: if the ordering were random, the
three lowest of nine hours would all fall after the retraction about 1 time in
84, p = 0.012.

**Why the filtered trace plot is not evidence.** The chart at
https://claude.ai/code/artifact/c5d332ef-effc-4cc0-9f22-fe3fae29b3d0 filters to
90-200 s before plotting. Any input produces a rhythmic-looking line after that
filter, including pure noise. The spectrum and the retraction compare against a
reference -- neighbouring speeds, and the same electrode's earlier hours -- and
the trace plot does not.

## What the rig is

Three measuring electrodes in agar islands in a petri dish, plus a fourth
reference electrode in a fourth island. An ADS1115 reads each measuring
electrode against the reference once per second and appends a row to
`data/readings/electrodes_YYYYMMDD.csv`. An SHT31 logs chamber temperature and
humidity to `environment_YYYYMMDD.csv`. A camera photographs the dish every
300 s into `data/images/`.

The organism is inoculated on the reference island and grows outward. When it
reaches a measuring island it connects that electrode to the reference and the
site becomes measurable.

Everything else in the repo -- web panel, LED matrix, LLM loop -- sits on top of
those three files and is not required to record.

## Running now

| | |
|---|---|
| run | still tagged `20260827T210834Z-live`; step 8 ended 2026-08-29 00:00 |
| dish | organism out since 2026-08-29 00:00. Nothing recording from the dish |
| electrodes | flat since 2026-08-29 00:00: all three at -1.7 mV, 0.016 mV per sample, 90-200 s RMS 0.02-0.09 mV. Below every level ever recorded with electrodes in agar |
| record | continuous 2026-08-27 23:08:34 to 2026-08-29 16:41:50, then paused by the user, resumed 2026-09-01 21:07:22. Not a fault |
| services | `sllm-api` active since 2026-08-29 00:01:36, `sllm-loop` inactive |
| recovery mode | ON since 2026-08-23, panel dark, LEDs blocked |
| camera | working, 300 s timelapse |
| lighting | rebuilt 2026-08-27 22:22. Frames stable at mean 117, 1.45% clipped |
| matrix | unplugged |

## Channel map

Board A rows are the source of truth.

| ADS | channel | row | Cat6 pair | state |
|---|---|---|---|---|
| A0 | ch0 | r38L | orange | bridged 2026-08-28 ~01:00, run 8, carried the signal to 2026-08-29 00:00. Not colonised in run 6 |
| A1 | ch1 | r40L | blue | bridged 2026-08-24 13:24:30, tube retracted 2026-08-26 ~04:05 |
| A2 | ch2 | r40R | green | bridged 2026-08-24 23:15:30 |
| A3 | reference | r38R | brown | inoculated at t=0; re-inoculated 2026-08-27 21:47 for run 8 |

## Established

- **A 2.2-2.4 min oscillation on ch1 and ch2**, amplitude 0.5-1.8 mV. Absent
  from ch0. Absent from the pre-bridge record. p < 0.005 against coloured-noise
  surrogates. Controls passed: not temperature or humidity, not the camera
  cadence, survives channel differencing. Matches the 1-2 min / 2-3 mV band
  reported by Adamatzky and Jones.
- **Noise floor 0.02-0.10 mV per sample** at 8 SPS, against 0.7-2.8 mV before
  the data rate was fixed on 2026-08-22.
- **The large DC excursion is the bridge transient, not the chamber.** Step at
  each bridge, peak +28 mV at h+18, decay constant 5.6-8.6 h, zero crossing at
  h+32. Correlation with temperature r = 0.04.

- **ch1 retraction, 2026-08-26 04:05.** Tube gone, ch2 still connected. ch1
  noise 0.032 -> 0.188 mV. The 100-160 s line on ch1 fell to +0.48/+0.89/+0.77
  dex against +1.20 to +1.90 before; all three below every pre-value, exact
  rank test p = 0.012. ch2 held inside its prior range over the same hours.

- **ch0 bridged, run 8, 2026-08-28 ~01:00.** Tube seen in the dish by the user.
  Time is dated from ch0's per-sample noise, not the timelapse: 0.154 mV at
  23:08, first sustained crossing below the step 7 blank floor of 0.101 mV at
  ~01:00, 0.037-0.061 mV from 01:58 on. Run 6 reference 0.032 connected, 0.188
  unconnected. ch1 (0.10-0.48) and ch2 (0.09-0.70) unchanged at blank levels.
  Uncertainty +-30 min; the 00:28 and 01:24 disturbances bracket it. Refine from
  the timelapse.

- **The 00:28-02:48 DC excursion is temperature, not the bridge.** ch0 +27.4 mV
  peak to trough, ch1 +16.9, ch2 +13.7, all three together, pairwise r
  0.83-0.91. Against chamber temperature ch0 r = +0.73 at +8.1 mV/C, ch1 +0.66,
  ch2 +0.52. Chamber 25.31 -> 26.43 C at 01:57 -> 26.01, channels followed up
  and back. Run 6's bridge transient had r = 0.04 with temperature.

- **Run 8 against the run 7 blank: the line requires the organism.** Same dish,
  same agar blobs, same electrodes, blank then organism, back to back. Hours
  with p <= 0.01 in the 60-200 s band:

  | window | ch0 | ch1 | ch2 |
  |---|---|---|---|
  | blank, 08-27 07:15-21:45, 14 h | 0/14, +0.57 to +0.91 dex | 0/14, +0.45 to +1.08 | 0/14, +0.55 to +1.00 |
  | organism, 08-28 03:00 - 08-29 00:00, 21 h | 19/21, +1.64 to +3.22 dex, 120-164 s | 9/21, +0.59 to +2.39 | 0/21, +0.50 to +1.16 |
  | after removal, 08-29 01:00-16:00, 14 h | 0/14, +0.48 to +1.02 | 0/14, +0.37 to +0.95 | 0/14, +0.56 to +0.88 |

  The line is on ch0, the channel run 6 used as its never-colonised control, at
  2.0-2.7 min -- run 6's band on a different electrode. ch1 carries a weaker
  version at the same period in the same hours. ch2 shows nothing and its
  per-sample noise stayed at 0.182 mV, the unconnected signature; ch0 0.034,
  ch1 0.051.

  Band amplitude does not separate the windows: 90-200 s RMS is ~0.5 mV on ch0
  in both. The difference is concentration, not size. The blank's band energy is
  broadband noise from a channel running 3x noisier per sample, 0.111 against
  0.034 mV.

  The post-removal window is weak evidence on its own. At 0.016 mV per sample it
  is a disconnected or dry input, not a blank with electrodes in agar.

  Estimator caveat: run 2026-09-01 from a re-implementation of the
  pre-registered statistic, in the session scratchpad, not in the repo. On run
  6's post-bridge hours it returns +2.3 to +2.7 dex where +1.2 to +1.9 is
  recorded here. Rankings and p-values hold; absolute dex is not comparable
  across the two implementations. Every number in the table above is from the
  one implementation.

## Observed 2026-08-26 10:45, unconfirmed

- No visible tubes anywhere in the dish. Organism alive on the reference island.
  Oat flakes on the recording islands uneaten.
- Possible onset of sporulation. **User will judge 2026-08-27.** Not recorded as
  fact. Sclerotium is ruled out by direction: Adamatzky reports sclerotium as a
  rise toward +20 mV; channels are at -19 mV and falling.
- ch2 shows no noise rise despite no visible tube: 0.071 mV against its own
  confirmed-unconnected baseline of 0.193 mV. An invisible conductive path to
  ch2 apparently survives. Condensation bridging ruled out -- channel spread
  widened to 12.2 mV and pairwise correlations fell, the opposite of a short.
- Current configuration: two disconnected control electrodes (ch0 never
  colonised, ch1 since 04:05) and one connected electrode (ch2), same dish,
  same hours.

Base rate for this assay, Whiting et al. `1312.4189v1.pdf` section 3.1: about
10 of 20 dishes grow a usable single tube; 42 of 240 single-tube dishes gave
the oscillations sought. Listed failure modes include multiple tubes,
sclerotia formation, and growth away from the oat flake.

## Not established

- The 30-40 min band. 0.23-0.47 mV against 4-5 mV expected. Ten times under.
  Do not expect it to appear.
- Whether the 2.2 min oscillation is the organism or electrochemistry at a
  colonised electrode. This is the open scientific question. Runs 7 and 8 do not
  touch it: removal takes away the organism and the material on the electrode
  surface together. A stimulus-response test separates them.
- Replication beyond this rig. n = 1 dish, one organism, two colonisation
  events.

## Known problems

1. **Condensation.** Chamber runs at or near 100% RH. It shorted the LED matrix,
   and it is the reason the matrix cannot be repowered for a light-stimulus test.
   Needs airflow, desiccant, or a lower setpoint.

   Not responsible for the 2026-08-26 ch1 noise rise -- that was the tube
   retracting. Humidity recovered to 99.9% while ch1's noise stayed 8-10x high.
   Per-sample noise tracks electrode connection, not humidity.
2. **ch0 not colonised.** Closed 2026-08-28: ch0 bridged in run 8. Run 8 has no
   never-colonised control channel unless ch1 or ch2 stays unreached.
3. **Camera frontend timeouts.** Two on 2026-08-26, 04:18:36 and 11:06:07. Both
   followed handling of the rig, per the user. I2C to the sensor answers during
   the fault (module ID 0x0708), so the control pins are fine and the CSI data
   lanes are not delivering. Recovery needs an `sllm-api` restart, which gaps the
   electrode record because the same process logs both.
4. **`/dev/media3` permission error** at `sllm-api` start. Harmless now, but a
   reboot that renumbers media nodes will present as a dead camera. Fix is a
   systemd drop-in with `DeviceAllow=char-media rw`; must be written by the user.
5. **Deployed tree drifts.** Services run `/var/www/sllm`. A commit is not a
   deploy. Diff before assuming deployed behaviour.

## Next

1. Light stimulus test, next run. Organism in, blue LED on for some minutes,
   off again, repeated, times recorded. This is the test that separates the
   organism from interface electrochemistry. Needs a light source; the matrix is
   unplugged after a condensation short.
2. Fix condensation before the next run.
3. Decide the stimulus block length and repeat count, and write them down before
   the run starts.

## Deferred

- **LLM loop.** Nothing to close a loop around until the signal question is
  settled.
- **Matrix repair.** Unplugged, shorted on condensation. Any rebuild needs it
  sealed. Required before the light-stimulus test.
- **Re-plating electrodes.** Not indicated. Shorted-lead test 2026-08-24 was
  flat: drift ch0 +0.025, ch1 +0.004, ch2 +0.031 mV over 27 min.
- **Foil shield.** Not indicated. In-solution noise is at or below the shorted
  floor; 8 SPS already notches 50/60 Hz.
- **True differential pair (0-1, 2-3).** Do it after the stimulus test, not
  with it. Changing geometry and mux together makes the common-mode result
  uninterpretable.

## Recording protocol

| # | step | mode | duration | state |
|---|---|---|---|---|
| bench 1 | shorted-lead test | — | 27 min | done 2026-08-24 |
| bench 2 | foil shield | — | — | not indicated |
| bench 3 | build agar islands | — | — | done 2026-08-24 |
| bench 4 | verify island isolation | — | — | done 2026-08-24 |
| 5 | noise floor, no organism | `test` | 12 h | not run; the pre-bridge window of run 6 is serving as the blank |
| 6 | organism in | `live` | 24 h from bridge, 36 max | done, 2026-08-24 02:42 - 2026-08-26 21:15 |
| 7 | organism removed | `test` | 2026-08-26 21:15 - 2026-08-27 21:47, 24.5 h, discard first 10 h | done, not yet analysed |
| 8 | organism back in, same blobs | `live` | 24 h from bridge | done, 2026-08-27 23:08 - 2026-08-29 00:00. 21 h analysed post-bridge |
| 9 | blue light stimulus, organism in | `live` | not scheduled | not run |

Steps 6 and 8: the 24 h counts from tube bridge, not inoculation. In run 6 the
first bridge came 10.7 h after inoculation, so budget ~36 h wall clock for
step 8 or accept a shorter post-bridge window. Bridge time comes from the
timelapse.

Step 7: fresh agar blobs are unavoidable, and fresh agar settles for 6-12 h,
hence 24 h rather than the 6 h originally planned.

Steps 7 and 8 are a paired control: same dish, same blobs, same electrodes,
blank then organism, back to back.

## Step 7 pre-registration

Written 2026-08-26 21:20 CEST. Run `20260826T191540Z-test` had started; none of
its data had been read.

**Dish.** Organism removed. Fresh agar blobs. Electrodes in the same
configuration and positions as run 6.

**Run length.** 20 h minimum; scheduled to end 2026-08-27 18:00 CEST at 20.75 h. Analysis window h+10 to end. The first 10 h are
discarded as fresh-agar settling and are not analysed for any purpose.

**Statistic.** Per channel, the largest periodogram peak in the 60-200 s band,
expressed as log10 excess (dex) over the local median background taken over
+-0.6 octave in log period. p from 200 coloured-noise surrogates drawn on that
background. Same estimator as run 6, unchanged.

**Decision rule.**

| result on any channel | conclusion |
|---|---|
| peak >1.0 dex at p<0.01 | artifact. The 2.2-2.4 min line does not require the organism |
| all channels <1.0 dex, or >=1.0 dex only at p>=0.01 | the line does not reproduce without the organism |
| 0.5-1.0 dex at p<0.01 | inconclusive. No claim either way |

**Reference values from run 6.** ch1 and ch2 post-bridge +1.20 to +1.95 dex at
p<0.005. ch0, never colonised, +0.48 to +0.75 dex, p 0.12-0.50.

**Exclusions declared in advance.** The first 10 h. Any window in which the lid
was opened or the rig was handled. Any `sllm-api` restart gap.

No other statistic will be substituted after the data is seen.

**Result, scored 2026-09-01.** Analysis window 2026-08-27 07:15 - 21:45, 14 h.
Every hour on every channel fell between +0.45 and +1.08 dex, and the only hour
at or above +1.0 dex was ch1 at +1.08, p = 0.070. Decision rule row 2: the line
does not reproduce without the organism.

**Actual run, recorded after the fact.** Ended 2026-08-27 21:47 CEST when the
organism went back in, 24.5 h. Analysis window h+10 to end = 2026-08-27 07:15 -
21:47, 14.5 h. Longer than the 20.75 h scheduled; statistic and decision rule
unchanged. The 21:47 - 23:08:34 tail is excluded.

## Excluded data

| window | reason |
|---|---|
| 2026-08-26 04:05:30 - 04:07:00 | lid opened, electrodes wiggled. Noise 4.1/4.8 mV |
| 2026-08-26 ~04:14 - 04:18 | camera ribbon pulled and reseated, lid open. RH fell to 72% |
| 2026-08-26 04:23:41 - 04:23:57 | `sllm-api` restarted to recover the camera. 15 s gap. run_id preserved |
| 2026-08-26 11:08:32 - 11:08:39 | `sllm-api` restarted after a second camera frontend timeout at 11:06:07. 7 s gap. run_id preserved |
| 2026-08-27 21:47:00 - 21:53:00 | lid opened, organism inoculated. Per-second std 69.8/68.9/62.8 mV against ~1.7 mV baseline |
| 2026-08-27 21:47 - 23:08:34 | organism in the dish, still tagged `20260826T191540Z-test` / `test`. 81 min. Excluded from step 7, not part of step 8 |
| 2026-08-28 00:00 - 03:00 | temperature excursion, all three channels. Excluded from the step 8 analysis window |
| 2026-08-29 00:00 - 00:05 | organism removed. Per-sample noise 0.895/0.398/2.625 mV against ~0.03 baseline. Everything after this is a dry or disconnected input, not a blank |
| 2026-08-29 16:41:50 - 2026-09-01 21:07:22 | recording paused by the user. Not a fault, no run in progress |

## Other documents

| file | what it is |
|---|---|
| `hardware_setup.md` | wiring, board, sensors, settings |
| `bring_up.md` | how to build the rig from scratch |
| `method_basis.md` | why the rig is built this way, with citations |
| `growth_run.md` | pre-registered protocol for the LLM-loop run |
| `av_instrument.md` | future A/V direction, not a spec |
| `led_matrix.md`, `DEPLOYMENT.md`, `TAILSCALE_SETUP.md` | subsystem reference |
| `nature_brief_20260827.md` | briefing notes for the 2026-08-27 editor visit |
| `archive/` | superseded session notes, kept for the timeline and evidence |


# Briefing notes — 2026-08-27

Facts as of 2026-08-26 05:00 CEST. Numbers here come from run
`20260824T004220Z-live`, which ended 2026-08-26 21:15 CEST. Current state is at
the top of this file.

## What the project is

Three measuring electrodes in agar islands in a petri dish, plus a reference
electrode in a fourth island. An ADS1115 16-bit ADC reads each measuring
electrode against the reference at 1 Hz, 8 SPS conversion rate. An SHT31 logs
chamber temperature and humidity at 1 Hz. A camera photographs the dish every
300 s.

Physarum polycephalum is inoculated on the reference island and grows outward.
When a protoplasmic tube reaches a measuring island, that electrode is
connected to the reference through the organism and the site becomes
measurable.

## What was measured

| | |
|---|---|
| run start | 2026-08-24 02:42 CEST |
| duration | 50 h continuous, one 15 s gap |
| bridge to ch1 | 2026-08-24 13:24:30 |
| bridge to ch2 | 2026-08-24 23:15:30 |
| ch0 | never reached by the organism |
| noise floor | 0.02-0.10 mV per sample |

## The finding

An oscillation at 2.2-2.4 min, amplitude 0.5-1.8 mV, on both bridged
electrodes.

- Absent from ch0, which the organism never reached.
- Absent from the 10 h pre-bridge record on all three channels.
- p < 0.005 against 200 colored-noise surrogates drawn on each channel's own
  smoothed spectral background.

## Retraction event, 2026-08-26 04:05 CEST

The ch1 tube retracted. ch2 remained connected. This gives a natural on/off at
one site with a simultaneous control at the other.

- ch1 per-sample noise rose 0.032 -> 0.188 mV, the bridge signature in reverse.
- The 100-160 s line on ch1 fell to +0.48, +0.89, +0.77 dex in the three hours
  after, against +1.20 to +1.90 in the six hours before. All three post-values
  are below every pre-value; exact rank test p = 0.012.
- ch2 over the same hours: +1.58, +1.09, +1.50 against a prior range of +1.34
  to +2.18. Within range.

The signal rose at ch1 when a tube arrived and fell when it left, while the
control site did neither.

Caveat on interpretation: retraction also removes organism material from the
electrode surface, so interface electrochemistry weakens the same way. This
test does not separate the two.

## Controls run

| control | result |
|---|---|
| temperature and humidity | own line at 4.00 min, 0.0027 C and 0.0008 % RH. Nothing at 2.4 min |
| camera cadence | 132 captures epoch-averaged at +-150 s. Largest excursion z = 2.7 over 301 lags. No 300 s line in the spectrum |
| shared reference | survives channel differencing. ch1-ch2 peaks 2.22 min at 0.66 mV, p < 0.005 |
| period stability | drifts 1.82-2.58 min across successive 4 h windows |

## Prior work

- Adamatzky A, Jones J. arXiv:1012.1809. Same electrode geometry: one reference
  island with the plasmodium inoculated on it, recording islands under agar
  blobs. Reports high-frequency waves at 1-2 min, 2-3 mV.
- Kashimoto, cited in the above: surface potential 5 mV at 1.5-2 min.

Measured period here is slightly longer, amplitude somewhat lower.

## Limits — state these first

- **n = 1.** One dish, one organism, one run. No replication.
- **Organism-driven versus interface electrochemistry is not resolved.** Every
  result to date fits both. A stimulus-response test separates them; a removal
  blank does not.
- **One measurement site as of 2026-08-26 07:00.** ch0 was never colonised; ch1's tube retracted at 04:05. ch2 remains connected.
- **The 30-40 min band is absent.** The same paper reports 4-5 mV there. This
  run gives 0.23-0.47 mV, ten times under.
- One 15 s gap and three excluded windows on 2026-08-26, all listed in
  `STATUS.md`.

## If asked what is next

Either a light-stimulus test with the organism in place, or removal followed by
an 18-24 h blank. The artifact threshold is fixed in writing before either
runs: a peak in 60-200 s exceeding local background by >1.0 dex at p < 0.01,
with no organism present, means artifact.

## Phrasing

Accurate: the oscillation appeared with colonisation, is absent from the
uncolonised control, and survives the environmental and instrumental controls
run so far.

Not accurate: confirmed biological activity.

