# Electrode rebuild — ordered plan

Goal: establish whether a bio signal exists. Written 2026-08-22.

Total elapsed: ~2 days, of which ~95 min is hands-on.

## Bench work

| # | step | time | done |
|---|---|---|---|
| 1 | Shorted-lead test | 30 min (mostly waiting) | ☐ |
| 2 | Foil shield on the top box | 30 min | ☐ |
| 3 | Build agar islands | 30 min | ☐ |
| 4 | Verify island isolation | 5 min | ☐ |

**1 — Shorted-lead test.** Tie Board A rows r38L, r40L, r40R, r38R into one
node (MCP604 pins 3, 5, 10, 12). Clip onto the 10 MΩ resistor legs; do not
solder, do not touch row 39 (VDD/VSS). Verify with a multimeter across r38L to
r40R — near 0 Ω, not 20 MΩ. Settle 1 min, then **record 20-30 min**, not a few
minutes — drift is the point, not offset.

Compare against the settled beaker figures at 8 SPS: **+2.38 / -0.61 / -2.65
mV**, ch2 wandering ~2.7 mV over 20 min.

| shorted result | means |
|---|---|
| same offsets as the beaker | op-amp offset, tips contribute nothing |
| ≈0 mV | the 2-3 mV is electrode mismatch; re-plating goes on the later list |
| ch2 still drifts ~2.7 mV | board or that buffer channel |
| ch2 flat | the drift is the ch2 tip; re-plate that one alone |

Does not gate step 3 — a few mV of DC offset does not hide a slow oscillation.

**Check the overnight beaker record before running this.** The ch2 wander was
measured ~50 min after immersion while all three channels were still
converging, so it may be settling rather than drift. Eight hours in the same
beaker settles the question at no cost. If ch2 is flat by morning there is
nothing to attribute and step 1 is only about offset.

**2 — Foil shield.** Wrap the outside of the top box, not the inside. One
ground wire to the board GND rail, one point only, not mains earth.

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
