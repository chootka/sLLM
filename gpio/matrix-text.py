"""
Matrix wiring test. Run with sudo.

Lights one pixel, then walks a pixel through the first row, then fills the
whole panel dim blue. If all three work, the wiring and the level shifter are
good.

Brightness is capped low throughout. 256 pixels at full white would draw
around 15A; this stays under a tenth of an amp.
"""

import time

import board
import neopixel

PIXELS = 256
PIN = board.D18
BRIGHTNESS = 0.05

px = neopixel.NeoPixel(PIN, PIXELS, brightness=BRIGHTNESS, auto_write=False)

BLUE = (0, 0, 255)
RED = (255, 0, 0)
OFF = (0, 0, 0)


def clear():
    px.fill(OFF)
    px.show()


try:
    print("1. pixel 0 blue")
    clear()
    px[0] = BLUE
    px.show()
    time.sleep(2)

    print("2. walking the first row")
    for i in range(16):
        clear()
        px[i] = BLUE
        px.show()
        time.sleep(0.1)

    print("3. all blue, dim")
    px.fill(BLUE)
    px.show()
    time.sleep(2)

    print("4. all red, dim — this is the imaging light")
    px.fill(RED)
    px.show()
    time.sleep(2)

    clear()
    print("done")

except KeyboardInterrupt:
    clear()
