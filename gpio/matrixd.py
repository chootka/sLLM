"""Root-owned matrix helper. Owns the panel, takes commands over a unix socket.

`rpi_ws281x` drives the PWM peripheral through /dev/mem, so whatever holds the
WS2812B panel must be root. The API must not be: it is a Flask app reachable
from the public internet through nginx. This daemon is the seam between those
two facts. It is the only thing that runs privileged, it speaks a fixed
vocabulary of nine commands, and it never evaluates anything a client sends.

    sudo python3 gpio/matrixd.py            # run in the foreground
    sudo systemctl start sllm-matrixd       # or as the service

Clients use gpio/matrix_client.py, which presents the same methods as
leds.Matrix, so callers do not care which they hold.

Protocol: newline-delimited JSON, one request per connection.

    -> {"cmd": "set_zone", "zone": 4, "intensity": 0.8}
    <- {"ok": true}
    <- {"ok": false, "error": "zone 2 is the barrier and is not drivable"}

One request per connection is deliberate. A persistent connection would save a
few hundred microseconds and cost the ability to reason about what happens when
a client dies holding it, which for this device means leaving the panel lit.

## The flash is the whole reason this is not trivial

leds.Matrix.capture_flash takes the exposure as a callable and restores the
blue stimulus in a `finally`. A callable cannot cross a socket, so the flash
splits into flash_begin and flash_end with the client's exposure in between --
and that reintroduces exactly the failure the `finally` existed to prevent. If
the client crashes, is killed, or simply loses the socket between the two
calls, the panel is left at IMAGING_BRIGHTNESS across all 256 pixels, roughly
0.8A of red, held over a living organism until someone notices.

So flash_begin arms a watchdog. If flash_end does not arrive within
FLASH_TIMEOUT_S the daemon restores the panel by itself. The client losing its
grip is a survivable event, not a stuck light.
"""

import json
import os
import signal
import socket
import sys
import threading
import time

import syspath  # noqa: F401  (path setup, must precede hardware imports)
import leds

SOCKET_PATH = "/run/sllm/matrix.sock"

# The unprivileged account the API runs as. The socket is chowned to this group
# with mode 0660, so the API can talk to the daemon and nothing else on the box
# can. This is the whole access control story; there is no auth in the protocol.
#
# `sllm` is a dedicated system account with no shell, no home and no sudo -- not
# a human's login. That is the point: the API is reachable from the internet, so
# whatever it runs as is what an attacker gets on a bad day. As a human account
# that would mean SSH keys, git credentials and a shell profile that can be
# rewritten to capture a sudo password. As `sllm` it means the data directory
# and one systemd unit.
#
# chootka is a member of this group, so the standalone tools still work by hand.
SOCKET_GROUP = "sllm"
SOCKET_MODE = 0o660

# How long a flash may stay open before the daemon restores without being told.
# Generous next to a still exposure, which is well under a second, but short
# enough that a wedged client is a blink rather than a sustained dose.
FLASH_TIMEOUT_S = 15.0

RECV_LIMIT = 64 * 1024  # a request is a few dozen bytes; this is a sanity cap

# How often the panel is re-sent its current frame.
#
# leds.Matrix only writes on a state change, which during a live run is once
# per ten minute turn. A frame that does not arrive intact -- or a chain that
# latches a bad state -- therefore persists for the whole turn, because nothing
# ever writes again to correct it. That is what made demo mode look dead: the
# daemon held the right state, and the panel did not show it.
#
# This re-sends the SAME frame, which matters for the electrode measurements.
# bus.SwitchGate exists because changing panel state pulls amps through grounds
# shared with the electrode reference, and a conversion taken across that edge
# measures the switching. An identical frame changes no LED's current, so it
# creates no such edge -- it is 256*24 bits of data-line activity and nothing
# more. Set to 0 to disable the refresh entirely.
REFRESH_INTERVAL_S = 2.0


class MatrixService:
    """The panel plus the flash state machine. All access is serialised.

    One lock over every panel operation. The device is a single chain of 256
    pixels with brightness as global state -- two writers interleaving would
    produce a frame that is neither of their intentions.
    """

    def __init__(self):
        self._matrix = leds.Matrix()
        self._lock = threading.RLock()
        self._flashing = False
        self._flash_deadline = 0.0
        self._flash_expired = False
        self._stop = threading.Event()
        self._watchdog = threading.Thread(target=self._watch, daemon=True)
        self._watchdog.start()

    # --- flash watchdog -----------------------------------------------------

    def _watch(self):
        """Restore the panel if a flash outlives its client, and refresh it.

        Two jobs on one timer because both are "put the panel back the way it
        should be", and a second thread would need the same lock anyway.

        The refresh never runs during a flash. Mid-flash the panel is red at
        IMAGING_BRIGHTNESS and `_render` would repaint it blue, blanking the
        backlight in the middle of somebody's exposure.
        """
        last_refresh = 0.0
        while not self._stop.wait(0.25):
            with self._lock:
                if self._flashing:
                    if time.monotonic() < self._flash_deadline:
                        continue
                    # Do not call _end_flash's bookkeeping twice; restore and mark.
                    self._flashing = False
                    self._flash_expired = True
                    try:
                        self._matrix._render()
                    except Exception as exc:  # noqa: BLE001 -- must not kill the thread
                        print(f"flash watchdog restore failed: {exc}", flush=True)
                    else:
                        print(
                            f"flash watchdog fired after {FLASH_TIMEOUT_S}s; "
                            "panel restored without a flash_end",
                            flush=True,
                        )
                    last_refresh = time.monotonic()
                    continue

                if REFRESH_INTERVAL_S <= 0:
                    continue
                now = time.monotonic()
                if now - last_refresh < REFRESH_INTERVAL_S:
                    continue
                last_refresh = now
                try:
                    self._matrix._render()
                except Exception as exc:  # noqa: BLE001 -- must not kill the thread
                    # Not fatal and not worth a line every two seconds; the next
                    # tick tries again. A permanently broken panel shows up as a
                    # failing set_zone, which the client already reports.
                    print(f"panel refresh failed: {exc}", flush=True)

    # --- commands -----------------------------------------------------------

    def ping(self):
        return {"zones": leds.ZONES, "barrier": leds.BARRIER_ZONE}

    def set_zone(self, zone, intensity):
        with self._lock:
            self._matrix.set_zone(int(zone), float(intensity))
        return {}

    def clear_stimulus(self):
        with self._lock:
            self._matrix.clear_stimulus()
        return {}

    def active_zones(self):
        with self._lock:
            # JSON object keys must be strings; the client casts them back.
            return {"zones": {str(z): v for z, v in self._matrix.active_zones().items()}}

    def stimulus_active(self):
        with self._lock:
            return {"active": self._matrix.stimulus_active()}

    def flash_begin(self):
        """Blue off, red on, and start the clock. The client exposes next."""
        with self._lock:
            if self._flashing:
                raise RuntimeError("a flash is already open")
            px = self._matrix._px
            px.fill((0, 0, 0))
            px.show()
            time.sleep(leds.BLANK_SETTLE)

            px.brightness = leds.IMAGING_BRIGHTNESS
            px.fill((255, 0, 0))
            px.show()
            time.sleep(leds.BLANK_SETTLE)

            self._flashing = True
            self._flash_expired = False
            self._flash_deadline = time.monotonic() + FLASH_TIMEOUT_S
        return {"timeout": FLASH_TIMEOUT_S}

    def flash_end(self):
        """Red off, blue restored. Safe to call after the watchdog beat us."""
        with self._lock:
            expired = self._flash_expired
            self._flash_expired = False
            if not self._flashing:
                # Either the watchdog already restored, or this is a stray call.
                # Both are harmless; report which so the client can log it.
                return {"expired": expired}
            self._flashing = False
            px = self._matrix._px
            px.fill((0, 0, 0))
            px.show()
            time.sleep(leds.BLANK_SETTLE)
            self._matrix._render()
        return {"expired": False}

    def off(self):
        with self._lock:
            self._flashing = False
            self._matrix.off()
        return {}

    def shutdown(self):
        self._stop.set()
        try:
            self.off()
        except Exception as exc:  # noqa: BLE001
            print(f"shutdown: could not blank the panel: {exc}", flush=True)


COMMANDS = {
    "ping": lambda svc, req: svc.ping(),
    "set_zone": lambda svc, req: svc.set_zone(req["zone"], req["intensity"]),
    "clear_stimulus": lambda svc, req: svc.clear_stimulus(),
    "active_zones": lambda svc, req: svc.active_zones(),
    "stimulus_active": lambda svc, req: svc.stimulus_active(),
    "flash_begin": lambda svc, req: svc.flash_begin(),
    "flash_end": lambda svc, req: svc.flash_end(),
    "off": lambda svc, req: svc.off(),
}


def handle(svc, conn):
    """One request, one response, then close."""
    try:
        conn.settimeout(10.0)
        buf = b""
        oversized = False
        while b"\n" not in buf:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
            if len(buf) > RECV_LIMIT:
                oversized = True
                break
        raw = buf.strip()
        if not raw and not oversized:
            return

        try:
            if oversized:
                raise ValueError("request too large")
            req = json.loads(raw)
            cmd = req.get("cmd")
            handler = COMMANDS.get(cmd)
            if handler is None:
                raise ValueError(f"unknown command {cmd!r}")
            reply = {"ok": True, **handler(svc, req)}
        except Exception as exc:  # noqa: BLE001 -- every failure is a reply
            reply = {"ok": False, "error": str(exc)}

        conn.sendall((json.dumps(reply) + "\n").encode())
    except (OSError, socket.timeout):
        pass  # client vanished; the watchdog covers any open flash
    finally:
        try:
            conn.close()
        except OSError:
            pass


def bind_socket():
    """Bind the unix socket with the right ownership, replacing any stale one."""
    directory = os.path.dirname(SOCKET_PATH)
    os.makedirs(directory, exist_ok=True)
    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    server.listen(8)

    import grp

    try:
        gid = grp.getgrnam(SOCKET_GROUP).gr_gid
        os.chown(SOCKET_PATH, 0, gid)
    except KeyError:
        print(f"! group {SOCKET_GROUP} not found; socket left root-owned", flush=True)
    os.chmod(SOCKET_PATH, SOCKET_MODE)
    return server


def main():
    if os.geteuid() != 0:
        print("matrixd must run as root: rpi_ws281x needs /dev/mem")
        return 1

    try:
        svc = MatrixService()
    except Exception as exc:  # noqa: BLE001
        print(f"matrix unavailable: {exc}")
        return 1

    server = bind_socket()
    print(f"matrixd listening on {SOCKET_PATH} "
          f"(group {SOCKET_GROUP}, mode {SOCKET_MODE:o})", flush=True)

    stopping = threading.Event()

    def _signal(_sig, _frame):
        stopping.set()
        try:
            # Unblock accept() by poking our own socket.
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as poke:
                poke.connect(SOCKET_PATH)
        except OSError:
            pass

    signal.signal(signal.SIGTERM, _signal)
    signal.signal(signal.SIGINT, _signal)

    try:
        while not stopping.is_set():
            try:
                conn, _ = server.accept()
            except OSError:
                break
            if stopping.is_set():
                conn.close()
                break
            threading.Thread(target=handle, args=(svc, conn), daemon=True).start()
    finally:
        print("matrixd stopping; blanking the panel", flush=True)
        svc.shutdown()
        server.close()
        try:
            os.unlink(SOCKET_PATH)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
