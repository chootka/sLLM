# Metered loop

Written 2026-09-08. Describes the coupling between the organism's contraction
period and the model's operating budget, the exposure cap on the model's light,
and the prediction scorer.

Code: `llm/loop.py` (`metered_budget`, `DoseLedger`, `apply_dose_cap`),
`llm/filters/prediction.py`. Constant: `MAX_DOSE_PER_HOUR` in `api/config.py`.

Enabled with `--metered`. Without the flag the loop runs as it did before.

## Plain English

The organism's contraction period sets how much the model gets to think with.
A fast organism buys a large context window and a long memory. A slow organism
shrinks both.

Each turn the model is shown the recent electrical state and what it did on
previous turns. It chooses a zone, a brightness and a duration, and states
which way it expects the period to move.

Blue light is assumed to slow the organism down. A slower organism means a
smaller budget on the next turn. So every light pulse the model orders costs it
capacity. It is not told this. It has to read it off its own history.

A rolling hour's budget caps the light regardless of what the model asks for.
Over budget, the duration is trimmed, and both the requested and the allowed
value are written to the turn log.

On the following turn the prediction is scored against the measured period.
A move smaller than the measurement can resolve counts as no change, not as a
miss.

## Direction

Chosen 2026-09-08: shorter period grants more tokens.

The inverse was built first. It makes light a reward, which is positive
feedback with no stopping condition. The chosen direction makes the only way to
think at full width leaving the organism alone.

The direction rests on the working assumption that blue light lengthens the
period and lowers the amplitude. That assumption is unsourced. If it is
backwards, restore the inverse mapping in `metered_budget`.

## Metering

Reference period 130 s, the middle of the 106-164 s band measured across runs
6, 8 and the 2026-09-05 window. Scale is `130 / period_s`, clamped x0.25 to x4.
Base `num_ctx` is 8192 when `LLM_NUM_CTX` is unset. Recomputed every turn, not
once at startup.

| period | num_ctx | history turns |
|---|---|---|
| 65 s | 16384 | 12 |
| 106 s | 10046 | 7 |
| 130 s | 8192 | 6 |
| 164 s | 6493 | 5 |
| 400 s | 2662 | 2 |

## Exposure cap

Dose is intensity x seconds, summed over the trailing hour. `MAX_DOSE_PER_HOUR`
is 300, about 8% duty at full intensity. Step 8's block protocol delivered 1800
over an hour; this is a sixth of that.

`MAX_STIMULUS_DURATION` bounds a single stimulus. Nothing bounded the sum until
this. A model asking for the maximum every turn was inside every prior limit.

The cap trims rather than refuses, so the log records the difference between
what was asked and what reached the dish. Dose is spent only when a stimulus is
actually applied; a sham turn lights nothing and costs nothing.

## Prediction scoring

The model states a direction, not a number of seconds. `estimate_period` takes
the peak FFT bin, and bin spacing near period P over a window of T seconds is
about `P^2 / T`: 9.4 s at P=130 over the 1800 s window, 19 s over 15 min. An
integer-second prediction scored against that is noise.

The deadband is half the bin width, +-4.7 s at 130 s over the 1800 s window.
Inside it, the outcome is recorded as no change.

Three numbers are logged per run:

- `hit_rate`, over all scored predictions.
- `base_rate`, what always answering the commonest observed direction scores.
- `signed_hit_rate`, excluding turns the model predicted no change.

Most turns the period does not cross a bin, so a model that always predicts no
change scores well while predicting nothing. A hit rate at or below the base
rate is no skill.

## What the run tests

Two outcomes are expected and the scores separate them.

1. The model infers that light costs it capacity and settles at intensity 0.
2. The model attributes ordinary period drift to its own actuation and keeps
   acting.

The second is the more likely first result. `signed_hit_rate` against
`base_rate` is what distinguishes an inferred transfer function from a
confabulated one.

## Not covered here

The system prompt that asks for `expected_period_trend` is not yet in
`llm/filters/prompts.md`. The scorer reads that key from the model's JSON
reply.
