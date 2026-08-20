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

- Inoculated:
- Settling complete (ch0 plateau, from shape.py):
- Analysed to:
- Disturbances, with times:
- Baseline recording used for MIN_DEPTH:

## Results

| test | outcome | notes |
|---|---|---|
| 1 amplitude tracks growth | | |
| 2 oscillation appears | | |
| 3 camera agrees | | |
| 4 chamber explains it | | |
| 5 applied vs sham | | |

**Verdict:**
