# WS2812B Matrix — Bring-Up and Zone Map

Status: working. Chain proven end to end, zone map measured.

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

**GPIO 18 is physical header pin 12.** Header pin 18 is GPIO 24.

## Pi 5 NeoPixel driver

`rpi_ws281x` DMA/PWM works on Pi 0–4, not on the Pi 5 — GPIO moved to the RP1
southbridge. The Pi 5 path uses the RP1's PIO:

```
Adafruit-Blinka-Raspberry-Pi5-Neopixel   1.0.0rc2
adafruit-circuitpython-neopixel          6.4.2
Adafruit-Blinka                          9.2.0
```

`neopixel_write.py` dispatches on `detector.board.any_raspberry_pi_5_board` and
imports `adafruit_raspberry_pi5_neopixel_write`. Everything touching the matrix
runs under `sudo`.

The driver raises `RuntimeError` on PIO failures — "Failed to open PIO device",
"pio_init() failed". A silent, error-free run means data left GPIO 18.

## Bring-up tools

| Script | Purpose |
|---|---|
| `gpio/matrix-text.py` | Proves the chain: one pixel, walking pixel, blue fill, red fill |
| `gpio/matrix_diag.py` | Holds GPIO 18 at a steady DC level for multimeter work |
| `gpio/matrix_map.py` | Blinking bars that reveal the index-to-position mapping |
| `gpio/leds.py grid` | Prints the index map and zone layout, no hardware needed |

### Isolating a dead data line

WS2812 traffic is too fast to meter. `matrix_diag.py` holds the pin at DC:

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

Cross-check the SoC's view:

```bash
sudo pinctrl get 18
# 18: op dh pn | hi   -> output, driving high, reads back high
```

If `pinctrl` says high and the meter says 0V, verify which physical pin the
probe is on. To locate pin 12: find the only adjacent pair of 5V pins on the
header — pins 2 and 4, the start of the even column. Pin 12 is the sixth in
that column.

## Verified mapping

Measured with `matrix_map.py`:

- indices 0–15 light the entire bottom row → row-wise, not column-wise
- indices 0–7 are its left half → chain starts bottom-left, running right
- indices 16–31 light the row above → rows stack upward
- indices 16–23 are at the right → serpentine, alternate rows reversed

Four flags in `leds.py`:

```python
SERPENTINE = True    # alternate lines run backwards
TRANSPOSE  = False   # first line is a row, not a column
FLIP_X     = False   # chain starts at the left
FLIP_Y     = True    # chain starts at the BOTTOM
```

Arena coordinates are `(x, y)` with `(0, 0)` at the top-left as the camera sees
the panel from above:

```
arena (0,15)  bottom-left   -> index 0
arena (15,15) bottom-right  -> index 15
arena (15,14) row above, right -> index 16   (serpentine turn)
arena (0,0)   top-left      -> index 255
```

## Zones

Nine zones in a 3×3 arrangement. Bands are 5/6/5, keeping the centre zone
symmetric about the dish. The zones tile all 256 pixels exactly once, asserted
in `leds.py grid`.

```
     . . . . . . . . . . . . . . . .
     . . . . 0 1 1 1 1 1 1 B . . . .
     . . . 0 0 0 1 1 1 1 2 B B . . .
     . . 0 0 0 0 1 1 1 1 2 2 2 B . .
     . 0 0 0 0 0 0 1 1 2 2 2 2 B B .
     . 3 0 0 0 0 0 1 1 2 2 2 2 2 5 .
     . 3 3 3 0 0 4 4 4 4 2 2 5 5 5 .
     . 3 3 3 3 3 4 4 4 4 5 5 5 5 5 .
     . 3 3 3 3 3 4 4 4 4 5 5 5 5 5 .
     . 3 3 3 6 6 4 4 4 4 8 8 5 5 5 .
     . 3 6 6 6 6 6 7 7 8 8 8 8 8 5 .
     . 6 6 6 6 6 6 7 7 8 8 8 8 8 8 .
     . . 6 6 6 6 7 7 7 7 8 8 8 8 . .
     . . . 6 6 6 7 7 7 7 8 8 8 . . .
     . . . . 6 7 7 7 7 7 7 8 . . . .
     . . . . . . . . . . . . . . . .
```

`.` is outside the dish, `B` is the lit ring of barrier zone 2. Print it with
`./scripts/py gpio/leds.py`. The map is computed from `DISH_RADIUS` and
`CENTRE_RADIUS`, not stored.

The arena is the dish, not the panel. A 150mm dish on a 160mm panel is a radius
of 7.5 px, so the corners fall outside the agar. Zone numbers keep their 3×3
compass directions; the shapes are a centre disc plus eight rim sectors.
`CENTRE_RADIUS` is r/3, making the centre one ninth of the dish area.

**Zone 2 is the barrier.** Held lit at low intensity to stop the plasmodium
reaching the reference electrode. Not offered to the model; `set_zone()` raises
if anything tries to drive it. Only its outermost ring is energised — 6 of its
21 pixels. The reference electrode must sit in the top-right. If it moves,
change `BARRIER_ZONE`.

## Measurements

- `show()` takes 8ms for 256 pixels — min 7.5, median 8.0, max 8.1 over 20
  writes. The 100ms blank in the capture sequence has ~12× headroom.
- `import board` 0.03s, constructing `NeoPixel` ~0s.

### Current budget

256 pixels at full white is ~15A. Never write white. Caps in `leds.py`:

| Constant | Value | Draw |
|---|---|---|
| `STIM_BRIGHTNESS` | 0.12 | one zone of blue, under 100mA |
| `IMAGING_BRIGHTNESS` | 0.012 | all dish pixels red at once, ~0.04A, brief |
| `BARRIER_BRIGHTNESS` | 0.06 | zone 2's outer ring, lit continuously |
| `MAX_BRIGHTNESS` | 0.30 | global ceiling |

`IMAGING_RED` is False. Captures use no red; the dish is backlit by the 850nm
IR flood. The panel has no diffuser and photographs as a grid of 256 dots. Set
True only with a diffuser fitted and the flood removed.

## Gotchas

**Single pixels are effectively invisible.** One pixel at brightness 0.05 is
value 12/255, and under a diffusing agar dish cannot be picked out. Use whole
lines of 16, blinking, for anything observed by eye. `matrix_map.py` does this.

**Never leave the data line at a static DC high.** It is not valid WS2812 data,
so the first pixels latch arbitrary values — in practice full white, the
maximum-current case. Release it after a meter reading. Garbage on the first
pixels also proves the chain is passing data.

**Capture blanking is mandatory.** `capture_flash()` does blue off → 100ms →
red on → expose → red off → blue restored, and restores the blue state even if
the exposure raises. Without the blank, a lit blue zone blows out the frame.

## Constraint carried into the ADC

ADC sampling is gated around switching: do not convert while the matrix, fan or
relay is being energised. See `gate.quiet()` in `gpio/bus.py`.
