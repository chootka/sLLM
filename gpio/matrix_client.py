"""Talk to the root-owned matrix daemon, looking exactly like leds.Matrix.

The panel needs root because rpi_ws281x goes through /dev/mem. The API must not
be root because it is exposed to the internet. gpio/matrixd.py resolves that by
being the only privileged process; this is the client side.

MatrixClient presents the same methods as leds.Matrix -- set_zone,
clear_stimulus, active_zones, stimulus_active, capture_flash, off -- so nothing
that drives the panel has to know which one it is holding.

    from matrix_client import open_matrix
    matrix, error = open_matrix()

`open_matrix` prefers the daemon and falls back to driving the panel directly
if this process happens to be root and the daemon is not running, which keeps
the standalone tools working unchanged.
"""

import json
import socket

import syspath  # noqa: F401  (path setup, must precede hardware imports)
import leds

from matrixd import SOCKET_PATH

# Longer than the daemon's own BLANK_SETTLE pauses, which a flash_begin call
# blocks on, plus room for the panel write itself.
TIMEOUT_S = 10.0

ZONES = leds.ZONES
BARRIER_ZONE = leds.BARRIER_ZONE


class MatrixUnavailable(Exception):
    """The daemon could not be reached, or refused the command."""


class MatrixClient:
    """A leds.Matrix work-alike backed by the daemon.

    One connection per request, matching the daemon. Nothing is cached: the
    daemon is the single source of truth for panel state, and this process is
    not the only client -- llm/loop.py drives zones through the same socket
    while the API is serving. A cached `active_zones` here would go stale the
    moment the loop acted.
    """

    def __init__(self, path=SOCKET_PATH):
        self.path = path
        # Fail construction if the daemon is not there, so callers get the same
        # "matrix is None" signal they already handle for a missing panel.
        self._call("ping")

    def _call(self, cmd, **kwargs):
        request = json.dumps({"cmd": cmd, **kwargs}) + "\n"
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(TIMEOUT_S)
                sock.connect(self.path)
                sock.sendall(request.encode())

                buf = b""
                while b"\n" not in buf:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
        except (OSError, socket.timeout) as exc:
            raise MatrixUnavailable(f"matrixd at {self.path}: {exc}") from exc

        if not buf.strip():
            raise MatrixUnavailable("matrixd closed the connection without replying")
        try:
            reply = json.loads(buf.strip())
        except ValueError as exc:
            raise MatrixUnavailable(f"malformed reply from matrixd: {exc}") from exc

        if not reply.get("ok"):
            raise MatrixUnavailable(reply.get("error", "unknown error"))
        return reply

    # --- the leds.Matrix surface -------------------------------------------

    def set_zone(self, zone, intensity):
        self._call("set_zone", zone=zone, intensity=intensity)

    def clear_stimulus(self):
        self._call("clear_stimulus")

    def active_zones(self):
        return {int(z): v for z, v in self._call("active_zones")["zones"].items()}

    def stimulus_active(self):
        return self._call("stimulus_active")["active"]

    def capture_flash(self, exposure):
        """Blue off -> red on -> expose -> red off -> blue restored.

        Same contract as leds.Matrix.capture_flash, including restoring the blue
        state if the exposure raises. The difference is that the restore is no
        longer guaranteed by this `finally` alone: if this process dies between
        the two calls the panel would stay red, so matrixd runs its own watchdog
        and restores without us. This `finally` is the fast path, not the only
        one.
        """
        self._call("flash_begin")
        try:
            return exposure()
        finally:
            try:
                self._call("flash_end")
            except MatrixUnavailable as exc:
                # Do not mask an exposure failure with a socket failure. The
                # daemon's watchdog restores the panel regardless.
                print(f"matrix flash_end failed, watchdog will restore: {exc}")

    def off(self):
        self._call("off")


def open_matrix(allow_direct=True):
    """(matrix, error). Prefers the daemon, falls back to the panel directly.

    The fallback exists for the standalone tools, which are run with sudo and
    may be used when the daemon is stopped. The API never takes it: it is not
    root, so leds.Matrix() would fail anyway, and it should not be the thing
    that owns the panel even if it could.
    """
    try:
        return MatrixClient(), None
    except MatrixUnavailable as exc:
        daemon_error = exc

    if not allow_direct:
        return None, daemon_error

    try:
        return leds.Matrix(), None
    except Exception as exc:  # noqa: BLE001 -- report, never raise, no panel is survivable
        return None, f"daemon: {daemon_error}; direct: {exc}"
