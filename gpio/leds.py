"""
Matrix control: blue stimulus by zone, red imaging light, barrier zone.

Two jobs on one device, per the build notes. Blue is the stimulus the model
drives, nine zones addressed independently. Red is the imaging backlight,
flashed for the duration of an exposure so the plasmodium reads as a dark
silhouette against a lit field.

Run with sudo, like everything else that touches the matrix.

    sudo python3 gpio/leds.py grid      # print the index map, no hardware
    sudo python3 gpio/leds.py zones     # light each zone 0..8 in turn
    sudo python3 gpio/leds.py barrier   # hold zone 2 only, as in the run
    sudo python3 gpio/leds.py capture    # demo the blank/flash/restore cycle

Orientation was measured with matrix_map.py, not assumed: the chain starts at
the bottom-left, runs right along the bottom row, and every alternate row runs
backwards. The four flags below encode that. If the panel is ever remounted or
rotated, re-run matrix_map.py and change only those flags; every zone and
sequence in this file derives from them.
"""

import sys
import time

SIDE = 16
PIXELS = SIDE * SIDE
ZONES = 9

# --- orientation, verified against the panel --------------------------------
# Arena coordinates are (x, y) with (0, 0) at the TOP-LEFT as the camera sees
# the panel from above. These flags carry arena coordinates onto the electrical
# chain order, whatever the panel happens to do internally.
#
# Measured with matrix_map.py: indices 0-15 light the bottom row, 0-7 its left
# half, so the chain starts bottom-left and runs right. Indices 16-31 light the
# row above with 16-23 at the RIGHT, so alternate rows reverse.
SERPENTINE = True  # every other line runs backwards — confirmed
TRANSPOSE = False  # first line is a row, not a column — confirmed
FLIP_X = False  # chain starts at the left — confirmed
FLIP_Y = True  # chain starts at the BOTTOM — confirmed

# --- current limits ---------------------------------------------------------
# 256 pixels at full white is roughly 15A. Never write white, and cap globally.
# One zone of blue at STIM_BRIGHTNESS is well under 100mA.
MAX_BRIGHTNESS = 0.30
STIM_BRIGHTNESS = 0.25  # per-zone blue, scaled by the model's intensity
IMAGING_BRIGHTNESS = 0.15  # all 256 red at once, ~0.8A, brief
BARRIER_BRIGHTNESS = 0.06  # zone 2, lit continuously, so keep it low

# Zone 2 is the TOP-RIGHT corner in arena coordinates. It is held lit as the
# barrier that stops the plasmodium reaching the reference electrode and
# corrupting the baseline, so the reference electrode must physically go in
# that corner. Moving the electrode means changing this constant to match.
BARRIER_ZONE = 2  # over the reference electrode, never offered to the model
BLANK_SETTLE = 0.1  # 100ms, imperceptible to the organism

# 16 does not divide into 3, so bands are 5/6/5. The wider middle band keeps the
# centre zone symmetric about the dish.
BANDS = ((0, 5), (5, 11), (11, 16))


def electrical_index(x, y):
    """Arena (x, y) -> position in the WS2812 chain."""
    if TRANSPOSE:
        x, y = y, x
    if FLIP_X:
        x = SIDE - 1 - x
    if FLIP_Y:
        y = SIDE - 1 - y
    if SERPENTINE and y % 2:
        x = SIDE - 1 - x
    return y * SIDE + x


def zone_bounds(zone):
    """Zone 0..8 -> ((x0, x1), (y0, y1)) half-open in arena coordinates."""
    if not 0 <= zone < ZONES:
        raise ValueError(f"zone {zone} out of range 0..{ZONES - 1}")
    return BANDS[zone % 3], BANDS[zone // 3]


def zone_pixels(zone):
    """Zone 0..8 -> the chain indices it occupies."""
    (x0, x1), (y0, y1) = zone_bounds(zone)
    return [electrical_index(x, y) for y in range(y0, y1) for x in range(x0, x1)]


def zone_of(x, y):
    """Arena (x, y) -> which zone contains it."""
    col = next(i for i, (a, b) in enumerate(BANDS) if a <= x < b)
    row = next(i for i, (a, b) in enumerate(BANDS) if a <= y < b)
    return row * 3 + col


def print_grid():
    """Dump the mapping as text, so it can be checked without the hardware."""
    print("chain index by arena position, (0,0) top-left as the camera sees it\n")
    print("     " + "".join(f"{x:>5}" for x in range(SIDE)))
    for y in range(SIDE):
        print(f"{y:>3}  " + "".join(f"{electrical_index(x, y):>5}" for x in range(SIDE)))

    print("\nzone layout\n")
    for y in range(SIDE):
        print("     " + " ".join(str(zone_of(x, y)) for x in range(SIDE)))

    print(f"\nzone {BARRIER_ZONE} is the barrier, held lit, not offered to the model")
    for z in range(ZONES):
        px = zone_pixels(z)
        (x0, x1), (y0, y1) = zone_bounds(z)
        print(
            f"  zone {z}: x {x0}-{x1 - 1}, y {y0}-{y1 - 1}, "
            f"{len(px)} pixels, indices {min(px)}..{max(px)}"
        )

    seen = sorted(i for z in range(ZONES) for i in zone_pixels(z))
    assert seen == list(range(PIXELS)), "zones must tile the panel exactly once"
    print(f"\nzones tile all {PIXELS} pixels exactly once")


class Matrix:
    """The panel. Holds the blue stimulus state so imaging can restore it."""

    def __init__(self):
        import board
        import neopixel

        self._px = neopixel.NeoPixel(
            board.D18, PIXELS, brightness=MAX_BRIGHTNESS, auto_write=False
        )
        # Intensity 0.0..1.0 per zone, the model's requested blue level.
        self._blue = [0.0] * ZONES
        self._blue[BARRIER_ZONE] = BARRIER_BRIGHTNESS / STIM_BRIGHTNESS
        self._render()

    def _render(self):
        """Push current blue state to the panel."""
        self._px.fill((0, 0, 0))
        for z, level in enumerate(self._blue):
            if level <= 0:
                continue
            value = int(255 * min(level, 1.0))
            for i in zone_pixels(z):
                self._px[i] = (0, 0, value)
        self._px.brightness = STIM_BRIGHTNESS
        self._px.show()

    def set_zone(self, zone, intensity):
        """Set one zone's blue level, 0.0..1.0. The barrier zone is protected."""
        if zone == BARRIER_ZONE:
            raise ValueError(f"zone {BARRIER_ZONE} is the barrier and is not drivable")
        if not 0.0 <= intensity <= 1.0:
            raise ValueError(f"intensity {intensity} outside 0.0..1.0")
        self._blue[zone] = intensity
        self._render()

    def clear_stimulus(self):
        """All zones off except the barrier."""
        for z in range(ZONES):
            if z != BARRIER_ZONE:
                self._blue[z] = 0.0
        self._render()

    def capture_flash(self, exposure):
        """Blue off -> red on -> expose -> red off -> blue restored.

        The blue must be blanked or a lit zone blows out the frame. Pass the
        exposure as a callable; whatever it returns is returned to the caller,
        and the blue state is restored even if it raises.
        """
        try:
            self._px.fill((0, 0, 0))
            self._px.show()
            time.sleep(BLANK_SETTLE)

            self._px.brightness = IMAGING_BRIGHTNESS
            self._px.fill((255, 0, 0))
            self._px.show()
            time.sleep(BLANK_SETTLE)

            return exposure()
        finally:
            self._px.fill((0, 0, 0))
            self._px.show()
            time.sleep(BLANK_SETTLE)
            self._render()

    def off(self):
        """Everything dark, including the barrier. For shutdown only."""
        self._px.brightness = MAX_BRIGHTNESS
        self._px.fill((0, 0, 0))
        self._px.show()


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "grid"

    if mode == "grid":
        print_grid()
        return 0

    m = Matrix()
    try:
        if mode == "zones":
            for z in range(ZONES):
                label = " (barrier, already lit)" if z == BARRIER_ZONE else ""
                print(f"zone {z}{label}")
                if z != BARRIER_ZONE:
                    m.set_zone(z, 1.0)
                time.sleep(2)
                m.clear_stimulus()
                time.sleep(0.3)
        elif mode == "barrier":
            print(f"zone {BARRIER_ZONE} held lit. ctrl-c to stop")
            m.clear_stimulus()
            while True:
                time.sleep(1)
        elif mode == "capture":
            print("blank, flash red, expose 0.5s, restore")
            m.set_zone(4, 1.0)
            time.sleep(2)
            m.capture_flash(lambda: time.sleep(0.5))
            time.sleep(2)
        else:
            print(f"usage: sudo python3 {sys.argv[0]} [grid|zones|barrier|capture]")
            return 1
    except KeyboardInterrupt:
        pass
    finally:
        m.off()
    return 0


if __name__ == "__main__":
    sys.exit(main())
