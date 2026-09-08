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
previous turns. It chooses one thing -- how many seconds to light the dish --
and states which way it expects the period to move. Brightness is fixed, and
METERED lights the whole dish rather than a zone, so duration is the only lever
it has.

Blue light is assumed to slow the organism down -- see Direction below for what
is sourced and what is not. A slower organism means a smaller budget on the
next turn. So every light pulse the model orders costs it
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

### What is established, and what is not

**That blue light alters the period at all: established.** Blue light changes
both the amplitude and the period of Physarum's contractile and electrical
oscillations as part of the avoidance response. Sources supplied 2026-09-08:

- https://www.sciencedirect.com/science/article/abs/pii/S1566119913004497
  (illumination modifies the diversity and fundamental frequency of periodic
  electrical activity against unilluminated controls)
- https://pmc.ncbi.nlm.nih.gov/articles/PMC7935053/
- https://www.ds.mpg.de/3550340/200305_prl_alim (contraction waves shift phase
  against each other under blue light, raising pumping efficiency)
- https://www.researchgate.net/publication/247490731_Variations_in_the_biological_clock_of_the_slime_moldPhysarum_polycephalummeasured_electrically

Also in `~/research/1312.4189v1.pdf`: photoavoidance from white [6], blue [7]
and UV [8], and Nakagaki 1999 [6] showing oscillation frequency phase-shifted
and frequency-locked by rhythmic pulses of **white** light.

**Which way blue moves the period: established, and it matches the mapping
built here.** Blue increases the period (slower rhythm) and decreases the
amplitude (weaker contractions). Red also increases the period but *increases*
amplitude, which is how the colour-sensor work separates them. Sources supplied
2026-09-08:

- https://arxiv.org/pdf/1312.4139
- https://www.researchgate.net/publication/259312937_Towards_slime_mould_colour_sensor_Recognition_of_colours_by_Physarum_polycephalum

| wavelength | period | amplitude |
|---|---|---|
| blue | increases | decreases |
| red | increases | increases |
| green / white | increases period diversity | increases diversity, irregular micro-oscillations |

So a blue pulse lengthening the period, and a longer period shrinking the
budget, is the sourced direction and not a guess. `metered_budget` keeps its
inverse in reserve only in case this rig disagrees with the literature.

### Wavelengths this rig should not be putting on the dish

Red is not driven -- `IMAGING_RED` is `False` and captures use the IR flood.
That matters more than it looks: red increases the period like blue does, so
any red would be a second uncontrolled input to the metered quantity, and the
switch-off transient reportedly increases the period further still.

Far-red is a separate pathway. Far-red irradiation reportedly fragments the
plasmodium into small spherical pieces, and ordinary red inhibits that,
implying something phytochrome-like: https://pubmed.ncbi.nlm.nih.gov/11281031/

**This is a lead on the sporangia question, not an answer.** The chamber's
flood is 850 nm, which is near-infrared and outside the far-red band that work
describes, so it is not the same stimulus. What it establishes is that a
long-wavelength morphogenetic pathway exists in this organism. The flood runs
continuously and cannot be gated from the Pi.

**One counter-datapoint, kept on the record.** `~/research/1012.1809v1.pdf`
quotes Fingerle et al: membrane potential "shows no correlation with exposure
to light". That is an older membrane-potential result and it is not reconciled
with the above here. It matters because this loop meters off the electrical
channel, not off contraction.

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

Dose is SECONDS of light, summed over the trailing hour.

METERED lights the whole dish, so its cap is `MAX_DOSE_PER_HOUR_WHOLE_DISH`,
30 s/hour, 0.83% duty. Set deliberately low: under a whole-dish stimulus the
organism cannot move out of the light, and sporangia are forming. It is not
derived from the single-zone figure.

`MAX_DOSE_PER_HOUR`, 300 s/hour, is the single-zone budget every other prompt
uses. A zone is a ninth of the dish, so 300 s on one zone is about 33
zone-seconds of light -- comparable in total to 30 s whole-dish, but delivered
as a longer local exposure the organism can move out from under.

Neither figure is a measured tolerance. `experiments/calibration/blue-light-
response/` is the experiment that would establish one, and it has not run.

**How to read a null result.** That blue light moves the period is established
in the literature, including electrically -- see Direction above. So a null
here is not evidence about the organism. It is evidence about this rig, and
means one of:

- 30 s/hour is below the dose that produces a visible shift
- the shift is smaller than `PERIOD_QUANTUM_S` (5 s) and is rounded away
- the electrodes are not resolving it
- the organism is not in a state to respond

Do not write up a null as "blue light does not affect the period".

It was intensity x seconds until 2026-09-08. That form assumes reciprocity --
that 1.0 for 60 s and 0.25 for 240 s do the same thing to the organism -- which
nothing establishes for Physarum. Brightness is now fixed at
`STIMULUS_INTENSITY` and is not offered to the model, so dose is seconds and
the assumption never arises.

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
