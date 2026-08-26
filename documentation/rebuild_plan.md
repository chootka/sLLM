# Electrode rebuild — ordered plan

Goal: establish whether a bio signal exists. Written 2026-08-22.

Total elapsed: ~2 days, of which ~95 min is hands-on.

## Bench work

| # | step | time | done |
|---|---|---|---|
| 1 | Shorted-lead test | 30 min (mostly waiting) | ☐ |
| 2 | Foil shield on the top box — OPTIONAL, not indicated | 30 min | ☐ |
| 3 | Build agar islands | 30 min | ☐ |
| 4 | Verify island isolation | 5 min | ☐ |

**1 — Shorted-lead test.** Tie Board A rows r38L, r40L, r40R, r38R into one
node (MCP604 pins 3, 5, 10, 12). The 10 MΩ resistor legs are trimmed flush to
the board — nothing to clip. Tie with wire scraps in r38L, r38R, r40L, r40R. Do
not solder, do not touch row 39 (VDD/VSS). Verify with a multimeter across r38L to
r40R — near 0 Ω, not 20 MΩ. Settle 1 min, then **record 20-30 min**, not a few
minutes — drift is the point, not offset.

**RESOLVED 2026-08-24. Step 1 done, 27 min recorded.**

| | shorted | settled beaker |
|---|---|---|
| ch0 | -1.72 | -3.71 |
| ch1 | -1.45 | -3.77 |
| ch2 | -2.32 | -4.01 |

Drift over 27 min shorted: ch0 +0.025, ch1 +0.004, ch2 +0.031 mV. Flat.

The earlier "ch2 wanders 2.7 mV / 20 min" claim is **withdrawn**. It came from a
20 min window taken ~50 min after immersion, inside the settling transient. The
26 h record shows all three converging to within 0.35 mV and flattening. Nothing
to attribute, no re-plating.

Method note: never attribute drift from a window shorter than the settling time.
A 20 min sample cannot distinguish drift from settling when settling runs hours.

Channel offsets are stable and do not matter — ch2-ch0 range 0.053 mV across the
settled hours. Buffers are unity gain, so amplitudes stay comparable across
channels regardless of zero point.

**2 — Foil shield. OPTIONAL — measurement says it is not needed.** In-solution
high-frequency noise is at or below the shorted-lead floor (ch0 0.026 vs 0.037,
ch1 0.026 vs 0.020, ch2 0.060 vs 0.182 mV), so the chamber is not picking up.
No day/night pattern across 26 h (ch2 0.040-0.096 mV). ADS1115 at 8 SPS already
notches 50/60 Hz. Measured 2026-08-24.

If ever done: wrap the outside of the top box, not the inside. One ground wire
to the board GND rail, one point only, not mains earth.

**3 — Agar islands.** Per `hardware_setup.md`:

- One island of non-nutrient 2% agar per electrode, bare dish floor between
  them, gaps ~10 mm.
- Reference island at the centre. Plasmodium is inoculated **on the reference
  island**, following Whiting 2014 and Adamatzky and Jones 2011.
- All four tips flat on the dish floor under their blob, at one depth.
- Bare oat flake on each recording island.

The barrier zone is dropped. Its purpose was keeping the plasmodium off the
reference, which is the opposite of the published method.

**4 — Verify isolation.** Multimeter between electrode pairs. Megohms or open
is correct. kΩ means agar is still bridging — find it before recording.

## Recording

LEDs off throughout. `sllm-loop` stays off.

| # | step | mode | duration | done |
|---|---|---|---|---|
| 5 | Noise floor, no organism | `test` | 12 h | ☐ |
| 6 | Organism in | `live` | 24 h, 36 max | ☐ |
| 7 | Organism removed | `test` | 6 h | ☐ |

**5** calibrates `MIN_DEPTH` in `llm/filters/reducer.py`, which is what left
growth-run test 2 unrun. A clean 60–200 s oscillation here with no organism
present means artifact, and the rig is not ready.

**6** — the 24 h counts from when the tube bridges, not from inoculation.
Whiting reports rhythm within ~30 min of a healthy tube bridging. Watch the
timelapse for the bridge; if it is slow, run to 36 h so there is still a full
day of post-bridge record.

**7** — same measurement as 5, either side of the organism. Compare against an
equal-length window from 6, not the whole run.

## Not now

- **LLM loop.** Nothing to close a loop around until 6 produces a signal.
- **Matrix repair.** Unplugged, shorted on condensation. LEDs are off for
  5–7 anyway. Any rebuild needs it sealed against condensation.
- **Re-plating electrodes.** Depends on step 1.
- **True differential pair (0-1, 2-3).** The `growth_run.md` follow-on. Do it
  after 5–7, not with them — changing geometry and mux at once makes the
  common-mode result uninterpretable. Re-measure common-mode share on the
  island geometry first.

## Done 2026-08-22

**ADC data rate 8 SPS**, deployed and live. Noise floor fell from 0.7-2.8 mV sd
to 0.045-0.109 mV — 15-35x. See `hardware_setup.md`.

This lowers the priority of step 2: most of the noise was the conversion
window, not pickup. Still worth an A/B, but no longer the main lever.
