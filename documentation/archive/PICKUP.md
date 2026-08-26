# Pick up here — written 2026-08-24 03:00 CEST

> **Superseded in part by `session_20260826.md`** (2026-08-26 04:00 CEST).
> The bridge time is found, both bridges are recorded, and a 2.2-2.4 min
> oscillation is established on ch1 and ch2. Read that file first.

## Read first

1. `session_20260824.md` — what was done today, with timeline
2. `method_basis.md` — why, with the Adamatzky/Whiting citations
3. `rebuild_plan.md` — the punch list; steps 1-4 now closed

## Running right now, do not disturb

| | |
|---|---|
| run | `20260824T004220Z-live`, started 2026-08-24 02:42 CEST |
| file | `/var/www/sllm/data/readings/electrodes_20260824.csv` |
| mode | `live` |
| recovery | ON — panel dark, LEDs blocked, `sllm-loop` held off |
| services | `sllm-api` active, `sllm-loop` inactive (correct) |
| chamber | 26.0 C, 97.5% RH |
| timelapse | running, 300 s interval |

Organism inoculated on the reference island ~02:40 CEST.

## First thing tomorrow

**Find the bridge time.** Scan the timelapse in `data/images/` for the first
protoplasmic tube reaching any recording island. The 24 h clock starts there,
not at inoculation. 36 h maximum. Record the time in `session_20260824.md`
under Timeline — the row is waiting.

Then check the record for:

- **The pre-bridge window** — this is a free blank. Recording islands have agar
  and electrodes but no organism until the bridge. Use it as the noise floor for
  those channels. Caveat: the reference has organism from t=0 and every channel
  is E - REF, so it is a blank for the recording sites only.
- **Bridging by condensation.** If islands short, channels collapse toward each
  other: inter-channel offsets shrink, pairwise correlation rises toward 1. Find
  when it happens and cut the analysis there. No multimeter needed.
- **Discount the first ~8 h.** Adamatzky and Jones report an ~8 h transient
  before regular oscillation appears.

## What to expect

| feature | value |
|---|---|
| main oscillation | 30-40 min period, 4-5 mV |
| slower band | 50-70 min, 3 mV |
| high-frequency band | 1-2 min, 2-3 mV, superimposed |
| sclerotium, i.e. drying failure | rise toward 50 mV |

Measured noise floor is 0.026-0.060 mV, so signal to noise is 50-200x.

**A signal identical on all three channels is the shared reference moving, not
the organism.** This already fooled us once — the earlier ~50 s rhythm.

## Then step 7, revised

Organism out, `test` mode. Two changes from the written plan:

- Fresh agar blobs are unavoidable — the organism cannot be selectively removed
  from colonised islands.
- Fresh agar means a settling transient. Beaker settling took 6-12 h. **Run
  18-24 h, not the 6 h in the plan, and discard the first half.**

## Open decision — RESOLVED 2026-08-26

`rebuild_plan.md` step 5 states the artifact criterion as "a clean 60-200 s
oscillation with no organism means artifact". This note previously said that
range was wrong and should be restated for 30-40 min, on the assumption the
signal would be in the 30-40 min band. **That assumption was wrong.** The
signal found on 2026-08-26 is at 2.2-2.4 min, i.e. 130-145 s, inside 60-200 s.
The criterion is aimed correctly; do not widen it.

What step 5 does still need is a threshold fixed in advance instead of the word
"clean", and an acknowledgement that the blank in use is the pre-bridge window
of run 6, not a separate recording. See `session_20260826.md`.

## Gotchas that cost time today

- `POST /api/admin/run` returns **401** when not logged in to the admin panel.
  The mode switch silently does not take. Check `run.json` after switching.
- Unclean shutdown leaves **NUL bytes** in the CSVs. Skip lines containing NUL
  when parsing.
- Reading files: services run from `/var/www/sllm`, **not** `~/sllm`. Docs are
  edited in `~/sllm/documentation`.
- Board A resistor legs are trimmed flush. Ties are wire scraps in r38L, r38R,
  r40L, r40R. Nothing to clip.
