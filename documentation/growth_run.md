# Growth run — pre-registered

Tests are fixed before the run starts and not changed once it does. Results go
at the bottom.

## The run

One plasmodium, undisturbed, inoculation to at least 24 h. No dish handling, no
chamber opening, no manual light.

`sllm-loop` runs. `LLM_SHAM_RATE` 0.25 makes it a randomised controlled trial
rather than a second variable.

Acquisition mode `test` throughout.

## Hypothesis

The organism grows over the day; the chamber does not. Anything tracking growth
is the organism; anything flat or tracking humidity is not.

## Excluded before analysis

- **First 6 hours.** Electrode settling into fresh agar: ch1 and ch2 plateau at
  ~4 h, ch0 at 5–6 h. Largest signal in the record.
- **Any window within 5 minutes of a dish change or chamber opening.** Handling
  rails the ADC at ±256 mV.
- **Any window whose channel mean was subtracted.** Raw channels and true
  pairwise differences only. Subtracting the mean of three channels smears each
  into the others and reverses the amplitude ranking.

## Tests

Split the post-settling record into EARLY and LATE halves.

**Test 1 — amplitude tracks growth.** IQR amplitude per 30 min window, per raw
channel.
- Positive: late-half median amplitude ≥1.5× the early half, on the channel
  nearest the organism, and not on a channel it has not reached.
- Negative: no change, or all three channels move together.

**Test 2 — oscillation appears.** Fraction of windows clearing `MIN_DEPTH`, per
raw channel.
- Positive: late half clears it in ≥3× as many windows as the early half.
- Requires a calibrated `MIN_DEPTH` from a baseline recording. Without one,
  report not run rather than using the provisional 0.15.

**Test 3 — the two instruments agree.** Plasmodium area per frame from the
timelapse against per-window amplitude.
- Positive: they correlate across the day, and the electrode nearest the
  organism correlates more strongly than the far ones.
- Camera and ADC share no failure mode.

**Test 4 — negative control.** Humidity and temperature against the same
features.
- A feature correlating with humidity more strongly than with growth is the
  chamber. 2026-08-20: common mode r = +0.85 with humidity.

**Test 5 — applied against sham. Primary test.** A quarter of turns are logged
and never applied; the model is not told which. Compare the 30 min after
applied turns against the 30 min after sham turns, on the features of test 1.
- Positive: applied differs from sham, on the channel nearest the lit zone, and
  the difference grows with intensity.
- The only manipulation in the set.
- `sham` and `applied` are in every turn record in `data/logs/turns_*.jsonl`.
- At 10 min a turn, 24 h is 144 turns, ~36 sham.

## Result criteria

Test 5 positive. Failing that, two of tests 1–3 positive with test 4 not
explaining them. One test alone is not a result.

## Before believing anything

1. Have I looked at the whole record, or only at windows?
   `./scripts/py scripts/shape.py <day>`
2. Did this also happen before the organism was there?
3. Does the result depend on a correction step? Turn it off and see.
4. Am I fitting a straight line through a curve?
5. What would the empty rig show?

## Run record

- Run `20260820T231556Z-live`, mode `live` throughout
- Started 2026-08-20 16:15 PST, stopped 2026-08-21 16:47 PST — 24 h 32 min
- 157 turns, 0 model failures, prompt `blind`, sham 0.25
- Inoculated 2026-08-20 10:30 PST — run began ~6 h after inoculation and dish
  change, settling complete at run start
- Disturbance: room lighting change ~15:00 PST 2026-08-21, mean frame
  brightness 69 → 117
- No baseline recording exists

## Results

| test | outcome | notes |
|---|---|---|
| 1 amplitude tracks growth | negative | all three channels 1.07× early-to-late, identical, against a 1.5× threshold |
| 2 oscillation appears | not run | needs a calibrated `MIN_DEPTH` |
| 3 camera agrees | not run | frame difference steps to 30% in the first 3 h then flat for 21. IR imaging cannot segment the plasmodium |
| 4 chamber explains it | — | common mode 0.96 of total variance. Temperature r = +0.48. Humidity railed at 99.9–100.0% all run, unusable as a regressor |
| 5 applied vs sham | negative | ch0 p = 0.80, ch1 p = 0.12, ch2 p = 0.63, on 111 applied against 28 sham. Not underpowered |

**Verdict: no evidence of an organism signal, and none of a closed loop.**

Test 5 is void if the matrix was already unplugged during this run. The panel
shorted on condensation and has been unpowered since a date still **TBC**;
`matrixd` reports success either way. Establish the date before citing the
applied-vs-sham result.

96% of variance is shared across all three electrodes, up from 86% the day
before.

## Follow-on

The three channels share one reference electrode, so anything moving that
reference appears on all three.

Two changes identified, in order:

1. **Agar geometry.** The continuous bed shunts the source. See
   `hardware_setup.md`.
2. **True differential pair.** Inputs 0-1 and 2-3, each a direct difference
   between two electrodes with no shared reference. Costs one channel. Change
   `ADC_CHANNELS` and the mux mode in `gpio/adc.py`. Test: a few hours in the
   same dish, then compare common-mode share against 0.96.
