# Start here — 2026-08-06

Written at the end of the 2026-08-05 evening session. Read this before anything
else, then `bring_up.md` for how things work.

---

## 1. The unresolved thing — and it is the experiment, not a detail

**The requirement:** the model's decisions must visibly light zones on the
matrix. Two ways of running it, both needed:

- **live**, at the real cadence, driven by real electrode data — this *is* the
  installation; without it there is nothing
- **demo**, sped up, driven by invented data, for showing people

Neither has been seen working as a sequence. Until it is, there is no
experiment. Treat this as blocking everything else, including the electrodes.

**Do this first. It should take ten minutes, not hours.**

The cause is **unknown**. Do not act on any proposed fix — there isn't one yet.

### What is already established (don't re-test)

- **All nine zones light** when set individually through `matrixd`. Verified one
  at a time, held, with everything else stopped.
- The panel, `matrixd`, and the zone→pixel mapping are all correct. The mapping
  provably tiles all 256 pixels exactly once.
- Demo **can** drive the panel: zone 8 at 18:46 PDT was seen and matched the
  daemon log to the second.

### What is not explained

During a demo run the daemon logged zones changing — centre, top-centre,
mid-right, bottom-centre, mid-left — while almost none of it was visible.

### The experiment that has never actually been run cleanly

```bash
sudo systemctl stop sllm-loop            # it overwrites the panel every turn
systemctl is-active sllm-loop sllm-demo  # both must be inactive
sudo systemctl start sllm-demo
```

Then **watch the panel continuously for three minutes without messaging Claude**,
and write down the sequence of positions. Afterwards:

```bash
sudo journalctl -u sllm-demo --no-pager | grep "turn "
```

Compare the two lists. Every previous attempt was contaminated — by test scripts
Claude killed with a stray `pkill`, by `sllm-loop` running and overwriting manual
tests, or by trying to compare observations in real time across a message delay
of several minutes.

### Rules that made this take hours

- **Stop `sllm-loop` and `sllm-demo` before any manual panel test.** Every turn
  calls `clear_stimulus()` and takes the panel.
- **Never try to sync observations in real time.** Messages arrive minutes late.
  Hold one state for minutes, or publish a wall-clock schedule in advance.
- Zone intensity below ~1.0 is barely brighter than the always-on barrier
  (`STIM_BRIGHTNESS` is 0.25, so 0.5 intensity ≈ 31/255). Test at 1.0.

---

## 2. Other open items, none blocking

- **Timelapse gets stuck.** Captures stop, `last_error` stays `null`, so it is
  blocking rather than failing — probably inside `capture_flash`. This is the
  most substantive real bug left.
- **Images are not run-labelled.** CSVs and turn logs carry `run_id`/`mode`;
  timelapse frames still land in one directory with no mode.
- **`/dev/media3: Operation not permitted`** noise in the API log. The
  `DeviceAllow` list in `sllm-api.service` misses it. Camera works regardless.
- **The red imaging flash is a periodic confound.** Every capture flashes red
  over the chamber at the same 300s cadence, and the model is never told. The
  IR-in-the-lid idea removes it. Worth settling before the empty-chamber run.

---

## 3. What works (built and verified 2026-08-05)

- **Fan** — BCM 23 relay (active-high) + BCM 12 PWM held high. 60s in every 300s.
- **Matrix behind a root-owned helper** — `sllm-matrixd` owns the panel; the API
  is unprivileged and hardened. Admin actions go through polkit, not sudo.
- **Dedicated `sllm` service account** — no shell, no home, not in sudo.
- **Passkey admin** on the ⚙ button, two devices enrolled (laptop, flipz).
- **`/logs`** — live turn view. `sham`/`applied` withheld unless signed in.
- **Run labelling** — every reading carries `run_id` and `mode` (`test`/`live`);
  non-live modes write to their own directory.

## 4. Commands

```bash
# state
systemctl is-active sllm-matrixd sllm-api sllm-loop sllm-demo
curl -s localhost/api/status | python3 -m json.tool

# the experiment
sudo systemctl stop sllm-loop && sudo systemctl start sllm-demo
sudo journalctl -u sllm-demo -f

# what the panel actually holds
cd /var/www/sllm && sudo -u sllm ./scripts/py -c "
import sys; sys.path.insert(0,'gpio')
from matrix_client import MatrixClient
print(MatrixClient().active_zones())"

# passkeys
sudo -u sllm ./scripts/py scripts/enrol_passkey.py --list
```

`active_zones()` excludes the barrier, so `{}` means "barrier only" — the
correct resting state.

## 5. Not pushed

19 commits sit on `main`, local only. Nothing has been pushed to GitHub.
