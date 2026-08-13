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

    The relay board is **active-high** -- verified on the bench by listening to
    the contact: HIGH closes it, LOW opens it. So driving the pin LOW here at
    startup leaves the load off, which is what we want from a service that may
    restart at any time.

    `pwm_pin` is an optional companion pin held high for as long as the relay
    is closed. The Noctua is a 4-pin fan, and a 4-pin fan only free-runs at
    full speed when its PWM line is genuinely floating. Ours is not floating:
    the Pi idles that pin as an input with the pull-down enabled, which the fan
    reads as a hard 0% duty and obeys by not turning. That is a relay that
    clicks and a fan that sits still, which looks exactly like a wiring fault
    and is not. Raising the pin with the relay is the whole fix.

    This is a level, not a waveform. Nothing here asks for a fan speed --
    `FanController` is bang-bang -- so there is no duty cycle for a real PWM
    signal to carry. Hardware PWM would also need a `pwm-2chan` overlay and a
    reboot, and this Pi's `RPi.GPIO` is the `rpi-lgpio` shim, so `GPIO.PWM`
    would be software-timed and jittery. If full speed ever proves too strong,
    that overlay is the upgrade path.
    """

    def __init__(self, pin, gate, min_on=0, min_off=0, name="relay", pwm_pin=None):
        self.pin = pin
        self.pwm_pin = pwm_pin
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
        if pwm_pin is not None:
            GPIO.setup(pwm_pin, GPIO.OUT)
            GPIO.output(pwm_pin, GPIO.LOW)

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
            # Order matters. Raise the speed command before applying power so
            # the fan never sees a live rail with a 0% duty on its PWM line,
            # and cut power before releasing it on the way down.
            if on:
                if self.pwm_pin is not None:
                    self._GPIO.output(self.pwm_pin, self._GPIO.HIGH)
                self._GPIO.output(self.pin, self._GPIO.HIGH)
            else:
                self._GPIO.output(self.pin, self._GPIO.LOW)
                if self.pwm_pin is not None:
                    self._GPIO.output(self.pwm_pin, self._GPIO.LOW)
        self._on = on
        self._changed_at = time.monotonic()
        return True

    def cleanup(self):
        self.set(False, force=True)


class FanController:
    """Timed air exchange. The fan exists to keep fresh air moving so mould
    does not establish -- that is its only job.

    It is not humidity control and not temperature control. It will move both,
    and that is accepted, but neither is a setpoint and neither is allowed to
    decide when the fan runs. An earlier version of this class had it backwards,
    treating relative humidity as the primary rule and the timed cycle as a
    fallback named `floor_due`; if that framing turns up anywhere else in the
    tree, it is wrong.

    The rule: run `cycle_on` seconds in every `cycle_period`. Short frequent
    bursts rather than long runs, so the chamber gets exchanged without being
    swept out.

    `rh_on`/`rh_off` are an optional extra-ventilation override, off by default
    (`rh_on=None`). It is deliberately not part of the mould logic -- it is
    there only if a run ever turns up a reason to move more air at saturation.
    When set, `rh_off` must sit below `rh_on`; the gap between them is what
    stops the fan chattering on sensor noise around a single threshold.
    """

    def __init__(self, relay, rh_on=None, rh_off=None,
                 cycle_period=300, cycle_on=60):
        if rh_on is not None and (rh_off is None or rh_off >= rh_on):
            raise ValueError(f"rh_off {rh_off} must be below rh_on {rh_on}")
        if not 0 < cycle_on <= cycle_period:
            raise ValueError(
                f"cycle_on {cycle_on} must be above 0 and within cycle_period {cycle_period}"
            )
        self.relay = relay
        self.rh_on = rh_on
        self.rh_off = rh_off
        self.cycle_period = cycle_period
        self.cycle_on = cycle_on
        self._window_start = time.monotonic()
        self._ran_this_window = 0.0
        self._last_tick = time.monotonic()
        self.reason = "startup"

    def _advance_window(self, now):
        if now - self._window_start >= self.cycle_period:
            self._window_start = now
            self._ran_this_window = 0.0

    def tick(self, humidity):
        """Decide the fan state. `humidity` may be None if the sensor failed."""
        now = time.monotonic()
        if self.relay.is_on:
            self._ran_this_window += now - self._last_tick
        self._last_tick = now
        self._advance_window(now)

        # The air-exchange cycle is the rule, and it is deliberately evaluated
        # without reference to any sensor. A failed SHT31 must not be able to
        # stop the chamber being ventilated.
        cycle_due = self._ran_this_window < self.cycle_on
        want, reason = cycle_due, (
            "air exchange" if cycle_due else "exchange satisfied"
        )

        # Optional extra ventilation at saturation. It can only ever add run
        # time on top of the cycle, never subtract it.
        if self.rh_on is not None and humidity is not None:
            if humidity >= self.rh_on:
                want, reason = True, f"humidity {humidity:.1f}% >= {self.rh_on}%"
            elif humidity > self.rh_off and self.relay.is_on:
                want, reason = True, "humidity deadband hold"

        self.reason = reason
        return self.relay.set(want)

    def status(self):
        return {
            "on": self.relay.is_on,
            "reason": self.reason,
            "held_for": round(self.relay.held_for, 1),
            "window_runtime": round(self._ran_this_window, 1),
            "window_target": self.cycle_on,
            "window_period": self.cycle_period,
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
                    min_on=getattr(config, 'FAN_MIN_ON', 60),
                    min_off=getattr(config, 'FAN_MIN_OFF', 60),
                    name="fan",
                    pwm_pin=getattr(config, 'FAN_PWM_PIN', None),
                )
                self.fan = FanController(
                    relay,
                    rh_on=getattr(config, 'FAN_RH_ON', None),
                    rh_off=getattr(config, 'FAN_RH_OFF', None),
                    cycle_period=getattr(config, 'FAN_CYCLE_PERIOD', 300),
                    cycle_on=getattr(config, 'FAN_CYCLE_ON', 60),
                )
                pwm = getattr(config, 'FAN_PWM_PIN', None)
                print(f"✓ fan relay on GPIO {config.FAN_PIN}"
                      + (f", PWM held high on GPIO {pwm}" if pwm is not None else ""))
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
