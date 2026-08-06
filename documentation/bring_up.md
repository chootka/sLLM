# Bring-up checklist

State as of 2026-08-05, on the replacement Pi 5 (serial 62a24b43).

## Working now

| Device | Bus | Status |
|---|---|---|
| ADS1115 | I²C 0x48 | reading, 3 channels differential at 1 Hz, gain 16 |
| SHT31 | I²C 0x44 | reading, ~24.7 °C / 53 %RH |
| WS2812B matrix | GPIO 18 | opens as root; **not** reachable from the API, see below |
| Camera | CSI | attached and capturing, but aimed at the ceiling |
| Noctua fan | BCM 23 relay + BCM 12 PWM | running, 60s in every 300s |

The GPIO 2/3 damage on the old board did not follow to this one:
`pinctrl get 2,3` reads `hi` on both, and both devices enumerate.

## Each module runs standalone

No API needed, and system python has the libraries:

```bash
python3 gpio/sensor.py watch     # temperature and humidity
python3 gpio/adc.py watch        # electrode millivolts
python3 gpio/camera.py info      # what camera is attached
sudo python3 gpio/leds.py zones  # matrix zones, needs root
```

## Attaching the Camera Module 3 NoIR

Power the Pi down first — the CSI connector is not hot-pluggable.

1. `sudo shutdown -h now`, wait for the green LED to stop.
2. Camera Module 3 uses the **narrow 22-pin** cable at the Pi 5 end and the
   wide 15-pin at the camera. Contacts face **away** from the ethernet port on
   the Pi, and toward the board on the camera. Lift the black retainer, seat
   the ribbon square, press the retainer back.
3. Boot, then confirm the sensor is seen before anything else:
   ```bash
   rpicam-hello --list-cameras     # expect imx708
   python3 gpio/camera.py info
   ```
   Nothing listed means the ribbon, not the software. Reseat both ends.
4. First capture:
   ```bash
   python3 gpio/camera.py shot
   ```
   Without the matrix this captures with no backlight, which is fine for
   checking focus and framing.
5. Once the camera is mounted at its final height, set
   `CAMERA_FOCUS_DIOPTRES` in `api/config.py`. Leaving it `None` sweeps
   autofocus once at startup and holds it, which is usually good enough; a
   fixed number is steadier across reboots. Dioptres are 1/metres, so a dish
   20 cm below the lens is about `5.0`.
6. Restart the API so it picks the camera up: `sudo systemctl restart sllm-api`.
   `/api/status` should then show `"camera": true` and a `camera_model`.

## The matrix is not reachable from the API

`gpio/leds.py` works under `sudo` with system python. It does **not** work
from the API, for two independent reasons:

1. **Root.** `rpi_ws281x` drives the PWM peripheral through `/dev/mem`.
   `sllm-api.service` runs as `chootka`.
2. **Split Blinka.** The venv has its own `board`/`neopixel`, while the C
   extension `_rpi_ws281x` only exists in `/usr/local/lib/python3.13/
   dist-packages`. Mixing them gives
   `ws2811_channel_t_gpionum_set, argument 2 of type 'int'`.

**Update 2026-08-05:** `python3-picamera2` and `python3-numpy` are now
installed for the system interpreter, which previously had neither. That
matters twice over. It removed a second symptom of the same split — before it,
no single interpreter had both `picamera2` and `_rpi_ws281x`, so the
blank/flash capture sequence could not run at all. And it makes option 2 below
cheap, because system python can now run the entire stack.

Until this is resolved the API starts fine and reports `"matrix": false`,
captures happen without the red backlight, and `/api/trigger-light` returns
503. Nothing else is affected.

Three ways out, in increasing order of effort and decreasing order of risk:

- **Run the API as root.** One line in the unit file. Fixes it immediately,
  but the whole Flask app, including the routes reachable through nginx, then
  runs privileged.
- **Use system python for the service** instead of the venv, and run as root.
  Removes the split-Blinka half of the problem too, but abandons the pinned
  dependency set.
- **A small root-owned matrix helper** that owns the panel and takes commands
  over a unix socket, with the API staying unprivileged. Most work, and the
  only option that does not put a web server on root.

The red imaging flash is required for the capture sequence to mean anything,
so this has to be settled before the timelapse is scientifically useful. It
does not block attaching the camera or checking focus.

## The admin page, and how a passkey gets enrolled

`https://sllm.visceral.systems` has a **⚙** button in the bottom-right corner.
Signed in, it starts and stops the model loop, starts and stops demo mode, and
sets whether the chamber is occupied.

Authentication is a **passkey**, not a password. There is no shared secret in
this system at all: the private key stays in your device's secure element and
the server holds only a public key. Nothing to brute-force, nothing to leak out
of config.py, and nothing phishable -- the credential is cryptographically
bound to the origin, so a lookalike domain cannot elicit a usable assertion.
`user_verification` is REQUIRED, so an unlocked device is not enough; the
authenticator must check the human.

### Enrolling a device

The first passkey cannot be authorised by a passkey, so enrolment is gated on
being able to get a shell on the Pi. **That SSH access is the root of trust,
and it is also the recovery path** if every registered device is lost.

```bash
cd /var/www/sllm
sudo -u sllm ./scripts/py scripts/enrol_passkey.py --label laptop
```

It prints a URL of the form `https://sllm.visceral.systems/?enrol=<token>`.
Open that **on the device being registered**, the admin panel opens itself,
click *Register this device*, approve the prompt. The token is single-use,
expires in ten minutes, and is stored only as a SHA-256 hash -- the printed
value is the only time it exists in the clear. It is spent when a credential
actually verifies, not when the page loads, so a failed attempt can be retried
with the same URL.

Register **at least two devices**. One passkey means one lost phone locks you
out of the web controls.

```bash
sudo -u sllm ./scripts/py scripts/enrol_passkey.py --list
sudo -u sllm ./scripts/py scripts/enrol_passkey.py --relabel 0 laptop
sudo -u sllm ./scripts/py scripts/enrol_passkey.py --revoke 1
```

**Android note.** Registering on a Samsung phone failed with "an unknown error
occurred while talking to the credential manager", with nothing reaching the
server to explain it. The cause was `excludeCredentials` in the registration
options, which Android's Credential Manager handles badly. It has been removed:
its only job was to stop the same authenticator registering twice, which is
harmless. If a device fails to enrol, the error is generated entirely on the
device -- check the screen lock and Play Services before looking at the Pi.

### Sessions

A successful login returns a bearer token held **in browser memory only**. Not
a cookie, because a cookie is attached to every request to this origin and that
is what makes CSRF possible; an Authorization header cannot be set by
cross-origin script, so CSRF is structurally impossible rather than mitigated.
Not localStorage either, because that survives the tab and any XSS could
harvest it later.

The practical consequence: **reloading the page signs you out.** That is the
intended trade for a control that puts light into a chamber.

## Why the API is not root, and what runs as what

```
sllm-matrixd   root    owns the WS2812B panel. The ONLY privileged process.
sllm-api       sllm    web API. No shell, no home, not in sudo.
sllm-loop      sllm    the model loop.
sllm-demo      sllm    invented data driving the panel. Never enabled at boot.
```

`sllm` is a dedicated system account, not a human login. The API is reachable
from the internet, so whatever it runs as is what an attacker gets on a bad
day. It used to run as `chootka`: SSH keys, git credentials, sudo group
membership, and a shell profile that could be rewritten to capture a sudo
password the next time you typed one. As `sllm` the blast radius is the data
directory and two systemd units. `chootka` is a member of the `sllm` group so
the standalone tools still work by hand; `chootka`'s own sudo is unchanged.

The panel needs `/dev/mem`, which needs root -- so it lives behind
`gpio/matrixd.py`, a small daemon speaking a fixed vocabulary over a unix
socket at `/run/sllm/matrix.sock` (root:sllm 0660). `gpio/matrix_client.py`
presents the same methods as `leds.Matrix`, so nothing else knows the
difference.

Starting and stopping units from the web goes through **polkit**, not sudo.
This is not a preference: `sllm-api.service` sets `NoNewPrivileges=true` and
sudo is setuid, so the kernel refuses it outright. sudo reports that as a
container misconfiguration, which is misleading -- it is the hardening working.
`deploy/50-sllm-loop.rules` grants the `sllm` uid exactly `start` and `stop` on
exactly `sllm-loop.service` and `sllm-demo.service`. Everything else returns
"Interactive authentication required".

### The network is not what it looks like

`sllm.visceral.systems` does **not** resolve to this Pi. It resolves to a
DigitalOcean droplet (`77.42.69.156`, tailnet name `sllm-reverse-proxy`) which
terminates TLS and forwards plain HTTP/1.0 to this box over Tailscale, arriving
from `100.75.40.22`.

Two consequences that cost time to discover:

1. **Port 80 here is the production path.** Redirecting it to HTTPS produces an
   infinite redirect loop for every public visitor. I did that and had to
   revert it inside a minute.
2. **The proxy sends no `X-Forwarded-Proto` and no `X-Forwarded-For`**, so this
   box cannot otherwise tell a request that arrived over public HTTPS from a
   plaintext one on the studio LAN. nginx now synthesises the header from a
   `geo`/`map` keyed on that tailnet address, which cannot be spoofed from
   outside the WireGuard tunnel. Admin routes reject anything not marked https,
   so plain LAN access to them returns 403.

Note also that the droplet terminates TLS, which puts it inside the trust
boundary: it sees admin traffic in the clear and serves the frontend JS. It
cannot obtain a passkey or forge a login, but it could steal a live session
token. That is inherent to any TLS-terminating proxy.

## Demo mode: watching the hardware without waiting

The live loop cannot be sped up without being made meaningless. The 30 minute
window and the 10 minute turn come from Physarum's contraction period, not from
caution. `--replay` is fast but deliberately refuses to actuate. So there was
no way to watch a zone go on and off.

`--demo` is the exception: invented data, real light, fast.

```bash
sudo systemctl start sllm-demo     # or the admin panel
sudo systemctl stop sllm-demo
```

It refuses to start while the chamber is marked occupied, and its turns are
written to `data/logs/replay/` where they cannot be confused with a real
session. Starting it stops `sllm-loop`, and vice versa -- they share the panel.

**Chamber occupancy** is asserted by a human, because nothing can detect it. It
is the presence of a file (`data/chamber_occupied`), toggled from the admin
panel and read fresh on every check -- deliberately not a line in config.py,
because a safety flag that needs an SSH session and a service restart is one
that will be stale exactly when it matters.

## /logs

`https://sllm.visceral.systems/logs` is a live, scrollable, timestamped view of
what the model is thinking: its full note per turn, the action it asked for,
the reduced per-channel state, and any refusal. It polls `/api/turns`.

**`sham` and `applied` are withheld from anyone not signed in as admin**, and
the redaction happens in the endpoint rather than the template, so the fields
never reach a public browser at all. This is not tidiness: the experiment
depends on the model not knowing which turns are controls, and a public list of
which turns were shams is a channel straight back into the loop the moment it
is quoted at the model or scraped into something the model later reads.

## Diagnosing the panel over a chat session: read this first

A large part of the night of 2026-08-05 was spent chasing a hardware fault on
the LED panel that did not exist. The panel was fine the whole time.

The cause was **observation lag**. I would set a zone, describe it, and by the
time that message was read the state had already moved on; the reply described
a different instant than the question. We compared notes across several minutes
of drift and concluded half the chain was dead. It was not.

If the panel ever looks wrong, do this instead of trading observations:

1. **Hold one state for minutes, not seconds.** Set it, then stop touching it.
2. **Use raw pixel bands, not zones**, so a mapping mistake cannot masquerade as
   a hardware fault. Stop matrixd first -- two processes cannot drive GPIO 18.

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

   Pixels 0-31 are the **bottom** two rows, 224-255 the **top** two. That is
   `FLIP_Y = True`, verified again on 2026-08-05.
3. **Trust the daemon's own state**, queryable from any client, over anyone's
   recollection of what the panel looked like:

   ```bash
   cd /var/www/sllm && sudo -u sllm ./scripts/py -c "
   import sys; sys.path.insert(0,'gpio')
   from matrix_client import MatrixClient
   print(MatrixClient().active_zones())"
   ```

The barrier zone being lit and nothing else IS the correct resting state.
`active_zones()` deliberately excludes the barrier, so `{}` means "barrier only".

## The three services, and which one is the experiment

```
sllm-matrixd   root    owns the WS2812B panel, unix socket at /run/sllm/matrix.sock
sllm-api       chootka sampling, logging, camera timelapse, fan. A matrixd client.
sllm-loop      chootka THE MODEL LOOP. Off unless you start it.
```

The first two start at boot. **`sllm-loop` does not**, deliberately: the model
driving light into a chamber is something to start on purpose, not something
that resumes because the power blinked.

```bash
sudo systemctl start sllm-loop      # begin
sudo systemctl stop sllm-loop       # end, clears the stimulus on the way out
systemctl is-active sllm-loop       # is the experiment running
journalctl -u sllm-loop -f          # watch turns as they happen
sudo systemctl enable sllm-loop     # only when it should survive a reboot
```

Stopping is safe: SIGTERM unwinds through loop.py's handler so the last zone
the model chose is cleared. Killing it with SIGKILL is not — that skips the
cleanup and leaves the zone lit, and only matrixd's own shutdown would blank it.

To change the turn interval or the sham rate for a service run, edit
`LLM_TURN_INTERVAL` and `LLM_SHAM_RATE` in `api/config.py`; the unit passes no
flags so the config is the only knob. Run it in the foreground instead when you
want the command-line flags.

## The model loop

`llm/loop.py` is the live version of `llm/filters/harness.py`. It imports the
reducer and the prompts rather than copying them, so the replay harness stays
evidence about what the live loop actually does.

Ollama runs on the laptop (`chootka-pro`, Tailscale `100.127.41.6`), not here.

**On the Mac, once:** Ollama binds `127.0.0.1` by default and will refuse the
Pi until told otherwise.

```bash
launchctl setenv OLLAMA_HOST 0.0.0.0     # then restart Ollama
ollama pull qwen2.5:14b
```

**On the Pi — run the loop from the deployed tree, not the checkout:**

```bash
cd /var/www/sllm
./scripts/py llm/loop.py --check       # is the model reachable, is there a window
./scripts/py llm/loop.py --dry-run     # full loop, never drives the matrix
sudo python3 llm/loop.py               # live -- system python, NOT ./scripts/py
```

**A live run must use system `python3`, not `./scripts/py`.** The venv cannot
drive the panel: it fails with `ws2811_channel_t_gpionum_set, argument 2 of
type 'int'`, and the loop then refuses to start rather than running as a silent
permanent sham. The system interpreter has `numpy`, `requests`, `picamera2` and
`_rpi_ws281x` together, so it can do the whole job.

For a hardware smoke test, add `--sham-rate 0 --interval 30`. At the default
sham rate of 0.25 roughly one turn in four is deliberately not applied, which
looks exactly like a dead matrix and will have you debugging working hardware.

The loop reads the CSV that `sllm-api.service` writes, and the service writes
under `/var/www/sllm/data`. Run from `~/sllm` it resolves its own, empty data
directory and reports `0 samples` — which looks exactly like a dead ADC and
is not. Replay runs are fine from either tree, since they bring their own
data.

### Testing without waiting on the organism

`--replay` slides the loop along a fixed session and `--speed` compresses the
clock. Twelve turns that would take two hours run in about two seconds. Replay
always implies `--dry-run`, and its turns are written to `data/logs/replay/`
so synthetic rows never land in the real record.

```bash
./scripts/py llm/loop.py --replay synthetic --speed 600 --turns 24
./scripts/py llm/loop.py --replay data/readings/electrodes_20260805.csv --speed 600
```

Synthetic sessions plant one event — the period lengthens 90s to 140s across
turns 10 to 14 — and log it next to the model's note. Any other event the
model reports is its own invention. A real recording cannot tell you that,
because you do not know what was in it; it can tell you how the loop behaves
on real noise. Both are worth running.

### Sham blocks

`LLM_SHAM_RATE` (default 0.25) is the fraction of turns where the action is
logged and not applied. The model is never told which turn it is in. `sham`
and `applied` are recorded per turn in the JSONL; neither ever enters a
prompt.

If the matrix cannot be driven, the loop refuses to start rather than running
as a permanent unlabelled sham — pass `--dry-run` to say that is what you
want.

### What gets written

```
data/readings/electrodes_YYYYMMDD.csv     1 Hz, one row per sample, mV
data/readings/environment_YYYYMMDD.csv    1 Hz, temperature C and F, RH
data/logs/turns_YYYYMMDD.jsonl            one record per turn, live runs
data/logs/replay/turns_YYYYMMDD.jsonl     replay and dry runs
```

Daily files, UTC. The turn record holds the reduced state, the model's full
reply, the validated action, `sham`, `applied`, and any refusal reason — so a
run can be re-read afterwards without the model's notes being the only
account of it.

## Picking this up again after a reboot

Everything survives a power cycle. `sllm-api.service` is enabled and restarts
on boot, so sampling and logging resume by themselves.

```bash
systemctl is-active sllm-api            # should be: active
sudo i2cdetect -y 1                     # 44 and 48
curl -s localhost/api/status | python3 -m json.tool
tail -3 data/readings/electrodes_*.csv  # is it still logging
git -C ~/sllm log --oneline -5          # what was done
```

Then read this file and `CLAUDE_README.md`. The open decisions are the matrix
root problem above and, once the camera is on, setting
`CAMERA_FOCUS_DIOPTRES`.

## Still to build

Per `CLAUDE_README.md`: port `reducer.py` from `llm/filters`, then the model
loop that reduces a 30 min window, POSTs to Ollama, and drives a zone. The
empty-chamber run — two to three days, electrodes in agar, nothing alive —
comes before the organism and is what the reducer thresholds get retuned
against.
