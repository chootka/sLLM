"""
Matrix control: blue stimulus by zone, red imaging light.

Two jobs on one device, per the build notes. Blue is the stimulus the model
drives, nine zones addressed independently. Red is the imaging backlight,
flashed for the duration of an exposure so the plasmodium reads as a dark
silhouette against a lit field.

Run with sudo, like everything else that touches the matrix.

    sudo python3 gpio/leds.py grid      # print the index map, no hardware
    sudo python3 gpio/leds.py zones     # light each zone 0..8 in turn
    sudo python3 gpio/leds.py capture    # demo the blank/flash/restore cycle

Orientation was measured with matrix_map.py, not assumed: the chain starts at
the bottom-left, runs right along the bottom row, and every alternate row runs
backwards. The four flags below encode that. If the panel is ever remounted or
rotated, re-run matrix_map.py and change only those flags; every zone and
sequence in this file derives from them.
"""

import math
import sys
import time

import recovery

SIDE = 16
PIXELS = SIDE * SIDE
ZONES = 9

# --- orientation, verified against the panel --------------------------------
# Arena (x, y) has (0, 0) TOP-LEFT as the camera sees the panel. These flags map
# arena coordinates onto the chain order.
#
# Measured with matrix_map.py: chain starts bottom-left running right, and
# alternate rows reverse.
SERPENTINE = True  # every other line runs backwards — confirmed
TRANSPOSE = False  # first line is a row, not a column — confirmed
FLIP_X = False  # chain starts at the left — confirmed
FLIP_Y = True  # chain starts at the BOTTOM — confirmed

# --- current limits ---------------------------------------------------------
# 256 pixels at full white is roughly 15A. Never write white, and cap globally.
# One zone of blue at STIM_BRIGHTNESS is well under 100mA.
MAX_BRIGHTNESS = 0.30
STIM_BRIGHTNESS = 0.12  # per-zone blue, scaled by the model's intensity
IMAGING_BRIGHTNESS = 0.012  # every dish pixel red at once, ~0.04A, brief

# The dish is backlit by an always-on 850nm IR flood, so captures need no red.
# The panel has no diffuser and photographs as 256 dots that bury the plasmodium.
#
# The flood is NOT even, as of 2026-08-19: ~20:1 gradient, bottom-right quadrant
# clipped. See documentation/hardware_setup.md.
#
# Red wants ~8ms and the IR flood ~60ms, so they cannot share a frame. Set True
# only if the panel gains a diffuser and the flood goes away.
IMAGING_RED = False
# --- recovery mode ----------------------------------------------------------
# Set while the plasmodium is coming back from sclerotium. Stimulus zones are
# not rendered and captures run without red. set_zone is still accepted and
# recorded as off, so active_zones stays true to what the organism got.
#
# In recovery nothing is lit at all. Until 2026-09-08 zone 2 was held lit as a
# barrier keeping the plasmodium off the reference electrode; the organism now
# starts ON the reference island, so the barrier was removed and every zone is
# drivable. recovery.json still carries a `dark` flag, now inert -- there is no
# longer a lit barrier for it to drop.
#
# llm/loop.py refuses a live run in recovery, so no turns are logged against an
# organism that could not have responded.
#
# State lives in data/recovery.json, read on every render; see gpio/recovery.py.
# The admin page owns it and the panel follows within one refresh interval.
BLANK_SETTLE = 0.1  # 100ms, imperceptible to the organism

# --- dish geometry ----------------------------------------------------------
# The arena is the dish, not the panel. Corner pixels fall outside the agar:
# lighting them stimulates nothing and flares into the frame during imaging.
#
# Distances are in pixels, which is the panel pitch. A 150mm dish on a 160mm
# 16x16 panel is radius 7.5. Every zone below follows from DISH_RADIUS.
DISH_RADIUS = 7.5
# Offset this if the dish does not sit concentric with the panel.
DISH_CENTRE = (SIDE / 2.0, SIDE / 2.0)

# Nine zones: a centre disc plus eight rim sectors. A round arena does not
# divide into a 3x3 grid -- the bands this replaced put four zones mostly
# outside the dish.
#
# r/3 makes the centre disc exactly one ninth of the dish area, so all nine
# zones carry equal weight.
CENTRE_RADIUS = DISH_RADIUS / 3.0
CENTRE_ZONE = 4

# Zone numbers keep their 3x3 directions, so zone 2 stays top-right:
#
#     0 1 2        NW  N  NE
#     3 4 5   -->   W  C  E
#     6 7 8        SW  S  SE
#
# Indexed anticlockwise from east, which is the order atan2 counts in.
SECTOR_ZONES = (5, 2, 1, 0, 3, 6, 7, 8)


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


def zone_of(x, y):
    """Arena (x, y) -> which zone contains it, or None if outside the dish."""
    cx, cy = DISH_CENTRE
    dx, dy = x + 0.5 - cx, y + 0.5 - cy
    distance = math.hypot(dx, dy)

    if distance > DISH_RADIUS:
        return None
    if distance <= CENTRE_RADIUS:
        return CENTRE_ZONE

    # Arena y grows downward, so negate it to get a compass bearing. The +22.5
    # rotates the sector boundaries off the axes, which puts east in the middle
    # of its sector rather than split across two.
    bearing = math.degrees(math.atan2(-dy, dx))
    return SECTOR_ZONES[int(((bearing + 22.5) % 360) // 45)]


# Computed once at import: the zone map is pure geometry and never moves at
# runtime, and _render walks it on every stimulus change.
ZONE_PIXELS = tuple(
    tuple(electrical_index(x, y)
          for y in range(SIDE) for x in range(SIDE) if zone_of(x, y) == zone)
    for zone in range(ZONES)
)

# Every pixel inside the dish. The corners are in no zone and are never lit,
# by stimulus or by the imaging flash.
DISH_PIXELS = tuple(
    electrical_index(x, y)
    for y in range(SIDE) for x in range(SIDE) if zone_of(x, y) is not None
)


def zone_pixels(zone):
    """Zone 0..8 -> the chain indices it occupies, and that _render energises."""
    if not 0 <= zone < ZONES:
        raise ValueError(f"zone {zone} out of range 0..{ZONES - 1}")
    return ZONE_PIXELS[zone]


def print_grid():
    """Dump the mapping as text, so it can be checked without the hardware."""
    print("chain index by arena position, (0,0) top-left as the camera sees it\n")
    print("     " + "".join(f"{x:>5}" for x in range(SIDE)))
    for y in range(SIDE):
        print(f"{y:>3}  " + "".join(f"{electrical_index(x, y):>5}" for x in range(SIDE)))

    print(f"\nzone layout, dish radius {DISH_RADIUS} px, '.' is outside it\n")
    for y in range(SIDE):
        cells = []
        for x in range(SIDE):
            zone = zone_of(x, y)
            cells.append("." if zone is None else str(zone))
        print("     " + " ".join(cells))

    print("\nall nine zones are drivable")
    target = len(DISH_PIXELS) / ZONES
    for z in range(ZONES):
        px = zone_pixels(z)
        print(f"  zone {z}: {len(px):>3} pixels, indices {min(px)}..{max(px)}")

    seen = sorted(i for z in range(ZONES) for i in zone_pixels(z))
    assert seen == sorted(DISH_PIXELS), "zones must tile the dish exactly once"
    print(f"\nzones tile all {len(DISH_PIXELS)} pixels inside the dish "
          f"({target:.1f} each if perfectly equal); "
          f"{PIXELS - len(DISH_PIXELS)} corner pixels stay dark")


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
        self._render()

    def _render(self):
        """Push current blue state to the panel."""
        self._px.fill((0, 0, 0))
        if recovery.active():
            # Nothing lit at all. Every pixel is zero, so the brightness scaler
            # has nothing to scale.
            self._px.show()
            return
        for z, level in enumerate(self._blue):
            if level <= 0:
                continue
            value = int(255 * min(level, 1.0))
            for i in zone_pixels(z):
                self._px[i] = (0, 0, value)
        self._px.brightness = STIM_BRIGHTNESS
        self._px.show()

    def set_zone(self, zone, intensity):
        """Set one zone's blue level, 0.0..1.0. All nine zones are drivable."""
        if not 0 <= zone < ZONES:
            raise ValueError(f"zone {zone} out of range 0..{ZONES - 1}")
        if not 0.0 <= intensity <= 1.0:
            raise ValueError(f"intensity {intensity} outside 0.0..1.0")
        # In recovery the panel shows no stimulus, so record none: active_zones
        # and everything logged from it stay true to what the dish received.
        self._blue[zone] = 0.0 if recovery.active() else intensity
        self._render()

    def active_zones(self):
        """Zones currently lit as stimulus, {zone: intensity}."""
        return {z: level for z, level in enumerate(self._blue) if level > 0}

    def stimulus_active(self):
        """Whether any drivable zone is currently lit."""
        return bool(self.active_zones())

    def clear_stimulus(self):
        """All zones off."""
        self._blue = [0.0] * ZONES
        self._render()

    def imaging_on(self):
        """Blue off, then the dish lit red, ready for an exposure.

        Split out from capture_flash because gpio/matrixd.py cannot take a
        callable across a socket and has to drive the two halves as separate
        requests. It has to be one definition in one place: when the daemon
        carried its own copy, changing the flash here left matrixd -- which is
        what actually owns the panel in the running system -- still doing the
        old thing, and the only symptom was in the images.
        """
        self._px.fill((0, 0, 0))
        self._px.show()
        time.sleep(BLANK_SETTLE)

        if recovery.active() or not IMAGING_RED:
            # No red backlight; the IR flood lights the exposure.
            return

        self._px.brightness = IMAGING_BRIGHTNESS
        # Only the dish, not the whole panel. The corner pixels sit outside the
        # dish wall, where they backlight nothing and instead flare off the rim
        # into the edge of the frame.
        self._px.fill((0, 0, 0))
        for i in DISH_PIXELS:
            self._px[i] = (255, 0, 0)
        self._px.show()
        time.sleep(BLANK_SETTLE)

    def imaging_off(self):
        """Red off, blue stimulus restored."""
        self._px.fill((0, 0, 0))
        self._px.show()
        time.sleep(BLANK_SETTLE)
        self._render()

    def capture_flash(self, exposure):
        """Blue off -> red on -> expose -> red off -> blue restored.

        The blue must be blanked or a lit zone blows out the frame. Pass the
        exposure as a callable; whatever it returns is returned to the caller,
        and the blue state is restored even if it raises.
        """
        try:
            self.imaging_on()
            return exposure()
        finally:
            self.imaging_off()

    def off(self):
        """Everything dark. For shutdown only."""
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
                print(f"zone {z}")
                m.set_zone(z, 1.0)
                time.sleep(2)
                m.clear_stimulus()
                time.sleep(0.3)
        elif mode == "capture":
            print("blank, flash red, expose 0.5s, restore")
            m.set_zone(4, 1.0)
            time.sleep(2)
            m.capture_flash(lambda: time.sleep(0.5))
            time.sleep(2)
        else:
            print(f"usage: sudo python3 {sys.argv[0]} [grid|zones|capture]")
            return 1
    except KeyboardInterrupt:
        pass
    finally:
        m.off()
    return 0


if __name__ == "__main__":
    sys.exit(main())
