# sLLM — hardware as built

Parts and pins. Bring-up and diagnostics: `bring_up.md`. Panel geometry and
current budget: `led_matrix.md`.

**TBC** = not measured.

## Inventory

| Device | Bus / pin | Role |
|---|---|---|
| Raspberry Pi 5 | — | host, replacement board fitted 2026-08-05 |
| ADS1115 | I²C `0x48` | electrode potentials, 3 differential channels at 1 Hz |
| SHT31 | I²C `0x44` | chamber temperature and humidity |
| WS2812B 16×16 | BCM 18 via 74AHCT125 | blue stimulus zones + barrier zone. **Unplugged**, shorted on condensation |
| Camera Module 3 NoIR (IMX708) | CSI | stills, 2304×1296 |
| 850nm IR flood | not GPIO-controlled | imaging illumination, always on. Confirmed fitted and running 2026-08-26 |
| Noctua NF-A6x25 5V | BCM 23 relay + BCM 12 PWM | air exchange, 60s in every 300s |

Not present: GPIO 17 ring light, GPIO 27 exposure LED, DHT22.

## Electrodes — ADS1115

Four Ag/AgCl electrodes, read differentially. One unity-gain buffer per
electrode on the perf board.

```
A0 ---- buffer ---- recording electrode 1  \
A1 ---- buffer ---- recording electrode 2   >  each measured against A3
A2 ---- buffer ---- recording electrode 3  /
A3 ---- buffer ---- reference electrode       (top-right corner, under barrier zone 2)
ADDR -- GND                                   address 0x48
```

Mux pairs available: 0-1, 0-3, 1-3, 2-3. Reference on A3 is the only
arrangement giving three channels from one chip. If the reference moves,
`BARRIER_ZONE` in `gpio/leds.py` moves with it.

Gain 16, ±0.256V full scale, 7.8125 µV per count.

The ADS1115 sees an op-amp output, not the electrode. Its switched-capacitor
input impedance does not load the tips.

Every conversion runs inside `gate.quiet()`. See `gpio/bus.py`.

### Analog front end

Schematics: `~/schematics/` (`0_physarum-full-schematic`, `1_physarum-board-a-cobbler`,
`3_physarum-wiring-guide`).

Board A, 3V3 domain. Per channel, x4 (E1, E2, E3, REF):

```
electrode --+-- 10M --> VBIAS        VBIAS = 1.65 V from 10k/10k off 3V3, 10u to GND
            |
            +--> MCP604 unity-gain follower --> 10k --+--> ADS1115 A0..A3
                                                      |
                                                    100n
                                                      |
                                                     GND
```

- U1 MCP604 quad CMOS op-amp, DIP-14. VDD 3V3 (pin 4), VSS GND (pin 11), 100n
  decoupling. Input bias ~1 pA, so the 10M bias resistors contribute ~10 uV.
  Inputs must stay below VDD-1.2 V (~2.1 V); everything sits at VBIAS 1.65 V.
- 10k + 100n at each ADS pin: absorbs the switched-capacitor charge kick,
  low-pass at 159 Hz.
- Electrodes enter on shielded Cat6 through a sealed grommet with a drip loop.
  Shield and the four partner wires land on GND at the board only, never inside
  the chamber.
- Chamber is a plain plastic box. No electrical shielding around the dish or
  the tips; the Cat6 braid is the only screening on the electrode path.
  `0_physarum-system-overview.html` says "foil-wrapped: dark + Faraday" and
  does not match the built rig.
- Channel map, board is the source of truth (Board A rows, confirmed at the
  bench 2026-08-26):

  | ADS input | app channel | Board A row | Cat6 pair | panel trace |
  |---|---|---|---|---|
  | A0 | ch0 | r38L | orange | orange, solid |
  | A1 | ch1 | r40L | blue | blue, dashed |
  | A2 | ch2 | r40R | green | green, dotted |
  | A3 | reference | r38R | brown | grey |
- The buffers exist because the ADS1115 presents ~710 kOhm differential input
  impedance at the +/-0.256 V range.

**MCP604 offset is expected.** Each follower adds a few mV of fixed offset.
Constant per channel, so it is a baseline shift, not noise: record a baseline
with electrodes in plain saline and subtract per channel. Zero-drift upgrade
option is a MCP6V14 (SMD).

Source impedance interacts with the 10M bias resistor: a 3 MOhm protoplasmic
tube against 10M to VBIAS attenuates by 0.77.

**Data rate 8 SPS, set 2026-08-22** (`ADC_DATA_RATE` in `api/config.py`).
Previously unset, so the library default 128 SPS applied. 125 ms integration
per conversion instead of 7.8 ms; three channels is 375 ms, inside the 1 s
cadence.

Measured effect, same beaker and electrodes, 45 min apart:

| channel | sd at 128 SPS | sd at 8 SPS |
|---|---|---|
| ch0 | 1.80 mV | 0.051 mV |
| ch1 | 0.69 mV | 0.045 mV |
| ch2 | 2.82 mV | 0.109 mV |

15-35x, against ~4x predicted from averaging alone. The excess was 50 Hz
pickup aliasing through a conversion window shorter than one mains cycle;
125 ms spans several cycles and cancels it. Noise floor is now ~50 uV, ~6 LSB.

### Two bench tests, and what each isolates

| test | setup | isolates |
|---|---|---|
| **shorted leads** | all four electrode leads clipped together at the far end | buffer + ADC offset only. Board A build step 5 expects all three channels ~0 mV |
| **common bath** | all four tips in one beaker of saline, wired normally | buffer offset + electrode mismatch |

Bath reading minus shorted reading is the electrode contribution. Run the
shorted test first.

### Chloridization, as built

Electrolytic. 5 mm tip of electrode wire as anode, a second silver wire as
cathode, 9V battery with 1k in line, 13 minutes, 100 mL distilled water with
6 g table salt (~1 M). All four electrodes plated in the same bath.

- Current ~8 mA. Tip area 0.08-0.16 cm2 at 0.5-1 mm wire, so 50-100 mA/cm2.
  Convention is ~1 mA/cm2. Expect a thick, loosely-adherent film.
- Iodide contamination ruled out: 6 g iodized salt carries ~1.6 umol iodide
  against 103 mmol chloride, and the bath passed ~62 umol of charge.

Wire diameter: **TBC**.

### Common-bath offsets, 2026-08-22

All four tips in 1 g / 100 mL saline, wired normally through the buffers.
True potential difference between tips in one bath is zero, so the reading is
offset. First 3 minutes after immersion, still settling:

| pair | mean | sd | drift over 3 min |
|---|---|---|---|
| ch0 - A3 | +8.95 mV | 1.80 | -0.72 mV |
| ch1 - A3 | +6.11 mV | 0.69 | -0.56 mV |
| ch2 - A3 | +3.81 mV | 2.82 | -2.64 mV |

All three positive. Electrode batch mismatch is excluded - one bath, four
electrodes. Consistent with MCP604 follower offset, which the wiring guide
already expects at a few mV per channel: each reading is Vos(n) - Vos(A3), so
one offset follower on A3 shifts all three the same way. The shorted-lead test
separates the two.

Fixed offset of this size is not a problem at gain 16 - 9 mV against
+/-256 mV of range. Drift is what matters.

Superseded: the 0.7-2.8 mV sd was the 128 SPS conversion window, not front-end
noise. See the data rate note above. At 8 SPS the same setup reads 0.045-0.109
mV, and the offsets scatter either side of zero (+2.5, -0.5, -2.6 mV) rather
than all positive.

### Agar geometry

**As built 2026-08-24: four discrete islands of non-nutrient 2% agar on bare
dish floor.** Arena 150 mm.

| | |
|---|---|
| reference island | 20 mm dia x 4 mm, centre |
| recording islands | 3 x 15 mm dia x 4 mm |
| gap | 10 mm bare floor, edge to edge |
| spacing | 27.5 mm centre to centre |
| tips | all four flat on the dish floor at one depth, agar dropped over them |
| oat flake | one per recording island, none on the reference |

Per Adamatzky and Jones 2011: discrete blobs on bare floor so the organism is
the only conductive path between sites.

**Superseded: one continuous agar bed**, reference buried in it, three recording
electrodes just below the surface. Two faults, both fixed by the switch to
islands:

- The bed conducts and shunts the source. Protoplasmic tube resistance is ~3 MΩ
  (Adamatzky 2014). Spreading resistance between mm-scale tips a few cm apart in
  the bed is 10-100 kΩ, a divider of 30:1 to 300:1: a 5 mV tube potential
  reaches the buffer as 17-170 µV, against a 7.8 µV step and tens of mV of
  drift. Test with a multimeter across two electrode leads: kΩ = shunted.
- Depth split. The bed loses water from the top, raising surface ion
  concentration, so an electrochemical gradient forms between the buried
  reference and the near-surface recorders. Appears on all three channels
  because they share that reference.

**Spacing and period.** 2-3 cm gives 30-40 min (Adamatzky and Jones 2011),
2-3 mm gives 60-180 s (Kishimoto 1958). 27.5 mm spacing predicts the 30-40 min
band. The 2026-08-24 run measured a 2.2-2.4 min oscillation and no 30-40 min
band; see `STATUS.md`. 2-3 mm spacing is incompatible with the 10 mm gaps
needed to keep the sites separate.

### Reading a bench test

Read from the running logger rather than starting a second process:

```bash
tail -f /var/www/sllm/data/readings/electrodes_$(date +%Y%m%d).csv
```

Do not run `gpio/adc.py watch` while `sllm-api` is active - both drive the same
ADS1115 over I2C. Stop the unit first if you want the standalone tool.

Allow 20-30 min to settle before reading. Tip source impedance cannot be
measured from the ADC; the buffers block it.

## Illumination

Two sources, never in the same frame.

**IR flood (imaging).** 850nm, always on, not GPIO-switched, takes no part in
the capture sequence.

- Emitter / part: **TBC**
- Power source: **TBC**
- Mounting height and standoff to the diffuser: **TBC**

**Fault, 2026-08-19: flood is uneven.** 6×6 luminance grid over the dish crop,
three frames spanning 18 hours: stable ~20:1 gradient, bottom-right quadrant
clipped at 255 over ~¼ of the dish, top-left at 10–25. Fixed geometry — single
near-field emitter, close under the diffuser, off-axis toward bottom-right.
Clipped pixels are unrecoverable.

### Replacement rig — target geometry

Dish is 150mm. 8 Lambertian emitters on a ring, illuminance across the 75mm
radius, best ring radius per standoff:

| Standoff to diffuser | Best ring diameter | max/min |
|---|---|---|
| 20mm | — | 5.8 |
| 30mm | 106mm | 2.8 |
| 40mm | 112mm | 1.7 |
| 50mm | 120mm | 1.4 |
| 75mm | 144mm | 1.1 |

Build: 8 emitters on a 110–120mm circle, 40–50mm below the diffuser, firing
straight up. Ring diameter is ~0.75× the dish; a ring matched to the dish edge
over-lights the rim.

At ~30mm add a 9th emitter at the centre: 8-on-a-ring is 2.8, 8+1 is 2.0, 12+1
is 1.6. Below ~25mm no ring geometry works at this dish width — use two spaced
diffuser layers and white cavity walls.

Table assumes wide-angle emitters; narrow domes at 40mm print discs. Figures
are illuminance before diffusion.

Drive: 4 strings of 2 LEDs across 5V, ~22Ω 0.5W per string, ~400mA total at
100mA per emitter. One resistor per string — 850nm Vf is ~1.4–1.6V and
paralleled emitters current-hog.

Order of work:

1. Standoff and diffusion. Uniformity is set by emitter-to-diffuser distance,
   not emitter count. Two spaced layers beat one sheet.
2. Ring geometry per the table, emitters pointing up, not inward. Inward-aimed
   gives a bright rim and dark centre.
3. Line the cavity sides and floor with white card.
4. Centre the array on the optical axis.
5. Lock camera exposure and gain.
6. Flat-field correction in software. Normalises a 2:1 gradient; cannot
   recover clipped pixels.

Measure with `./scripts/py scripts/flatfield.py` on matched-exposure frames.
Baseline 2026-08-19: ratio 23.2, clipped 9.2%. Target: ratio under 2, nothing
clipped.

2026-08-20: first replacement string browned out the fan relay and was removed.
8 emitters draw ~65mA against a 4A supply, so check that wiring for a short
before rebuilding. Old single emitter back in service; the 23:1 gradient stands.

**Matrix red (disabled).** `IMAGING_RED = False` in `gpio/leds.py`. The panel is
a bare 10mm-pitch array with no diffuser, so it photographs as a grid of 256
dots. Exposures differ by an order of magnitude — ~8ms for red at
`IMAGING_BRIGHTNESS` against ~60ms for the flood. Re-enable only with a
diffuser above the panel and the IR flood removed.

The capture sequence blanks the panel before every exposure, which keeps the
barrier zone out of frame.

## Matrix — WS2812B 16×16

**Fault: unplugged. Shorted from condensation inside the chamber.** Date
unplugged: **TBC**. Humidity railed at 99.9-100.0% for the whole 20260821 run.
The panel sits under the dish inside the humid box; any rebuild needs the
matrix sealed against condensation.

`sllm-matrixd` reports success with the panel unpowered - writes go out over
GPIO 18 and there is no readback. Software state is not evidence the panel lit.


**Never write white.** 256 pixels at full white draws ~15A. `MAX_BRIGHTNESS` in
`gpio/leds.py` caps globally; one zone of blue at `STIM_BRIGHTNESS` is under
100mA.

Data on BCM 18 (**physical header pin 12**) through a 74AHCT125 level shifter.
Shifter pinout: `gpio/matrix_diag.py`. Zone geometry, brightness caps, current
budget: `led_matrix.md`.

The panel is owned exclusively by `sllm-matrixd` running as root — the only
privileged process in the system. Everything else talks to it over a unix
socket at `/run/sllm/matrix.sock` (root:sllm, 0660) via `gpio/matrix_client.py`,
which presents the same methods as `leds.Matrix`. Stop the unit before driving
GPIO 18 directly.

## Camera

Camera Module 3 NoIR on the CSI ribbon. Not hot-pluggable — power down first.
Cable orientation and attach procedure: `bring_up.md`.

From `api/config.py`:

- `CAMERA_RESOLUTION = (2304, 1296)` — IMX708 binned full-field mode.
- `CAMERA_FOCUS_DIOPTRES = 9.3` — measured 2026-08-13, sweep peak at 16×
  contrast. Locked, not hunting.
- `IMAGE_CAPTURE_INTERVAL = 300` seconds.

UVC camera on USB supported as an alternative (`CAMERA_SOURCE`,
`USB_CAMERA_RESOLUTION`, `USB_CAMERA_FLUSH_FRAMES`). List attached cameras with
`./scripts/py gpio/camera.py info`.

## Chamber fan

Noctua NF-A6x25 5V on a relay. Runs on a timed cycle for mould prevention.
Humidity and temperature are not setpoints and do not gate it.

```
relay IN  -> physical pin 16 = BCM 23, active-high (HIGH closes)
fan PWM   -> physical pin 32 = BCM 12, held HIGH as a level while running
```

The PWM line is a held level, not a waveform. Without it the relay closes and
the fan does not turn: the pin idles as an input with the pull-down on, and the
fan reads 0% duty. See the `Relay` docstring in `gpio/sensor.py`.

Cycle: 60s on in every 300s (20% duty), 30s minimum on, 60s minimum off.
`FAN_RH_ON` / `FAN_RH_OFF` saturation ventilation is off by default.

## Environment sensor

SHT31 at `0x44` (`0x45` with ADDR high), read once a second.

## Quick checks

```bash
i2cdetect -y 1                    # expect 44 and 48
./scripts/py gpio/adc.py watch    # electrode millivolts
./scripts/py gpio/sensor.py watch # temperature and humidity
./scripts/py gpio/camera.py info  # what camera is attached
sudo systemctl stop sllm-matrixd && sudo python3 gpio/leds.py zones
```

Deeper diagnostics, polkit/systemd layout, panel debugging: `bring_up.md`.
