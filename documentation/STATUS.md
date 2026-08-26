# Status

Updated 2026-08-26 08:35 CEST. This is the only current-state document. If
another file disagrees with this one, this one is right.

## In plain language

Three metal probes sit in small blocks of agar in a petri dish. A fourth probe
sits in a fourth block and is the reference. A chip measures the voltage of
each probe against the reference once a second and writes it to a file. A
camera photographs the dish every five minutes.

The slime mould starts on the reference block and grows outward. When it
reaches a probe, it connects that probe to the reference, and that site can
then be measured.

Two of the three probes have been reached. Both show the voltage rising and
falling about every two minutes, by up to 1.8 thousandths of a volt. The
unreached probe does not. Nothing showed it before the organism arrived. The
same rhythm at the same speed and size is reported in the published work.

The half-hour rhythm this rig was designed around is not present. It is ten
times smaller than expected.

It is not yet proven that the two-minute rhythm comes from the organism. It
appeared when the organism arrived, which is not the same as being caused by
it. The test that settles this is removing the organism and seeing whether the
rhythm stops.

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
| run | `20260824T004220Z-live`, started 2026-08-24 02:42 CEST |
| elapsed | 50 h |
| services | `sllm-api` active, `sllm-loop` inactive |
| recovery mode | ON since 2026-08-23, panel dark, LEDs blocked |
| chamber | 25.6 C, 99.5% RH |
| camera | working, 300 s timelapse |
| matrix | unplugged |

## Channel map

Board A rows are the source of truth.

| ADS | channel | row | Cat6 pair | state |
|---|---|---|---|---|
| A0 | ch0 | r38L | orange | never colonised |
| A1 | ch1 | r40L | blue | bridged 2026-08-24 13:24:30, tube retracted 2026-08-26 ~04:05 |
| A2 | ch2 | r40R | green | bridged 2026-08-24 23:15:30 |
| A3 | reference | r38R | brown | inoculated at t=0 |

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

## Not established

- The 30-40 min band. 0.23-0.47 mV against 4-5 mV expected. Ten times under.
  Do not expect it to appear.
- Whether the 2.2 min oscillation is the organism or electrochemistry at a
  colonised electrode. This is the open scientific question.

## Known problems

1. **Condensation.** Chamber runs at or near 100% RH. Condensation moved the
   per-sample noise on ch1 by 10x on 2026-08-26 with no mechanical change, and
   previously shorted the LED matrix. This is the main unsolved engineering
   problem. Needs airflow, desiccant, or a lower setpoint.
2. **ch0 not colonised.** Useful as a running control; a problem only if a third
   measuring site is required.
3. **`/dev/media3` permission error** at `sllm-api` start. Harmless now, but a
   reboot that renumbers media nodes will present as a dead camera. Fix is a
   systemd drop-in with `DeviceAllow=char-media rw`; must be written by the user.
4. **Deployed tree drifts.** Services run `/var/www/sllm`. A commit is not a
   deploy. Diff before assuming deployed behaviour.

## Next

1. Decide the artifact threshold in advance and write it into `rebuild_plan.md`
   step 5: a peak in 60-200 s exceeding local background by >1.0 dex at p<0.01,
   with no organism, means artifact.
2. Run one of two tests:
   - **Light stimulus.** Blue LED on/off blocks, 20 min each, four repeats,
     times recorded. Shows whether the organism drives the signal. Keeps the
     organism. Blocked on condensation risk to the matrix.
   - **Organism removed.** `test` mode, 18-24 h, discard the first half. Shows
     whether the signal depends on the organism. Ends the run.
3. Fix condensation before the next run regardless of which test runs.

## Excluded data

| window | reason |
|---|---|
| 2026-08-26 04:05:30 - 04:07:00 | lid opened, electrodes wiggled. Noise 4.1/4.8 mV |
| 2026-08-26 ~04:14 - 04:18 | camera ribbon pulled and reseated, lid open. RH fell to 72% |
| 2026-08-26 04:23:41 - 04:23:57 | `sllm-api` restarted to recover the camera. 15 s gap. run_id preserved |

## Other documents

| file | what it is |
|---|---|
| `hardware_setup.md` | wiring, board, sensors, settings |
| `bring_up.md` | how to build the rig from scratch |
| `method_basis.md` | why the rig is built this way, with citations |
| `rebuild_plan.md` | bench punch list and the recording step table |
| `growth_run.md` | pre-registered protocol for the LLM-loop run |
| `av_instrument.md` | future A/V direction, not a spec |
| `led_matrix.md`, `DEPLOYMENT.md`, `TAILSCALE_SETUP.md` | subsystem reference |
| `nature_brief_20260827.md` | briefing notes for the 2026-08-27 editor visit |
| `archive/` | superseded session notes, kept for the timeline and evidence |
