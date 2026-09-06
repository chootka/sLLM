# Cycles / entrainment

## Plain English

The tube contracts and expands, roughly every two minutes. That is a beat. Each
turn the model says what it believes that beat is, and everything it does is
expressed in its own estimate rather than in seconds. When it comes back it is
told how many cycles actually passed against how many it expected. The only
thing it can do to the organism is place light, which shifts the beat it is
trying to follow.

Whether the two settle into a shared tempo, or the model only learns to track
something indifferent to it, is what the run records.

## What is different from BLIND

BLIND hands the model `period_s`. Here it is withheld:

- the state carries no period on any channel
- the reply carries `believed_period_s`
- `duration_cycles` converts with the model's belief, not the measurement, so a
  wrong estimate makes a wrong-length stimulus and nothing says so
- each turn carries `since_last_turn`: gap, cycles expected at the last stated
  period, cycles actually elapsed, and the difference

## Logged per turn

`believed_period_s`, `measured_period_s`, and `cycle_error`
(`gap_s`, `cycles_expected`, `cycles_actual`, `error_cycles`).

Entrainment, if it happens, is `error_cycles` converging toward zero.

## Sonification

`/cycles` clicks both tempos: the organism at its measured period, the model at
its believed period, both multiplied by the same constant so the ratio is
exact. Wrong estimate, two clicks drifting past each other. Right estimate,
one click.

## Status

Prompt variant and loop changes written 2026-09-06. Exercised on replay against
`electrodes_20260905.csv`. Never run live.
