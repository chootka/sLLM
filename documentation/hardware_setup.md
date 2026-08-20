# sLLM — hardware as built

What is physically in the chamber and how it is wired. Bring-up procedure and
diagnostics live in `bring_up.md`; the panel's geometry and current budget live
in `led_matrix.md`. This file is the parts-and-pins reference only.

Anything marked **TBC** has not been measured — do not treat it as fact.

## Inventory

| Device | Bus / pin | Role |
|---|---|---|
| Raspberry Pi 5 | — | host, replacement board fitted 2026-08-05 |
| ADS1115 | I²C `0x48` | electrode potentials, 3 differential channels at 1 Hz |
| SHT31 | I²C `0x44` | chamber temperature and humidity |
| WS2812B 16×16 | BCM 18 via 74AHCT125 | blue stimulus zones + barrier zone |
| Camera Module 3 NoIR (IMX708) | CSI | stills, 2304×1296 |
| 850nm IR flood | not GPIO-controlled | imaging illumination, always on |
| Noctua NF-A6x25 5V | BCM 23 relay + BCM 12 PWM | air exchange, 60s in every 300s |

Gone from earlier revisions of this document: the microscope ring light on
GPIO 17, the exposure LED on GPIO 27, and the DHT22. None of them exist in the
code and none are wired. The ADC also no longer reads two single-ended
electrodes — see below.

## Electrodes — ADS1115

Aluminium tape, read **differentially**, never single-ended. The potential that
matters is between a recording tip and the reference, and a differential pair
rejects the common-mode noise both wires pick up from the mains and from the
panel.

```
A0 ---- recording electrode 1  \
A1 ---- recording electrode 2   >  each measured against A3
A2 ---- recording electrode 3  /
A3 ---- reference electrode       (top-right corner, under barrier zone 2)
ADDR -- GND                       address 0x48
```

The mux only offers the pairs 0-1, 0-3, 1-3, 2-3, so reading 0/1/2 against 3 is
the only arrangement that gets three channels out of one chip. That is why the
reference is on A3, and why it must sit in the corner the barrier zone lights —
if the reference moves, `BARRIER_ZONE` in `gpio/leds.py` moves with it.

Gain 16, ±0.256V full scale, 7.8125 µV per count. Plasmodium surface potentials
are single-digit millivolts; the default gain 1 would bury the whole signal in
the first 60 counts of a 32768-count range.

Every conversion runs inside `gate.quiet()` — nothing switches while a sample is
taken. See `gpio/bus.py`.

## Illumination

Two separate light sources with two different jobs. They cannot share a frame.

**IR flood (imaging).** An always-on 850nm flood backlights the dish. It is not
switched from GPIO and takes no part in the capture sequence. Being IR, it is
not a stimulus Physarum can respond to, which is the whole point of using it.

- Emitter / part: **TBC**
- Power source: **TBC**
- Mounting height and standoff to the diffuser: **TBC**

**Known fault, 2026-08-19: the flood is not even.** Sampling a 6×6 luminance
grid over the dish crop on three frames spanning 18 hours gives a stable ~20:1
gradient — the bottom-right quadrant clips at 255 across roughly a quarter of
the dish, the top-left sits at 10–25. The pattern does not move between frames,
so it is fixed geometry: a single near-field emitter, close under the diffuser
and off the optical axis toward the bottom-right. Anything in the clipped region
is unrecoverable.

### Replacement rig — target geometry

The dish is **150mm**. Modelling 8 Lambertian emitters on a ring, illuminance
across the 75mm-radius disc, best ring radius at each standoff:

| Standoff to diffuser | Best ring diameter | max/min |
|---|---|---|
| 20mm | — | 5.8 |
| 30mm | 106mm | 2.8 |
| 40mm | 112mm | 1.7 |
| 50mm | 120mm | 1.4 |
| 75mm | 144mm | 1.1 |

**Build to 8 emitters on a 110–120mm circle, 40–50mm below the diffuser**,
firing straight up into it. Note the ring is *smaller* than the dish, about
0.75x its diameter — the outer emitters still throw light inward across the
centre, so a ring matched to the dish edge over-lights the rim.

With only ~30mm of height, add a 9th emitter at the centre: 8-on-a-ring alone is
2.8 there, 8+1 is 2.0, and 12+1 is 1.6. Below ~25mm no ring geometry works for a
dish this wide — that case is two spaced diffuser layers and white cavity walls
doing the work instead.

Caveats on the table: it assumes **wide-angle emitters** (narrow domes at 40mm
print discs no matter what the geometry says), and it is illuminance before any
diffusion, so the built rig should beat it.

Drive: 4 strings of 2 LEDs across 5V, ~22Ω 0.5W per string, ~400mA total at
100mA per emitter. One resistor per string — 850nm Vf is only ~1.4-1.6V and
paralleled emitters current-hog badly.

Order of work, first item is most of the win:

1. Standoff and diffusion. Uniformity is set by emitter-to-diffuser distance,
   not emitter count. Two spaced layers beat one sheet on the LEDs.
2. Ring geometry per the table above, emitters pointing up, not inward at the
   dish. Inward-aimed gives a bright rim and dark centre.
3. Line the cavity — sides and floor — with white card. Free bounce fill, and a
   bigger win than adding emitters.
4. Centre the array on the optical axis.
5. Lock camera exposure and gain so AE stops metering the hot spot.
6. Flat-field correction in software, last. It can normalise a 2:1 gradient; it
   cannot recover clipped pixels.

Measure before and after with `./scripts/py scripts/flatfield.py` on frames with
matched exposure. Baseline 2026-08-19: **ratio 23.2, clipped 9.2%**. Target is
ratio under 2 with nothing clipped.

**First attempt, 2026-08-20: removed.** The new IR string browned out the fan
relay. Not a capacity problem — 8 emitters draw roughly 65mA against a 4A supply
— so suspect a short in that wiring and check it before rebuilding. The LEDs
came out and the old single emitter is back in service, so the 23:1 gradient
above is still what the camera sees.

**Matrix red (disabled).** `IMAGING_RED = False` in `gpio/leds.py`. The panel is
a bare 10mm-pitch array with no diffuser above it, so lit for imaging it
photographs as a grid of 256 dots that buries the plasmodium between them. The
two sources also want exposures an order of magnitude apart — roughly 8ms for
red at `IMAGING_BRIGHTNESS` against ~60ms for the flood — so exposing for one
blows or blacks the other. Re-enable only if the panel gains a diffuser and the
IR flood goes away.

The capture sequence still blanks the panel before every exposure regardless,
which is what keeps the barrier zone out of the frame.

## Matrix — WS2812B 16×16

**Never write white.** 256 pixels at full white draws roughly 15A, far past
what the supply or the wiring will take. `MAX_BRIGHTNESS` in `gpio/leds.py`
caps it globally; one zone of blue at `STIM_BRIGHTNESS` is under 100mA.

Data on BCM 18 (**physical header pin 12**, not physical 18) through a 74AHCT125
level shifter. Wiring and the shifter's own pinout are in `gpio/matrix_diag.py`;
zone geometry, brightness caps and the current budget are in `led_matrix.md`.

The panel is owned exclusively by `sllm-matrixd` running as root — it is the
only privileged process in the system. Everything else talks to it over a unix
socket at `/run/sllm/matrix.sock` (root:sllm, 0660) via `gpio/matrix_client.py`,
which presents the same methods as `leds.Matrix`. Never drive GPIO 18 directly
while matrixd is up; stop the unit first.

## Camera

Camera Module 3 NoIR on the CSI ribbon. The connector is not hot-pluggable —
power down first. Cable orientation and the attach procedure are in
`bring_up.md`; do not work from memory on ribbon orientation.

From `api/config.py`:

- `CAMERA_RESOLUTION = (2304, 1296)` — the IMX708's binned full-field mode. The
  full 4608×2592 is four times the pixels for no extra information about a
  plasmodium and makes a multi-day timelapse enormous.
- `CAMERA_FOCUS_DIOPTRES = 9.3` — measured 2026-08-13, sweep peak at 16×
  contrast. Focus is locked rather than left hunting between frames.
- `IMAGE_CAPTURE_INTERVAL = 300` seconds.

A UVC camera on USB is supported as an alternative (`CAMERA_SOURCE`,
`USB_CAMERA_RESOLUTION`, `USB_CAMERA_FLUSH_FRAMES`). List attached cameras with
`./scripts/py gpio/camera.py info`.

## Chamber fan

A Noctua NF-A6x25 5V on a relay. Its only purpose is keeping fresh air moving so
mould does not establish — it will shift humidity and temperature as a side
effect, but neither is a setpoint and neither decides when it runs. The timed
cycle is the whole rule.

```
relay IN  -> physical pin 16 = BCM 23, active-high (HIGH closes)
fan PWM   -> physical pin 32 = BCM 12, held HIGH as a level while running
```

The PWM line is held high as a level, not driven as a waveform. Without it the
relay closes and the fan does not turn: the pin idles as an input with the
pull-down on, and the fan reads that as 0% duty. See the `Relay` docstring in
`gpio/sensor.py`.

Cycle: 60s on in every 300s (20% duty), with 30s minimum on and 60s minimum off
purely to stop the contacts chattering. Optional extra ventilation at saturation
(`FAN_RH_ON` / `FAN_RH_OFF`) is off by default and is not part of the mould
logic.

## Environment sensor

SHT31 at `0x44` (`0x45` if ADDR is pulled high), read once a second. It replaced
the DHT22 the original build notes called for.

## Quick checks

```bash
i2cdetect -y 1                    # expect 44 and 48
./scripts/py gpio/adc.py watch    # electrode millivolts
./scripts/py gpio/sensor.py watch # temperature and humidity
./scripts/py gpio/camera.py info  # what camera is attached
sudo systemctl stop sllm-matrixd && sudo python3 gpio/leds.py zones
```

Deeper diagnostics, the polkit/systemd layout, and the panel debugging protocol
are in `bring_up.md`.
