"""
Zone-map discovery. Run with sudo.

matrix-text.py proves the chain works. This answers the question the zone map
depends on: how chain index maps to physical position. The panel is probably
serpentine, but that should be verified rather than assumed.

Single pixels turned out to be invisible in practice — one pixel at low
brightness, under a diffusing agar dish, simply cannot be picked out. So every
stage here lights a whole line of 16 and blinks it. A blinking bar is obvious
in a way a static dim dot is not.

    sudo python3 gpio/matrix_map.py

Three observations pin the mapping down completely:

  where indices 0..15 sit    -> is the first line a row or a column, on which edge
  where indices 0..7 sit     -> which end of that line the chain starts from
  where indices 16..31 sit   -> serpentine or progressive, and which way

Serpentine means the second line runs backwards: 16..31 will sit alongside
0..15 but with the half-line at the OPPOSITE end. Progressive means it starts
from the same end as the first.

16 pixels of blue at this brightness is about 80mA. Never white.
"""

import time

import board
import neopixel

PIXELS = 256
PIN = board.D18

FILL_BRIGHTNESS = 0.05  # all 256, keep dim
LINE_BRIGHTNESS = 0.25  # 16 at a time, safe to push so it is actually visible

BLUE = (0, 0, 255)
OFF = (0, 0, 0)

MARKER_HOLD = 2.0
BLINK_SECONDS = 6.0
BLINK_HZ = 2.0
GAP = 1.0

px = neopixel.NeoPixel(PIN, PIXELS, brightness=FILL_BRIGHTNESS, auto_write=False)


def clear(pause=GAP):
    px.fill(OFF)
    px.show()
    time.sleep(pause)


def blink(indices, seconds=BLINK_SECONDS):
    """Blink a set of indices so it cannot be missed."""
    px.brightness = LINE_BRIGHTNESS
    half = 1.0 / (2 * BLINK_HZ)
    for _ in range(int(seconds * BLINK_HZ)):
        px.fill(OFF)
        for i in indices:
            px[i] = BLUE
        px.show()
        time.sleep(half)
        px.fill(OFF)
        px.show()
        time.sleep(half)
    px.brightness = FILL_BRIGHTNESS


try:
    print(f"stage 0: all blue, {MARKER_HOLD}s — starting marker")
    px.brightness = FILL_BRIGHTNESS
    px.fill(BLUE)
    px.show()
    time.sleep(MARKER_HOLD)
    clear()

    print(f"stage 1: indices 0-15 blinking, {BLINK_SECONDS}s — WHICH EDGE, row or column")
    blink(range(0, 16))
    clear()

    print(f"stage 2: indices 0-7 blinking, {BLINK_SECONDS}s — WHICH END it starts from")
    blink(range(0, 8))
    clear()

    print(f"stage 3: indices 16-31 blinking, {BLINK_SECONDS}s — the SECOND line")
    blink(range(16, 32))
    clear()

    print(f"stage 4: indices 16-23 blinking, {BLINK_SECONDS}s — WHICH END the second starts")
    blink(range(16, 24))
    clear(0)

    print("done")

except KeyboardInterrupt:
    clear(0)
