"""Averaged mux-settling test -- the sensitive version of tip-impedance.

A single settling trace is unreadable here: at 860 SPS the electrodes pick up
several millivolts of periodic interference, which is far larger than the
settling step being looked for. But that interference is not synchronised to
when the mux switches, so averaging many repeats cancels it while the settling
transient -- which IS synchronised to the switch, every time -- survives.

A low-impedance tip is settled by the first conversion: the averaged trace is
flat. A high-impedance tip charges the switched-capacitor input slowly and the
averaged trace approaches its final value over several samples.

    sudo ./scripts/py scripts/electrode_settling.py
"""

import pathlib
import statistics
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'api'))
sys.path.insert(0, str(ROOT / 'gpio'))

import syspath  # noqa: F401
import config
from bus import SwitchGate, get_i2c

import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

REFERENCE = getattr(config, 'ADC_REFERENCE_CHANNEL', 3)
CHANNELS = tuple(getattr(config, 'ADC_CHANNELS', (0, 1, 2)))
REPEATS = 60
DEPTH = 10


def main():
    gate = SwitchGate(getattr(config, 'ADC_SWITCH_SETTLE', 0.25))
    ads = ADS.ADS1115(get_i2c(), address=getattr(config, 'ADC_ADDRESS', 0x48))
    ads.data_rate = 860
    ads.gain = 16

    print(f"averaging {REPEATS} switch events per channel, {DEPTH} samples deep\n")
    for c in CHANNELS:
        park = AnalogIn(ads, 2 if c != 2 else 0, REFERENCE)
        chan = AnalogIn(ads, c, REFERENCE)
        traces = []
        for _ in range(REPEATS):
            with gate.quiet():
                park.voltage
                traces.append([chan.voltage * 1000.0 for _ in range(DEPTH)])
            time.sleep(0.004)

        avg = [statistics.fmean(t[i] for t in traces) for i in range(DEPTH)]
        sem = [statistics.pstdev([t[i] for t in traces]) / (REPEATS ** 0.5)
               for i in range(DEPTH)]
        settled = statistics.fmean(avg[-3:])
        step = avg[0] - settled
        # Significant only if the first-sample offset clears its own error bar.
        verdict = "FLAT (low impedance)" if abs(step) < 3 * sem[0] else \
                  "SETTLING TRANSIENT -- high impedance"
        print(f"  ch{c}  settled {settled:+8.3f} mV   "
              f"first-sample step {step:+7.3f} +/- {sem[0]:.3f} mV   {verdict}")
        print("       " + " ".join(f"{v:+7.2f}" for v in avg))
        print("   +/- " + " ".join(f"{s:7.2f}" for s in sem))
    return 0


if __name__ == "__main__":
    sys.exit(main())
