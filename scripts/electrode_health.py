"""Test the electrode tips electrically, using only the ADS1115.

A DC offset reading proves an electrode is CONNECTED. It does not prove the tip
is undamaged: a cracked or partly de-plated tip still conducts and still gives a
clean, stable number. What damage actually changes is the tip's SOURCE
IMPEDANCE, and that is measurable from the ADC alone -- three ways:

  consistency  The mux can read the 0-1 pair directly as well as 0-3 and 1-3.
               A linear, well-behaved set of electrodes satisfies
               (0-3) - (1-3) = (0-1). If that does not close, something in the
               chain is nonlinear or loading.

  gain         The ADS1115's input impedance falls as PGA gain rises. A
               low-impedance tip is unaffected; a high-impedance one forms a
               divider with the input and reads LOW at high gain. Absolute
               datasheet impedances are not needed and not used -- the three
               channels are compared against each other, so a damaged tip shows
               up as the one channel whose reading moves when the others do not.

  settling     The input is switched-capacitor. After the mux lands on a
               channel, the sampling cap charges through the source impedance.
               A low-impedance tip is settled by the first conversion; a
               high-impedance one approaches exponentially over many. This is
               the mechanism behind the +81mV "reading" from the open ch1 on
               2026-08-15 -- it was a settling artifact, not a potential.

Nothing here can distinguish three EQUALLY damaged tips from three good ones;
these are comparative tests. What they catch is one tip unlike the others.

    sudo ./scripts/py scripts/electrode_health.py
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
GAINS = (16, 8, 4, 2, 1)
AVG_N = 48


def mean_mv(chan, n=AVG_N):
    vals = [chan.voltage * 1000.0 for _ in range(n)]
    return statistics.fmean(vals), statistics.pstdev(vals)


def main():
    gate = SwitchGate(getattr(config, 'ADC_SWITCH_SETTLE', 0.25))
    ads = ADS.ADS1115(get_i2c(), address=getattr(config, 'ADC_ADDRESS', 0x48))
    ads.data_rate = 860          # fastest, so the settling test has resolution

    print("=" * 68)
    print("TEST 1  consistency: does (ch0-3) - (ch1-3) equal (ch0-1)?")
    print("=" * 68)
    ads.gain = 16
    with gate.quiet():
        a, _ = mean_mv(AnalogIn(ads, 0, REFERENCE))
        b, _ = mean_mv(AnalogIn(ads, 1, REFERENCE))
        direct, _ = mean_mv(AnalogIn(ads, 0, 1))
    predicted = a - b
    err = direct - predicted
    print(f"  ch0-3     {a:+9.3f} mV")
    print(f"  ch1-3     {b:+9.3f} mV")
    print(f"  predicted ch0-1 = {predicted:+9.3f} mV")
    print(f"  measured  ch0-1 = {direct:+9.3f} mV")
    print(f"  closure error   = {err:+9.3f} mV  "
          f"({'OK' if abs(err) < 1.0 else 'SUSPECT — chain is not linear'})")

    print()
    print("=" * 68)
    print("TEST 2  gain dependence: a high-impedance tip sags at high gain")
    print("=" * 68)
    print(f"  {'gain':>6} " + "".join(f"{'ch%d' % c:>22}" for c in CHANNELS))
    table = {c: {} for c in CHANNELS}
    for gain in GAINS:
        ads.gain = gain
        row = ""
        with gate.quiet():
            for c in CHANNELS:
                mv, sd = mean_mv(AnalogIn(ads, c, REFERENCE))
                table[c][gain] = mv
                row += f"{mv:+12.3f} ±{sd:5.3f} "
        print(f"  {gain:>6} " + row)

    print()
    print("  drift from gain 16 to gain 1 (relative to the gain-16 reading):")
    for c in CHANNELS:
        hi, lo = table[c][16], table[c][1]
        pct = (lo - hi) / abs(hi) * 100 if hi else float('nan')
        print(f"    ch{c}: {hi:+9.3f} -> {lo:+9.3f} mV   ({pct:+6.1f}%)")

    print()
    print("=" * 68)
    print("TEST 3  settling after the mux lands on the channel")
    print("=" * 68)
    ads.gain = 16
    for c in CHANNELS:
        park = AnalogIn(ads, 2 if c != 2 else 0, REFERENCE)
        chan = AnalogIn(ads, c, REFERENCE)
        with gate.quiet():
            park.voltage                       # force the mux elsewhere
            time.sleep(0.05)
            trace = [chan.voltage * 1000.0 for _ in range(12)]
        settled = statistics.fmean(trace[-4:])
        excursion = trace[0] - settled
        print(f"  ch{c}: first={trace[0]:+8.3f}  settled={settled:+8.3f}  "
              f"first-sample excursion {excursion:+7.3f} mV")
        print("        " + " ".join(f"{v:+7.2f}" for v in trace[:8]))

    ads.gain = getattr(config, 'ADC_GAIN', 16)
    print()
    print("gain register restored to", ads.gain)
    return 0


if __name__ == "__main__":
    sys.exit(main())
