# Bring-up checklist

Replacement Pi 5, serial 62a24b43. Hardware state current to 2026-08-20.

## Working now

| Device | Bus | Status |
|---|---|---|
| ADS1115 | I²C 0x48 | reading, 3 channels differential at 1 Hz, gain 16 |
| SHT31 | I²C 0x44 | reading, ~24.7 °C / 53 %RH |
| WS2812B matrix | GPIO 18 | opens as root, reached via matrixd |
| Camera | CSI | attached, mounted over the dish, 5 min timelapse |
| Noctua fan | BCM 23 relay + BCM 12 PWM | running, 60s in every 300s |

`pinctrl get 2,3` reads `hi` on both; the old board's GPIO 2/3 damage did not
follow to this one.

## Each module runs standalone

System python has the libraries:

```bash
python3 gpio/sensor.py watch     # temperature and humidity
python3 gpio/adc.py watch        # electrode millivolts
python3 gpio/camera.py info      # what camera is attached
sudo python3 gpio/leds.py zones  # matrix zones, needs root
```

## Attaching the Camera Module 3 NoIR

CSI connector is not hot-pluggable. Power down first.

1. `sudo shutdown -h now`, wait for the green LED to stop.
2. Camera Module 3 uses the narrow 22-pin cable at the Pi 5 end, the wide
   15-pin at the camera. Contacts face away from the ethernet port on the Pi,
   toward the board on the camera. Lift the black retainer, seat the ribbon
   square, press the retainer back.
3. Confirm the sensor is seen:
   ```bash
   rpicam-hello --list-cameras     # expect imx708
   python3 gpio/camera.py info
   ```
   Nothing listed means the ribbon, not the software. Reseat both ends.
4. First capture:
   ```bash
   python3 gpio/camera.py shot
   ```
5. With the camera at its final height, set `CAMERA_FOCUS_DIOPTRES` in
   `api/config.py`. `None` sweeps autofocus once at startup and holds it; a
   fixed number is steadier across reboots. Dioptres are 1/metres — a dish
   20 cm below the lens is ~`5.0`.
6. `sudo systemctl restart sllm-api`. `/api/status` then shows
   `"camera": true` and a `camera_model`.

## The matrix daemon

`rpi_ws281x` drives the PWM peripheral through `/dev/mem`, so the panel needs
root. The venv's `board`/`neopixel` also disagrees with the system's
`_rpi_ws281x` C extension (`ws2811_channel_t_gpionum_set, argument 2 of type
'int'`).

Resolved 2026-08-05 with a root-owned helper. `gpio/matrixd.py` owns the panel
and takes commands over `/run/sllm/matrix.sock` (root:sllm, 0660).
`gpio/matrix_client.py` is a `leds.Matrix` work-alike, so `app.py`, `camera.py`
and `loop.py` do not know which they hold. `sllm-api` reports `matrix: true`
while staying unprivileged.

`python3-picamera2` and `python3-numpy` are installed for the system
interpreter so one interpreter has both `picamera2` and `_rpi_ws281x`.

## Admin page and passkeys

`https://sllm.visceral.systems`, **⚙** button bottom-right. Signed in: start and
stop the model loop, start and stop demo mode, switch acquisition between `test`
and `live`.

Authentication is a passkey. The private key stays in the device's secure
element; the server holds only a public key. `user_verification` is REQUIRED.

### Enrolling a device

The first passkey cannot be authorised by a passkey. Enrolment is gated on
shell access to the Pi, which is also the recovery path if every registered
device is lost.

```bash
cd /var/www/sllm
sudo -u sllm ./scripts/py scripts/enrol_passkey.py --label laptop
```

Prints `https://sllm.visceral.systems/?enrol=<token>`. Open it on the device
being registered, click *Register this device*, approve the prompt. The token is
single-use, expires in ten minutes, and is stored only as a SHA-256 hash. It is
spent when a credential verifies, not when the page loads, so a failed attempt
can be retried with the same URL.

Register at least two devices.

```bash
sudo -u sllm ./scripts/py scripts/enrol_passkey.py --list
sudo -u sllm ./scripts/py scripts/enrol_passkey.py --relabel 0 laptop
sudo -u sllm ./scripts/py scripts/enrol_passkey.py --revoke 1
```

**Android.** `excludeCredentials` has been removed from the registration
options — Android's Credential Manager fails on it with "an unknown error
occurred while talking to the credential manager" and nothing reaches the
server. Enrolment errors are generated on the device; check the screen lock and
Play Services before looking at the Pi.

### Sessions

Login returns a bearer token held in browser memory only — not a cookie, not
localStorage. **Reloading the page signs you out.**

## Service accounts

```
sllm-matrixd   root    owns the WS2812B panel. The ONLY privileged process.
sllm-api       sllm    web API. No shell, no home, not in sudo.
sllm-loop      sllm    the model loop.
sllm-demo      sllm    invented data driving the panel. Never enabled at boot.
```

`sllm` is a dedicated system account, not a human login. `chootka` is a member
of the `sllm` group so the standalone tools work by hand; `chootka`'s own sudo
is unchanged.

Starting and stopping units from the web goes through polkit, not sudo.
`sllm-api.service` sets `NoNewPrivileges=true` and sudo is setuid, so the kernel
refuses it; sudo reports this as a container misconfiguration.
`deploy/50-sllm-loop.rules` grants the `sllm` uid exactly `start` and `stop` on
exactly `sllm-loop.service` and `sllm-demo.service`. Everything else returns
"Interactive authentication required".

### Network path

`sllm.visceral.systems` does not resolve to this Pi. It resolves to a
DigitalOcean droplet (`77.42.69.156`, tailnet name `sllm-reverse-proxy`) which
terminates TLS and forwards plain HTTP/1.0 to this box over Tailscale, arriving
from `100.75.40.22`.

1. **Port 80 here is the production path.** Redirecting it to HTTPS gives every
   public visitor an infinite redirect loop.
2. **The proxy sends no `X-Forwarded-Proto` and no `X-Forwarded-For`.** nginx
   synthesises the header from a `geo`/`map` keyed on that tailnet address,
   which cannot be spoofed from outside the WireGuard tunnel. Admin routes
   reject anything not marked https, so plain LAN access to them returns 403.

The droplet terminates TLS and is inside the trust boundary: it sees admin
traffic in the clear and serves the frontend JS. It cannot obtain a passkey or
forge a login; it could steal a live session token.

## Demo mode

`--demo` uses invented data, real light, fast clock.

```bash
sudo systemctl start sllm-demo     # or the admin panel
sudo systemctl stop sllm-demo
```

Refuses to start while acquisition is `live`. Its turns are written to
`data/logs/replay/`. Starting it stops `sllm-loop`, and vice versa — they share
the panel.

**Chamber occupancy is the acquisition mode** (2026-08-08). `live` means a real
session is being recorded; `test` means the chamber is empty. The separate
`data/chamber_occupied` flag was removed.

The interlock is enforced in three places:

1. The `live` button is disabled while a demo runs; the demo `running` button is
   disabled while acquisition is `live`.
2. `POST /api/admin/run` refuses `live` with a 409 while the demo unit is
   active. `POST /api/admin/loop` refuses to start a demo with a 409 while the
   mode is `live`. The endpoints are reachable without the page.
3. `llm/loop.py` refuses `--demo` when it reads the mode as `live`, covering a
   demo started by hand from a shell.

## /logs

`https://sllm.visceral.systems/logs` — live timestamped view of the model's full
note per turn, the action it asked for, the reduced per-channel state, and any
refusal. Polls `/api/turns`.

`sham` and `applied` are redacted in the endpoint, not the template, for anyone
not signed in as admin. A public list of which turns were shams is a channel
back into the loop.

## Diagnosing the panel over a chat session

Observation lag makes traded observations useless: a state described in one
message has moved on by the time the reply arrives.

1. **Hold one state for minutes, not seconds.**
2. **Use raw pixel bands, not zones**, so a mapping mistake cannot look like a
   hardware fault. Stop matrixd first — two processes cannot drive GPIO 18.

   ```bash
   sudo systemctl stop sllm-matrixd
   sudo python3 -c "
   import sys; sys.path.insert(0,'gpio')
   import board, neopixel, time
   px = neopixel.NeoPixel(board.D18, 256, brightness=0.2, auto_write=False)
   px.fill((0,0,0))
   for i in range(0, 32): px[i] = (0,0,255)
   px.show(); time.sleep(30)"
   sudo systemctl start sllm-matrixd
   ```

   Pixels 0-31 are the bottom two rows, 224-255 the top two. `FLIP_Y = True`,
   verified 2026-08-05.
3. **Query the daemon's own state:**

   ```bash
   cd /var/www/sllm && sudo -u sllm ./scripts/py -c "
   import sys; sys.path.insert(0,'gpio')
   from matrix_client import MatrixClient
   print(MatrixClient().active_zones())"
   ```

Barrier zone lit and nothing else is the correct resting state.
`active_zones()` excludes the barrier, so `{}` means barrier only.

## Running the loop

`sllm-api`, `sllm-loop` and `sllm-matrixd` are enabled. `sllm-demo` is not.

```bash
sudo systemctl start sllm-loop      # begin
sudo systemctl stop sllm-loop       # end, clears the stimulus on the way out
systemctl is-active sllm-loop       # is the experiment running
journalctl -u sllm-loop -f          # watch turns as they happen
```

SIGTERM unwinds through loop.py's handler and clears the last zone. SIGKILL
skips the cleanup and leaves the zone lit until matrixd shuts down.

Turn interval and sham rate for a service run: `LLM_TURN_INTERVAL` and
`LLM_SHAM_RATE` in `api/config.py`. The unit passes no flags. Run in the
foreground for command-line flags.

## The model loop

`llm/loop.py` is the live version of `llm/filters/harness.py`. It imports the
reducer and the prompts rather than copying them.

Ollama runs on the laptop (`chootka-pro`, Tailscale `100.127.41.6`).

**On the Mac, once:**

```bash
launchctl setenv OLLAMA_HOST 0.0.0.0     # then restart Ollama
ollama pull qwen2.5:14b
```

**On the Pi — run from the deployed tree, not the checkout:**

```bash
cd /var/www/sllm
./scripts/py llm/loop.py --check       # is the model reachable, is there a window
./scripts/py llm/loop.py --dry-run     # full loop, never drives the matrix
./scripts/py llm/loop.py               # live -- no sudo, matrixd owns the panel
```

No sudo. `sllm-loop.service` runs `api/venv/bin/python llm/loop.py` as `sllm`.

For a hardware smoke test add `--sham-rate 0 --interval 30`. At the default
0.25, one turn in four is not applied and looks like a dead matrix.

The loop reads the CSV that `sllm-api.service` writes under `/var/www/sllm/data`.
Run from `~/sllm` it resolves its own empty data directory and reports
`0 samples`. Replay runs work from either tree.

### Replay

`--replay` slides the loop along a fixed session; `--speed` compresses the
clock. Twelve turns that would take two hours run in about two seconds. Replay
implies `--dry-run` and writes to `data/logs/replay/`.

```bash
./scripts/py llm/loop.py --replay synthetic --speed 600 --turns 24
./scripts/py llm/loop.py --replay data/readings/electrodes_20260805.csv --speed 600
```

Synthetic sessions plant one event — the period lengthens 90s to 140s across
turns 10 to 14 — and log it next to the model's note. Any other event the model
reports is its own invention.

### Prompt variants

`LLM_PROMPT` picks one of five, parsed out of `llm/filters/prompts.md` by
`llm/filters/prompts.py`. Harness and loop read the same file.

| variant | what the model is told |
|---|---|
| `blind` | the interface and nothing else |
| `informed` | that it is coupled to Physarum, plus the zone map |
| `adversarial` | that its context is finite and the organism consumes it |
| `mimic` | nothing — it is given Physarum's architecture instead |
| `null` | describe only, no actions; the model noise floor |

`adversarial` changes loop behaviour, not just wording. It pins `num_ctx`
(32768 unless `LLM_NUM_CTX` is set), stops truncating history, and sends the
compact state so a quiet channel drops its coarse trace. All three or none.

The loop stops when the context fills rather than letting Ollama evict the
oldest turns. It budgets off the conversation it builds itself.

```bash
./scripts/py llm/loop.py --prompt adversarial --num-ctx 4096 --replay synthetic --speed 600
```

### Sham blocks

`LLM_SHAM_RATE` (default 0.25) is the fraction of turns where the action is
logged and not applied. The model is never told which. `sham` and `applied` are
recorded per turn in the JSONL and never enter a prompt.

If the matrix cannot be driven the loop refuses to start. Pass `--dry-run` to
run anyway.

### What gets written

```
data/readings/electrodes_YYYYMMDD.csv     1 Hz, one row per sample, mV
data/readings/environment_YYYYMMDD.csv    1 Hz, temperature C and F, RH
data/logs/turns_YYYYMMDD.jsonl            one record per turn, live runs
data/logs/replay/turns_YYYYMMDD.jsonl     replay and dry runs
```

Daily files, UTC. The turn record holds the reduced state, the model's full
reply, the validated action, `sham`, `applied`, any refusal reason, and Ollama's
token `usage`. Under `adversarial` it also carries `context_used`.

The logged state includes `period_depth` per channel, which the model never
sees. `MIN_DEPTH` in `reducer.py` is calibrated against it.

## Deploying

```bash
sudo ./scripts/deploy_on_pi.sh              # code + config, restarts sllm-api
sudo ./scripts/deploy_on_pi.sh --dry-run    # what would change, no side effects
sudo ./scripts/deploy_on_pi.sh --deps       # also pip install, when requirements moved
sudo ./scripts/deploy_on_pi.sh --no-restart # stage it, restart nothing
```

`deploy/` is the source of truth for everything outside the code: the four
systemd units, the nginx site, and the polkit rule. The script installs each
only when it differs from what is live.

What the script does not do:

1. **Does not generate unit files.** Generated units carried `User=chootka` and
   none of the hardening.
2. **Does not install `etc/nginx.conf`.** That file is deleted. The live config
   is `deploy/nginx-sllm.visceral.systems.conf`, validated with `nginx -t`
   before reload.
3. **Does not restart `sllm-matrixd`, `sllm-loop` or `sllm-demo`.** Bouncing
   matrixd blanks the panel including the barrier zone; starting the loop puts
   light into the chamber. If a unit file for one of them changed, the script
   reports it and leaves it.

`QUICK_DEPLOY.md` and `DEPLOY_NOW.md` are deleted. This section is the
deployment doc.

## After a reboot

`sllm-api.service` restarts on boot, so sampling and logging resume.

```bash
systemctl is-active sllm-api            # should be: active
sudo i2cdetect -y 1                     # 44 and 48
curl -s localhost/api/status | python3 -m json.tool
tail -3 data/readings/electrodes_*.csv  # is it still logging
git -C ~/sllm log --oneline -5          # what was done
```

Check `data/recovery.json`: with recovery on, the panel is held dark and the
loop refuses a live run.

## Still to build

- **Clean empty-dish baseline.** Electrodes in agar, nothing alive,
  undisturbed, two hours minimum. `MIN_DEPTH` in `llm/filters/reducer.py` is a
  placeholder until it exists.
- **Even IR backlighting.** ~23:1 gradient, bottom-right quadrant clipped. See
  `hardware_setup.md`. Measure with `scripts/flatfield.py`.
- **A control for ADVERSARIAL.** Identical context pressure attributed to
  something neutral rather than the organism.
- **Timelapse frames are not run-labelled.** CSVs and turn logs carry `run_id`
  and `mode`; images land in one directory with neither.
- **`/dev/media3: Operation not permitted`** in the API log. The `DeviceAllow`
  list in `deploy/sllm-api.service` stops at `media2`. Camera works regardless.
