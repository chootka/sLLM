# Bring-up checklist

State as of 2026-08-05, on the replacement Pi 5 (serial 62a24b43).

## Working now

| Device | Bus | Status |
|---|---|---|
| ADS1115 | I²C 0x48 | reading, 3 channels differential at 1 Hz, gain 16 |
| SHT31 | I²C 0x44 | reading, ~24.7 °C / 53 %RH |
| WS2812B matrix | GPIO 18 | opens as root; **not** reachable from the API, see below |
| Camera | CSI | not attached yet |
| Noctua fan | relay | not wired, `FAN_ENABLED = False` |

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

## Still to build

Per `CLAUDE_README.md`: port `reducer.py` from `llm/filters`, then the model
loop that reduces a 30 min window, POSTs to Ollama, and drives a zone. The
empty-chamber run — two to three days, electrodes in agar, nothing alive —
comes before the organism and is what the reducer thresholds get retuned
against.
