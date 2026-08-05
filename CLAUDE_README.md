# sLLM — Pi-side

This Raspberry Pi 5 runs the sensing and actuation for an installation that
couples a *Physarum polycephalum* plasmodium to a language model. The model
itself runs elsewhere (Ollama on a laptop over the network). This machine
samples electrodes, drives a light matrix, and captures images.

## Hardware attached

| Device | Interface | Notes |
|---|---|---|
| WS2812B matrix, 16×16 | GPIO 18 via 74AHCT125 | 9 zones mapped onto pixel groups |
| ADS1115 ADC | I²C, addr 0x48 | 4 Ag/AgCl electrodes, differential, gain 16 |
| FS400-SHTXX | I²C, addr 0x44 or 0x45 | temperature and humidity |
| Noctua NF-A6x25 | GPIO PWM + relay | intake fan |
| Pi Camera Module 3 NoIR | CSI, 22-pin to 15-pin cable | above the chamber lid |

**Power.** The matrix and the level shifter run from a separate Mean Well 5V
supply, *not* from the Pi. Grounds are common. The ADC and sensor take 3.3V
from the Pi header. The Pi has its own USB-C supply.

**Level shifter.** 74AHCT125, pin 14 to 5V, pins 1 and 7 to ground, pin 2 from
GPIO 18, pin 3 to matrix DIN. WS2812 data needs close to 4V for a reliable
high and Pi GPIO is 3.3V, hence the buffer.

**neopixel needs root.** Installed with `sudo pip install
adafruit-circuitpython-neopixel --break-system-packages`. Anything touching
the matrix runs under sudo.

## Physical arrangement

The matrix lies flat under a 100mm square petri dish of non-nutrient agar, so
it backlights the arena. The organism grows on the agar. Four electrodes enter
from above, tips just below the agar surface, three recording plus one
reference in a far corner.

Zone 2 (the corner above the reference electrode) is held permanently lit at
low intensity as a barrier, to stop the plasmodium reaching the reference and
corrupting the baseline. It is not available to the model.

## What the matrix is for

Two jobs on one device.

**Blue is the stimulus.** *Physarum* is photophobic in blue and near-UV. Nine
zones of roughly 3×3 pixels each, addressed independently. The model chooses a
zone, intensity and duration each turn.

**Red is the imaging light.** The camera is NoIR and sees red fine. Flashing
all pixels red during the exposure backlights the agar, so the plasmodium
appears as a dark silhouette. *Physarum* responds far less to red than blue,
and the dose per frame is brief.

Capture sequence: blue off → red on → expose → red off → blue restored. The
blue must be blanked or a lit zone blows out the frame; a 100ms gap is
imperceptible to an organism responding over minutes.

**Never write white.** 256 pixels at full white draws roughly 15A. Cap
brightness globally in software; one zone of blue at low brightness is under
100mA.

## What to build here

- [x] Zone map: pixel indices → 9 zones. Verified empirically, not assumed —
      serpentine, chain starts bottom-left, rows stack upward. See
      `documentation/led_matrix.md`.
- [x] `leds.py` — set zone colour and intensity, blank/restore for capture,
      hold zone 2 lit as the barrier. Exercised against hardware.
- [ ] `adc.py` — ADS1115 at 1 Hz, 3 channels differential against the common
      reference, into a rolling buffer.
- [ ] `sensor.py` — FS400 read, and a bang-bang fan loop: on above 95% RH, off
      below 91%, minimum on and off times of a few minutes, plus a floor
      schedule for CO2 (one minute in twenty regardless).
- [ ] `camera.py` — picamera2, timelapse with the blank/flash sequence.
- [ ] Loop: reduce a 30 min window every N minutes, POST to Ollama, parse the
      JSON action, drive the zone.

The reduction layer, the prompts, and a replay harness already exist in the
main repo and are tested against synthetic data. Do not rewrite them; port
`reducer.py` across and replace its `read_adc` stub.

## Things that matter

**Log everything, timestamped.** Both readings and actions, including turns
where nothing changed. The record of quiet turns is evidence, not noise.

**Sham blocks are part of the design.** Periods where the model acts normally,
the action is logged, and the action is not applied. The model must not be
told which block it is in.

**The empty-chamber run comes before the organism.** Two to three days with
electrodes in agar and nothing alive, everything else running. That gives the
real noise floor and tells you what the fan and any switching couple into the
electrode signal. The thresholds in `reducer.py` were calibrated against
synthetic noise and will need retuning against this.

**Gate sampling around switching.** Do not let the ADC convert while anything
is being energised.
