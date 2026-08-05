"""Chamber environment: SHT31 temperature and humidity, and the fan relay.

No mock fallback. When the sensor is not readable this module reports that it
is not readable, and the API sends nulls. The previous version invented
plausible numbers whenever the sensor was missing, which is how a mock 55% RH
ended up on the dashboard for a chamber that was never being measured -- and
sham blocks are already part of this experiment's design, so fabricated
environmental data is not a harmless placeholder.

    ./scripts/py gpio/sensor.py          # one reading
    ./scripts/py gpio/sensor.py watch    # stream readings until ctrl-c
"""

import pathlib
import sys
import threading
import time
from datetime import datetime, timezone

import syspath  # noqa: F401  (path setup, must precede hardware imports)
from bus import SwitchGate, get_i2c


class SensorUnavailable(Exception):
    """The SHT31 could not be reached."""


class Sensor:
    """SHT31D on the shared I2C bus."""

    def __init__(self, address=0x44, gate=None):
        self.address = address
        self._gate = gate
        import adafruit_sht31d

        self._dev = adafruit_sht31d.SHT31D(get_i2c(), address=address)

    def read(self):
        """(temperature_c, relative_humidity). Raises SensorUnavailable."""
        try:
            # The SHT31 sits on the same bus as the ADC but does not switch
            # anything, so it needs no gate of its own. It is passed one only
            # so a caller can serialise bus access if it wants to.
            if self._gate is not None:
                with self._gate.quiet():
                    return self._dev.temperature, self._dev.relative_humidity
            return self._dev.temperature, self._dev.relative_humidity
        except (OSError, RuntimeError) as exc:
            raise SensorUnavailable(f"SHT31 at 0x{self.address:02X}: {exc}") from exc


class Relay:
    """A GPIO-switched relay with enforced minimum dwell times.

    Used by the fan. The vaporizer, if it is ever wired in, is the same shape:
    a pin, a deadband decided elsewhere, and dwell times that stop a controller
    chattering the contacts. Switching goes through the gate so no ADC
    conversion is in flight when the contacts move.
    """

    def __init__(self, pin, gate, min_on=0, min_off=0, name="relay"):
        self.pin = pin
        self.name = name
        self._gate = gate
        self._min_on = min_on
        self._min_off = min_off
        self._on = False
        # Start the clock in the past so the first transition is never blocked
        # by a dwell time that has not actually elapsed yet.
        self._changed_at = time.monotonic() - max(min_on, min_off)

        import RPi.GPIO as GPIO

        self._GPIO = GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

    @property
    def is_on(self):
        return self._on

    @property
    def held_for(self):
        """Seconds in the current state."""
        return time.monotonic() - self._changed_at

    def can_change(self):
        """Whether the dwell time for the current state has elapsed."""
        return self.held_for >= (self._min_on if self._on else self._min_off)

    def set(self, on, force=False):
        """Drive the relay. Returns True if the state actually changed.

        Refuses to change before the dwell time has elapsed unless forced;
        `force` exists for shutdown, where leaving a fan running because its
        minimum-on has not expired would be the wrong call.
        """
        if on == self._on:
            return False
        if not force and not self.can_change():
            return False

        with self._gate.switching():
            self._GPIO.output(self.pin, self._GPIO.HIGH if on else self._GPIO.LOW)
        self._on = on
        self._changed_at = time.monotonic()
        return True

    def cleanup(self):
        self.set(False, force=True)


class FanController:
    """Bang-bang humidity control with a floor schedule.

    Two rules, whichever asks for the fan wins:

    Humidity -- run above `rh_on`, stop below `rh_off`. The deadband between
    them is what stops the fan cycling on sensor noise around a single
    threshold.

    Floor -- run `floor_on` seconds in every `floor_period` regardless. A
    sealed chamber sitting at a stable 93% RH never trips the humidity rule,
    and the organism still needs the CO2 clearing. Without this the fan could
    stay off indefinitely.
    """

    def __init__(self, relay, rh_on=95.0, rh_off=91.0,
                 floor_period=1200, floor_on=60):
        if rh_off >= rh_on:
            raise ValueError(f"rh_off {rh_off} must be below rh_on {rh_on}")
        self.relay = relay
        self.rh_on = rh_on
        self.rh_off = rh_off
        self.floor_period = floor_period
        self.floor_on = floor_on
        self._window_start = time.monotonic()
        self._ran_this_window = 0.0
        self._last_tick = time.monotonic()
        self.reason = "startup"

    def _advance_window(self, now):
        if now - self._window_start >= self.floor_period:
            self._window_start = now
            self._ran_this_window = 0.0

    def tick(self, humidity):
        """Decide the fan state. `humidity` may be None if the sensor failed."""
        now = time.monotonic()
        if self.relay.is_on:
            self._ran_this_window += now - self._last_tick
        self._last_tick = now
        self._advance_window(now)

        floor_due = self._ran_this_window < self.floor_on

        if humidity is None:
            # No reading: fall back to the floor schedule alone. Ventilating on
            # a fixed duty is safe; guessing at humidity is not.
            want, reason = floor_due, "floor (no reading)"
        elif humidity >= self.rh_on:
            want, reason = True, f"humidity {humidity:.1f}% >= {self.rh_on}%"
        elif humidity <= self.rh_off:
            want, reason = floor_due, (
                "floor schedule" if floor_due else f"humidity {humidity:.1f}% <= {self.rh_off}%"
            )
        else:
            # Inside the deadband: hold, unless the floor schedule wants it.
            want = self.relay.is_on or floor_due
            reason = "deadband hold" if self.relay.is_on else (
                "floor schedule" if floor_due else "deadband idle"
            )

        self.reason = reason
        return self.relay.set(want)

    def status(self):
        return {
            "on": self.relay.is_on,
            "reason": self.reason,
            "held_for": round(self.relay.held_for, 1),
            "window_runtime": round(self._ran_this_window, 1),
            "window_target": self.floor_on,
        }


class EnvironmentMonitor:
    """Background thread: read the sensor, drive the fan, publish the latest."""

    def __init__(self, config, gate=None, log=None):
        self.gate = gate or SwitchGate(getattr(config, 'ADC_SWITCH_SETTLE', 0.25))
        self.interval = getattr(config, 'SENSOR_READ_INTERVAL', 1.0)
        self.log = log
        self.latest = {
            "temperature": None,
            "temperature_f": None,
            "humidity": None,
            "timestamp": 0,
            "datetime": None,
            "available": False,
            "error": None,
        }
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

        try:
            self.sensor = Sensor(getattr(config, 'SHT31_I2C_ADDRESS', 0x44))
        except Exception as exc:
            self.sensor = None
            self.latest["error"] = f"sensor init failed: {exc}"
            print(f"✗ SHT31 unavailable: {exc}")
        else:
            print(f"✓ SHT31 on I2C 0x{self.sensor.address:02X}")

        self.fan = None
        if getattr(config, 'FAN_ENABLED', False):
            try:
                relay = Relay(
                    config.FAN_PIN, self.gate,
                    min_on=getattr(config, 'FAN_MIN_ON', 180),
                    min_off=getattr(config, 'FAN_MIN_OFF', 180),
                    name="fan",
                )
                self.fan = FanController(
                    relay,
                    rh_on=getattr(config, 'FAN_RH_ON', 95.0),
                    rh_off=getattr(config, 'FAN_RH_OFF', 91.0),
                    floor_period=getattr(config, 'FAN_FLOOR_PERIOD', 1200),
                    floor_on=getattr(config, 'FAN_FLOOR_ON', 60),
                )
                print(f"✓ fan relay on GPIO {config.FAN_PIN}")
            except Exception as exc:
                print(f"✗ fan relay unavailable: {exc}")
        else:
            print("· fan disabled in config (not wired yet)")

    def _read_once(self):
        if self.sensor is None:
            return None, None, "sensor not initialised"
        try:
            temperature, humidity = self.sensor.read()
            return temperature, humidity, None
        except SensorUnavailable as exc:
            return None, None, str(exc)

    def poll(self):
        """One read-and-decide cycle. Returns the published reading."""
        temperature, humidity, error = self._read_once()
        reading = {
            # `temperature` stays Celsius: it is what the sensor reports and
            # what everything downstream logs. Fahrenheit is carried alongside
            # for display, computed here so the frontend never has to.
            "temperature": round(temperature, 2) if temperature is not None else None,
            "temperature_f": round(temperature * 9 / 5 + 32, 2) if temperature is not None else None,
            "humidity": round(humidity, 2) if humidity is not None else None,
            "timestamp": time.time(),
            "datetime": datetime.now(timezone.utc).astimezone().isoformat(),
            "available": error is None,
            "error": error,
        }
        if self.fan is not None:
            self.fan.tick(humidity)
            reading["fan"] = self.fan.status()

        with self._lock:
            self.latest = reading

        if self.log is not None:
            try:
                self.log.append({
                    "timestamp": reading["timestamp"],
                    "datetime": reading["datetime"],
                    "temperature_c": reading["temperature"],
                    "temperature_f": reading["temperature_f"],
                    "humidity_pct": reading["humidity"],
                    "fan_on": reading.get("fan", {}).get("on"),
                })
            except OSError as exc:
                print(f"environment log write failed: {exc}")
        return reading

    def snapshot(self):
        with self._lock:
            return dict(self.latest)

    def _run(self):
        while not self._stop.is_set():
            try:
                self.poll()
            except Exception as exc:
                print(f"environment loop error: {exc}")
            self._stop.wait(self.interval)

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self.fan is not None:
            self.fan.relay.cleanup()


def main():
    # Config lives beside this module's parent, so the deployed copy at
    # /var/www/sllm finds its own config rather than the checkout's.
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'api'))
    import config

    monitor = EnvironmentMonitor(config)
    watch = len(sys.argv) > 1 and sys.argv[1] == "watch"

    try:
        while True:
            reading = monitor.poll()
            if reading["available"]:
                line = (f"{reading['temperature']:5.2f} C  "
                        f"{reading['temperature_f']:6.2f} F  "
                        f"{reading['humidity']:5.2f} %RH")
            else:
                line = f"unavailable: {reading['error']}"
            if reading.get("fan"):
                line += f"   fan {'ON ' if reading['fan']['on'] else 'off'} ({reading['fan']['reason']})"
            print(line)
            if not watch:
                return 0
            time.sleep(monitor.interval)
    except KeyboardInterrupt:
        return 0
    finally:
        monitor.stop()


if __name__ == "__main__":
    sys.exit(main())
