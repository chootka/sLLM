# metered

## Plain English

The organism's own rhythm decides how much the model gets to think with. A
faster rhythm buys the model a bigger working memory and more of its own past
turns; a slower one shrinks both. The model's only action is to light the whole
dish for a chosen number of seconds. It is told the metering rule but not what
light does, so it has to work out the connection from its own history, and each
turn it states which way it expects the rhythm to move. That prediction is
scored.

## What it tests

Whether a model, coupled to an organism through a stated rule, infers the one
relationship the rule depends on.

## Setup

- Dish: `three-radial`. Reference island central, plasmodium placed on it.
- Stimulus: whole dish, fixed brightness `STIMULUS_INTENSITY`.
- Exposure: `MAX_DOSE_PER_HOUR_WHOLE_DISH`, 180 s per rolling hour, 5% duty.
- Budget: `metered_budget()`, reference period 130 s, clamped x0.25 to x4.

## Running it

    ./scripts/py llm/loop.py --experiment metered --dry-run   # no light, real turns
    ./scripts/py llm/loop.py --experiment metered             # live

Selecting `metered` in the admin panel writes it to `data/run.json`, and
`sllm-loop` started afterwards picks it up without arguments.

## How to read a null result

That blue light moves the period is established in the literature. A null here
is a statement about this rig -- dose too low, shift below the 5 s resolution,
electrodes not resolving it, or the organism not in a state to respond. It is
not evidence that light does not affect the organism. See
`documentation/metered_loop.md`.

## Status

In development. Never run.
