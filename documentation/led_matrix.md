# WS2812B Matrix — Bring-Up and Zone Map

Notes from getting the 16×16 matrix working on the Pi 5, and the verified
mapping everything downstream depends on.

Status: **working.** Chain proven end to end, zone map measured, `leds.py`
exercised against hardware.

## The chain

```
Pi 5 GPIO 18  ->  74AHCT125 pin 2 (1A, input)
                  74AHCT125 pin 3 (1Y, output)  ->  matrix DIN
                  74AHCT125 pin 1 (1OE)         ->  GND   (active low, enables)
                  74AHCT125 pin 7 (GND)         ->  GND
                  74AHCT125 pin 14 (VCC)        ->  5V

Matrix 5V/GND    ->  Mean Well 5V supply, NOT the Pi
Grounds          ->  Pi, Mean Well and shifter all common
```

**GPIO 18 is physical header pin 12.** Not header pin 18 — that is GPIO 24.
This cost the entire first debugging session; see below.

## Pi 5 needs a different NeoPixel driver

The classic `rpi_ws281x` DMA/PWM path works on Pi 0–4 and **not** on the Pi 5,
because the Pi 5 moves GPIO onto the RP1 southbridge. The Pi 5 path uses the
RP1's PIO instead, via a separate package:

```
Adafruit-Blinka-Raspberry-Pi5-Neopixel   1.0.0rc2
adafruit-circuitpython-neopixel          6.4.2
Adafruit-Blinka                          9.2.0
```

`neopixel_write.py` dispatches on `detector.board.any_raspberry_pi_5_board` and
imports `adafruit_raspberry_pi5_neopixel_write`. If that package is missing on a
Pi 5, nothing works. Everything touching the matrix runs under `sudo`.

The driver raises `RuntimeError` on PIO failures — "Failed to open PIO device",
"pio_init() failed". **A silent, error-free run means data really did leave
GPIO 18.** That is useful: it cleanly separates software faults from wiring
faults, and it is what told us to stop suspecting the driver and go get a meter.

## Bring-up tools

| Script | Purpose |
|---|---|
| `gpio/matrix-text.py` | Proves the chain: one pixel, walking pixel, blue fill, red fill |
| `gpio/matrix_diag.py` | Holds GPIO 18 at a steady DC level for multimeter work |
| `gpio/matrix_map.py` | Blinking bars that reveal the index-to-position mapping |
| `gpio/leds.py grid` | Prints the index map and zone layout, no hardware needed |

### Isolating a dead data line

WS2812 traffic is far too fast to see on a meter. `matrix_diag.py` holds the pin
at DC instead, so each stage of the chain can be probed:

```bash
sudo python3 gpio/matrix_diag.py high     # hold 3.3V
sudo python3 gpio/matrix_diag.py low      # hold 0V
sudo python3 gpio/matrix_diag.py toggle   # 1Hz square wave
```

Black lead on any common ground, then measure in order. The first point where
the expected voltage fails to appear is the fault:

| Probe | Expect with the line HIGH |
|---|---|
| Pi header pin 12 | ~3.3V |
| 74AHCT125 pin 2 | ~3.3V |
| 74AHCT125 pin 3 | ~5V |
| Matrix DIN | ~5V |

`pinctrl` gives the SoC's own view and is worth cross-checking:

```bash
sudo pinctrl get 18
# 18: op dh pn | hi   -> output, driving high, reads back high
```

**When `pinctrl` says the pad is high and the meter says 0V, believe neither —
check which physical pin the probe is on.** That contradiction was the whole
fault: the meter was on header pin 11 (GPIO 17), which is diagonally adjacent
and happened to be driven low by something else. To locate pin 12 with
certainty, find the only adjacent pair of 5V pins on the header — those are
pins 2 and 4, the start of the even column. Pin 12 is the sixth in that column.

## Verified mapping

Measured with `matrix_map.py`, not assumed:

- indices 0–15 light the **entire bottom row** → row-wise, not column-wise
- indices 0–7 are its **left half** → chain starts bottom-left, running right
- indices 16–31 light the **row above** → rows stack upward
- indices 16–23 are at the **right** → serpentine, alternate rows reversed

In `leds.py` this is four flags, and nothing else needs to change if the panel
is remounted:

```python
SERPENTINE = True    # alternate lines run backwards
TRANSPOSE  = False   # first line is a row, not a column
FLIP_X     = False   # chain starts at the left
FLIP_Y     = True    # chain starts at the BOTTOM
```

Arena coordinates are `(x, y)` with `(0, 0)` at the **top-left as the camera
sees the panel from above**. Corners, for orientation:

```
arena (0,15)  bottom-left   -> index 0
arena (15,15) bottom-right  -> index 15
arena (15,14) row above, right -> index 16   (serpentine turn)
arena (0,0)   top-left      -> index 255
```

## Zones

Nine zones in a 3×3 arrangement. 16 does not divide by 3, so the bands are
5/6/5 — the wider middle band keeps the centre zone symmetric about the dish.
The zones tile all 256 pixels exactly once, asserted in `leds.py grid`.

```
0 0 0 0 0 1 1 1 1 1 1 2 2 2 2 2     zone 0  top-left
0 0 0 0 0 1 1 1 1 1 1 2 2 2 2 2     zone 1  top-middle
0 0 0 0 0 1 1 1 1 1 1 2 2 2 2 2     zone 2  top-right   <- BARRIER
3 3 3 3 3 4 4 4 4 4 4 5 5 5 5 5     zone 4  centre
6 6 6 6 6 7 7 7 7 7 7 8 8 8 8 8     zone 8  bottom-right
```

Note this differs from the "roughly 3×3 pixels each" in the build notes: a 3×3
grid of zones over a 16×16 panel gives about 5×5 pixels per zone. The full
partition was chosen because it backlights the arena with no dark bands. Nine
small 3×3 clusters with gaps between them is a different stimulus geometry; it
would only need `BANDS` changing.

**Zone 2 is the barrier.** Held permanently lit at low intensity to stop the
plasmodium reaching the reference electrode and corrupting the baseline. It is
not offered to the model, and `set_zone()` raises if anything tries to drive it.
The reference electrode must therefore sit in the **top-right corner**. If it
moves, change `BARRIER_ZONE` to match.

## Measurements

- **`show()` takes 8ms** for 256 pixels — min 7.5, median 8.0, max 8.1 over 20
  writes. The 100ms blank in the capture sequence has ~12× headroom.
- Startup is negligible: `import board` 0.03s, constructing `NeoPixel` ~0s.

### Current budget

256 pixels at full white is roughly **15A**. Never write white. Caps in
`leds.py`:

| Constant | Value | Draw |
|---|---|---|
| `STIM_BRIGHTNESS` | 0.25 | one zone of blue, well under 100mA |
| `IMAGING_BRIGHTNESS` | 0.15 | all 256 red at once, ~0.8A, brief |
| `BARRIER_BRIGHTNESS` | 0.06 | zone 2, lit continuously |
| `MAX_BRIGHTNESS` | 0.30 | global ceiling |

## Gotchas

**Single pixels are effectively invisible.** One pixel at brightness 0.05 is
value 12/255, and under a diffusing agar dish it cannot be picked out at all —
three separate test runs where the fills were obvious and the single-pixel
stages were missed entirely. Use whole lines of 16, blinking, for anything that
has to be observed by eye. `matrix_map.py` does this.

**Never leave the data line at a static DC high.** It is not valid WS2812 data,
so the first pixels latch arbitrary values — in practice full white, which is
the maximum-current case. Fine for a brief meter reading, but release it after.
Conveniently, this doubles as a crude continuity test: garbage on the first
pixels proves the chain is passing data.

**Capture blanking is mandatory.** `capture_flash()` does blue off → 100ms →
red on → expose → red off → blue restored, and restores the blue state even if
the exposure raises. Without the blank, a lit blue zone blows out the frame.

## Where this sits in the build

The matrix was **step 1**, brought up on its own before anything else was
attached. That is deliberate and worth preserving as a method: with only one
peripheral on the bench, a dead data line has a small number of possible
causes, and the meter procedure above actually converges. The same session
would have been much harder to reason about with the ADC, sensor and fan all
half-wired at the same time.

At the end of step 1, a scan of `/dev/i2c-1` returns no addresses — no ADS1115
at 0x48, no FS400 at 0x44/0x45 — and neither driver library is installed. That
is the expected state, not a fault, and it is recorded here as the baseline the
next step starts from.

Step 2 is the ADS1115. When it lands, the constraint to carry over is that
**ADC sampling must be gated around switching**: do not convert while the
matrix, fan or relay is being energised. That is the interface `adc.py` will
need against `leds.py`.
