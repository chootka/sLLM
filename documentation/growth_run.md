# Growth run — written before the data exists

The point of writing this first: on 2026-08-20 every positive finding came from
looking at the data, spotting something, and building an explanation around it.
Both died within the hour. Deciding the test in advance is what stops that.

Fill in the results at the bottom. Do not change the tests once the run starts.

## The run

One plasmodium, undisturbed, from inoculation to at least 24 h. No dish
handling, no chamber opening, no manual light.

**Run `sllm-loop`.** An earlier draft of this file said to keep it off, on the
grounds that a model lighting zones is a second variable. That was wrong: the
sham blocks make it a randomised controlled trial, which is stronger than
passive observation, and it does not have to be a separate run.

Acquisition mode `test` throughout, so nothing lands in the live record.

## The idea being tested

The organism grows over the day; the chamber does not. So anything that tracks
growth is the organism, and anything flat or tracking humidity is not.

## Excluded before analysis

- **The first 6 hours.** Electrodes settle into fresh agar: ch1 and ch2 plateau
  in about 4 h, ch0 in 5–6 h. Everything before the plateau is settling, and it
  is the largest signal in the record.
- **Any window within 5 minutes of a dish change or chamber opening.** Handling
  rails the ADC at ±256 mV.
- **Any window whose channel mean was subtracted.** Work on raw channels and on
  true pairwise differences only. Subtracting the mean of three channels smears
  each into the others and reverses the amplitude ranking.

## The tests, decided in advance

Split the post-settling record into an EARLY half and a LATE half.

**Test 1 — amplitude tracks growth.**
IQR amplitude per 30 min window, per raw channel.
- Positive: late-half median amplitude is at least 1.5x the early half, on the
  channel nearest the organism, and not on a channel it has not reached.
- Negative: no change, or all three channels move together (that is the
  chamber).

**Test 2 — oscillation appears.**
Fraction of windows clearing `MIN_DEPTH`, per raw channel.
- Positive: the late half clears it in at least 3x as many windows as the early
  half.
- Requires a calibrated `MIN_DEPTH`. Without a baseline recording this test
  cannot be run — say so rather than using the provisional 0.15.

**Test 3 — the two instruments agree.**
Plasmodium area per frame from the timelapse, against per-window amplitude.
- Positive: they correlate across the day, and the electrode nearest the
  organism correlates more strongly than the far ones.
- This is the strongest test available, because the camera and the ADC share no
  failure mode.

**Test 4 — the negative control.**
Humidity and temperature against the same features.
- If a feature correlates with humidity more strongly than with growth, it is
  the chamber. On 2026-08-20 the common mode hit r = +0.85 with humidity.

**Test 5 — applied against sham. This is the primary test.**
`LLM_SHAM_RATE` is 0.25: a quarter of turns are logged and never applied, and
the model is never told which. Randomised, same organism, same chamber, same
humidity.

Compare the 30 min after applied turns against the 30 min after sham turns, on
the same features as test 1.
- Positive: applied turns differ from sham turns, on the channel nearest the lit
  zone, and the difference grows with intensity.
- This is the only test here that manipulates rather than observes, so it is
  the one that can show the loop is closed rather than merely correlated.
- `sham` and `applied` are in every turn record in `data/logs/turns_*.jsonl`.
- Needs enough turns. At 10 min a turn, 24 h is 144 turns, roughly 36 sham.

## What counts as a result

Test 5 positive is the result worth having: it is the only manipulation.

Failing that, two of tests 1–3 positive with test 4 not explaining them. One
test alone is not a result — that is exactly what happened twice on
2026-08-20.

## Before believing anything

1. Have I looked at the whole record, or only at windows?
   `./scripts/py scripts/shape.py <day>`
2. Did this also happen before the organism was there?
3. Does the result depend on a correction step? Turn it off and see.
4. Am I fitting a straight line through a curve?
5. What would the empty rig show?

## Record the run here

- Run: `20260820T231556Z-live`, mode `live` throughout
- Started 2026-08-20 16:15 PST, stopped 2026-08-21 16:47 PST — 24 h 32 min
- 157 turns, **0 model failures**, prompt `blind`, sham 0.25
- Inoculated 2026-08-20 10:30 PST, so the run began ~6 h after inoculation and
  ~6 h after the dish change: settling was already complete at run start
- Disturbances: room lighting change at ~15:00 PST 2026-08-21, visible in the
  timelapse as mean frame brightness 69 -> 117
- No baseline recording exists. The plain-dish run did not happen.

## Results

| test | outcome | notes |
|---|---|---|
| 1 amplitude tracks growth | **negative** | all three channels 1.07x early-to-late, identical, against a 1.5x threshold. Identical across channels means global, not local |
| 2 oscillation appears | **not run** | needs a calibrated `MIN_DEPTH`, which needs a baseline recording |
| 3 camera agrees | **not run** | no progressive change detectable. Frame difference steps to 30% in the first 3 h then sits flat for 21. The IR imaging cannot segment the plasmodium |
| 4 chamber explains it | — | common mode is **0.96** of total variance. Temperature r = +0.48. Humidity railed at 99.9-100.0% all run, so it can no longer serve as a regressor |
| 5 applied vs sham | **negative** | ch0 p = 0.80, ch1 p = 0.12, ch2 p = 0.63, on 111 applied against 28 sham. Not underpowered |

**Verdict: no evidence of an organism signal, and none of a closed loop.**

This is a result about the instrument, not about the organism. The measurement
cannot see local activity, because 96% of its variance is shared across all
three electrodes — up from 86% the day before. Anything happening at one
electrode is a rounding error against that.

More runs of this kind will not change the answer. The next work is on the
measurement.

## What follows from it

The three channels share one reference electrode, so anything moving that
reference appears on all three. That is what common mode is, and 0.96 says it
is nearly everything.

The ADS1115 can measure a **true differential pair** instead: inputs 0-1 and
2-3, each a direct difference between two electrodes with no shared reference.
Common mode is then rejected in hardware rather than subtracted in software,
and subtracting it in software is what manufactured two false findings on
2026-08-20.

Cost: two channels instead of three. Change: `ADC_CHANNELS` and the mux mode in
`gpio/adc.py`. Test: a few hours in the same dish, then compare common-mode
share against the 0.96 above.
