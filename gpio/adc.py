"""Electrode sampling: ADS1115, three differential channels, 1 Hz.

Three recording electrodes are read against the reference in the corner under
the barrier zone. Differential, not single-ended: what matters is the potential
between a recording tip and the reference, and a differential pair rejects the
common-mode noise both wires pick up from the mains and from the panel.

Data rate 8 SPS: each conversion integrates over 125ms rather than the
library default's 7.8ms. Longer integration averages more of the noise away,
and 125ms spans several mains cycles so 50Hz pickup largely cancels. Three
channels at 8 SPS is 375ms, inside the 1 Hz cadence.

Gain 16 gives +/-0.256V full scale, 7.8125 uV per count. Plasmodium surface
potentials run to single-digit millivolts, so the default gain 1 would put the
entire signal inside the first 60 counts of a 32768-count range.

The ADS1115's hardware differential pairs are fixed: the mux can only measure
0-1, 0-3, 1-3 and 2-3. Reading channels 0, 1 and 2 against reference 3 is
therefore the only arrangement that gets three differential channels from one
chip, and it is why the reference electrode is wired to A3.

Every conversion runs inside `gate.quiet()`, so nothing is switching while the
sample is taken. See gpio/bus.py.

    ./scripts/py gpio/adc.py            # one sample from each channel
    ./scripts/py gpio/adc.py watch      # stream until ctrl-c
"""

import pathlib
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone

import syspath  # noqa: F401  (path setup, must precede hardware imports)
from bus import SwitchGate, get_i2c

# The ADS1115 mux supports only these differential pairs.
VALID_PAIRS = {(0, 1), (0, 3), (1, 3), (2, 3)}


class ADCUnavailable(Exception):
    """The ADS1115 could not be reached."""


class ElectrodeADC:
    """ADS1115 reading N channels differentially against a common reference."""

    def __init__(self, config, gate=None):
        self.gate = gate or SwitchGate(getattr(config, 'ADC_SWITCH_SETTLE', 0.25))
        self.address = getattr(config, 'ADC_ADDRESS', 0x48)
        self.gain = getattr(config, 'ADC_GAIN', 16)
        self.reference = getattr(config, 'ADC_REFERENCE_CHANNEL', 3)
        self.channels = tuple(getattr(config, 'ADC_CHANNELS', (0, 1, 2)))
        self.sample_rate = getattr(config, 'ADC_SAMPLE_RATE', 1.0)
        self.data_rate = getattr(config, 'ADC_DATA_RATE', 8)

        for channel in self.channels:
            if (channel, self.reference) not in VALID_PAIRS:
                raise ValueError(
                    f"channel {channel} against reference {self.reference} is not a "
                    f"differential pair the ADS1115 mux can select; valid pairs are "
                    f"{sorted(VALID_PAIRS)}"
                )

        import adafruit_ads1x15.ads1115 as ADS
        from adafruit_ads1x15.analog_in import AnalogIn

        try:
            self._ads = ADS.ADS1115(get_i2c(), address=self.address)
            self._ads.gain = self.gain
            self._ads.data_rate = self.data_rate
        except (OSError, ValueError) as exc:
            raise ADCUnavailable(f"ADS1115 at 0x{self.address:02X}: {exc}") from exc

        # Channel numbers are passed as plain ints rather than the library's
        # ADS.P0..P3 constants. Those constants were only ever 0..3, and the
        # 3.x releases dropped them entirely -- AnalogIn takes ints directly.
        # This works on both, which matters because the venv here has 2.2.23
        # and system python has 3.0.5.
        self._inputs = {
            channel: AnalogIn(self._ads, channel, self.reference)
            for channel in self.channels
        }

    def read_once(self):
        """One differential sample from every channel, in millivolts.

        All channels are taken inside a single gate hold so they belong to the
        same quiet window rather than being spread across a switching event.
        """
        try:
            with self.gate.quiet():
                return {
                    channel: self._inputs[channel].voltage * 1000.0
                    for channel in self.channels
                }
        except OSError as exc:
            raise ADCUnavailable(f"ADS1115 read failed: {exc}") from exc


class ElectrodeMonitor:
    """Background thread: sample at the configured rate into a rolling buffer."""

    def __init__(self, config, gate=None, log=None):
        self.interval = 1.0 / getattr(config, 'ADC_SAMPLE_RATE', 1.0)
        self.buffer = deque(maxlen=getattr(config, 'MAX_READINGS_BUFFER', 2400))
        # None disables disk logging; the standalone CLI passes nothing so a
        # bring-up check does not scribble into the run's record.
        self.log = log
        self.latest = {
            "timestamp": 0,
            "datetime": None,
            "channels": {},
            "value": None,
            "available": False,
            "error": None,
        }
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

        try:
            self.adc = ElectrodeADC(config, gate=gate)
        except Exception as exc:
            self.adc = None
            self.latest["error"] = f"ADC init failed: {exc}"
            print(f"✗ ADS1115 unavailable: {exc}")
        else:
            print(
                f"✓ ADS1115 on I2C 0x{self.adc.address:02X}, gain {self.adc.gain}, "
                f"channels {self.adc.channels} against reference {self.adc.reference}"
            )

    @property
    def gate(self):
        return self.adc.gate if self.adc else None

    def poll(self):
        """One sample cycle. Returns the published reading."""
        if self.adc is None:
            reading = dict(self.latest)
            reading["timestamp"] = time.time()
            with self._lock:
                self.latest = reading
            return reading

        try:
            channels = self.adc.read_once()
            error = None
        except ADCUnavailable as exc:
            channels, error = {}, str(exc)

        reading = {
            "timestamp": time.time(),
            "datetime": datetime.now(timezone.utc).astimezone().isoformat(),
            "channels": {str(k): round(v, 4) for k, v in channels.items()},
            # The frontend chart plots a single trace; give it the first
            # recording channel and let the rest ride along in `channels`.
            "value": round(next(iter(channels.values())), 4) if channels else None,
            "available": error is None,
            "error": error,
        }

        with self._lock:
            self.latest = reading
            if error is None:
                self.buffer.append(reading)

        if error is None and self.log is not None:
            row = {"timestamp": reading["timestamp"],
                   "datetime": reading["datetime"]}
            row.update({f"ch{k}_mv": v for k, v in reading["channels"].items()})
            try:
                self.log.append(row)
            except OSError as exc:
                # A full or unwritable disk must not stop sampling; the
                # in-memory buffer keeps the loop running either way.
                print(f"electrode log write failed: {exc}")
        return reading

    def snapshot(self):
        with self._lock:
            return dict(self.latest)

    def history(self, limit=None):
        with self._lock:
            items = list(self.buffer)
        return items[-limit:] if limit else items

    def _run(self):
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                self.poll()
            except Exception as exc:
                print(f"adc loop error: {exc}")
            # Subtract the work so the cadence stays at the configured rate
            # rather than drifting by however long a conversion took.
            self._stop.wait(max(0.0, self.interval - (time.monotonic() - started)))

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def stop(self):
        self._stop.set()


def main():
    # Config lives beside this module's parent, so the deployed copy at
    # /var/www/sllm finds its own config rather than the checkout's.
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'api'))
    import config

    monitor = ElectrodeMonitor(config)
    if monitor.adc is None:
        return 1
    watch = len(sys.argv) > 1 and sys.argv[1] == "watch"

    try:
        while True:
            reading = monitor.poll()
            if reading["available"]:
                print("   ".join(
                    f"ch{channel}-{monitor.adc.reference} {value:+9.4f} mV"
                    for channel, value in reading["channels"].items()
                ))
            else:
                print(f"unavailable: {reading['error']}")
            if not watch:
                return 0
            time.sleep(monitor.interval)
    except KeyboardInterrupt:
        return 0
    finally:
        monitor.stop()


if __name__ == "__main__":
    sys.exit(main())
