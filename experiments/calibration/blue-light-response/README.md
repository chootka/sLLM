# Blue light response

Step 9 of the recording protocol.

## Plain English

The organism is connected to an electrode and that electrode is oscillating.
Blue light is shone on the dish for an hour, then not for an hour, six times
each. If the oscillation is the organism, the light should change it. If it is
chemistry at the metal surface, the light has no reason to.

## What it separates

The 2.2-2.4 min oscillation on colonised electrodes is established. Whether it
is the organism's own rhythm or electrochemistry at a colonised electrode is
not. Removing the organism takes both away at once, so no blank can separate
them. A stimulus the organism responds to and the metal does not is the test.

## Driver

`scripts/stimulus_run.py`. 1 h dark, 1 h blue, 6 pairs, dark first, 12 h.
Intensity 0.50 on the 8 drivable zones. Zone 2 is the barrier and is never
driven. Every transition is timestamped into `data/stimulus_<ts>.jsonl` by the
script that made it; that file defines the block edges for the analysis.

## Pre-registration

`documentation/STATUS.md`, section "Step 9 pre-registration". Statistic,
decision rule, void conditions and exclusions were fixed before the run.

## History

- 2026-09-06 03:21:34 CEST, attempted under run `20260906T012038Z-live`.
  Stopped 03:26:49 after two dark blocks. No blue block ran. The panel was
  showing pixels nothing had commanded. Not a result; the protocol is unused.
