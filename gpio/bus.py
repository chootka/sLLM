"""Shared I2C bus and the switching gate.

Two things here that everything else on the hardware side depends on.

**One bus object.** The ADS1115 and the SHT31 sit on the same two wires.
Blinka's busio.I2C is not free to construct repeatedly, and an earlier version
of the API opened its own instance in a retry loop with the sensor unplugged,
which jammed the i2c_designware driver hard enough that the adapter had to be
unbound. One module-level instance, created lazily, shared by everyone.

**One gate.** From the build notes: the ADC must not convert while the matrix,
the fan or a relay is being energised. A 16x16 panel changing state pulls
amps through grounds shared with the electrode reference, and a conversion
taken across that edge measures the switching, not the organism. Anything that
switches wraps it in `gate.switching()`; the ADC takes its samples inside
`gate.quiet()`, which additionally waits out a settle time after the last
switch before it will hand over.
"""

import threading
import time
from contextlib import contextmanager

_i2c = None
_i2c_lock = threading.Lock()


def get_i2c():
    """The one I2C bus, created on first use.

    Constructed lazily rather than at import so that importing this module is
    always safe -- a caller that only wants the zone map should not touch the
    hardware, and an import-time failure here would take the whole API down.
    """
    global _i2c
    with _i2c_lock:
        if _i2c is None:
            import board
            import busio

            _i2c = busio.I2C(board.SCL, board.SDA)
        return _i2c


class SwitchGate:
    """Mutual exclusion between switching events and ADC conversions.

    Not a plain lock: after a switching event releases, conversions stay
    blocked for `settle` seconds so the rail and the electrode reference have
    time to come back to rest.
    """

    def __init__(self, settle):
        self._lock = threading.Lock()
        self._settle = settle
        # monotonic, not wall clock -- this is a duration comparison and must
        # not jump if the system clock is stepped by NTP mid-run.
        self._last_switch = 0.0

    @contextmanager
    def switching(self):
        """Hold for the duration of energising something.

        Blocks until any in-flight conversion finishes, and starts the settle
        countdown on release.
        """
        with self._lock:
            try:
                yield
            finally:
                self._last_switch = time.monotonic()

    @contextmanager
    def quiet(self):
        """Hold for the duration of a conversion.

        Waits until the bus has been switch-free for the settle time, then
        holds the lock so nothing can switch underneath the conversion.
        """
        while True:
            with self._lock:
                remaining = self._settle - (time.monotonic() - self._last_switch)
                if remaining <= 0:
                    yield
                    return
            # Released before sleeping, so a switching caller is not blocked
            # behind a conversion that is only waiting to start.
            time.sleep(remaining)

    def since_last_switch(self):
        """Seconds since the last switching event released."""
        return time.monotonic() - self._last_switch
