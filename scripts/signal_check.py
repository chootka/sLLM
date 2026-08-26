#!/usr/bin/env python3
"""Is there an organism in this recording, or is it the chamber?

Run it on a baseline (empty dish, undisturbed) to calibrate MIN_DEPTH, then on
a real recording to see whether anything clears it.

    ./scripts/py scripts/signal_check.py --baseline BASELINE.csv
    ./scripts/py scripts/signal_check.py RECORDING.csv --baseline BASELINE.csv

Both arguments accept a date (20260820), a filename, or a path. Files are
looked for in the deployed tree as well as the checkout, and in the `test/`
subdirectory.
"""

import argparse
import csv
import glob
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'llm', 'filters'))
from reducer import _period_and_depth, PERIOD_MIN, PERIOD_MAX  # noqa: E402

WIN, STEP = 1800, 450
SEARCH = ['/var/www/sllm/data/readings', os.path.join(os.path.dirname(HERE), 'data', 'readings')]


def resolve(token):
    if os.path.exists(token):
        return token
    names = [token, f'electrodes_{token}.csv', f'{token}.csv']
    for root in SEARCH:
        for sub in ('', 'test'):
            for name in names:
                hit = glob.glob(os.path.join(root, sub, name))
                if hit:
                    return hit[0]
    raise SystemExit(f"no recording matching '{token}' under {SEARCH}")


def load(path):
    """Tolerant of the NUL runs an unclean shutdown leaves in a CSV."""
    ch, iso, bad = [[], [], []], [], 0
    with open(path, errors='replace') as f:
        for row in csv.DictReader(x.replace('\x00', '') for x in f):
            try:
                v = [float(row[f'ch{i}_mv']) for i in range(3)]
            except (TypeError, ValueError, KeyError):
                bad += 1
                continue
            iso.append(row['datetime'][:16])
            for i in range(3):
                ch[i].append(v[i])
    if bad:
        print(f"  ({bad} malformed rows skipped)")
    return np.array(ch), np.array(iso)


def amplitude(x):
    t = np.arange(len(x))
    x = x - np.polyval(np.polyfit(t, x, 1), t)
    return float(np.percentile(x, 75) - np.percentile(x, 25)) * 1.414


def measure(ch, lo=0, hi=None):
    """Per-channel depth and amplitude over every window, common mode removed."""
    seg = ch[:, lo:hi if hi else ch.shape[1]]
    n = seg.shape[1]
    common = seg.mean(axis=0)
    diff = seg - common
    depths = [[], [], []]
    amps = [[], [], []]
    windows = 0
    for s in range(0, n - WIN, STEP):
        windows += 1
        for i in range(3):
            w = diff[i][s:s + WIN]
            depths[i].append(_period_and_depth(w)[1])
            amps[i].append(amplitude(w))
    cm_share = common.var() / seg.var(axis=1).mean() if n else float('nan')
    return depths, amps, windows, cm_share, n


def report(label, path, quiet=False):
    ch, iso = load(path)
    depths, amps, windows, cm, n = measure(ch)
    if not quiet:
        print(f"\n=== {label} ===")
        print(f"  {os.path.basename(path)}  {n/3600:.1f} h, {windows} windows")
        print(f"  common-mode share of variance: {cm:.2f}"
              f"{'   <-- the chamber, not the organism' if cm > 0.5 else ''}")
        for i in range(3):
            print(f"  ch{i}: depth med {np.median(depths[i]):.3f} "
                  f"p95 {np.percentile(depths[i], 95):.3f} | "
                  f"amplitude med {np.median(amps[i]):.2f} mV")
    return depths, amps


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('recording', nargs='?', help='date, filename or path')
    p.add_argument('--baseline', required=True,
                   help='empty dish, undisturbed, >= 2 h')
    p.add_argument('--percentile', type=float, default=95,
                   help='baseline percentile MIN_DEPTH is set to (default 95)')
    args = p.parse_args()

    base_depths, base_amps = report('BASELINE (empty dish)', resolve(args.baseline))
    pooled = np.concatenate(base_depths)
    threshold = float(np.percentile(pooled, args.percentile))

    print(f"\n--- calibration ---")
    print(f"  {len(pooled)} baseline windows across 3 channels")
    print(f"  p{args.percentile:g} of baseline depth = {threshold:.3f}")
    print(f"  set MIN_DEPTH = {threshold:.2f} in llm/filters/reducer.py")
    print(f"  expected false positive rate at that threshold: "
          f"{100 - args.percentile:.0f}%")

    if not args.recording:
        return 0

    depths, amps = report('RECORDING', resolve(args.recording))
    print(f"\n--- verdict, against MIN_DEPTH {threshold:.2f} ---")
    any_clear = False
    for i in range(3):
        d = np.array(depths[i])
        rate = (d > threshold).mean()
        base_rate = (np.array(base_depths[i]) > threshold).mean()
        amp_ratio = np.median(amps[i]) / max(np.median(base_amps[i]), 1e-9)
        clears = rate > 3 * max(base_rate, 0.02)
        any_clear |= clears
        print(f"  ch{i}: {rate*100:5.1f}% of windows oscillate "
              f"(baseline {base_rate*100:.1f}%) | "
              f"amplitude {amp_ratio:.1f}x baseline"
              f"{'   <-- clears' if clears else ''}")

    print()
    if any_clear:
        print("  At least one channel is doing something the empty dish does not.")
    else:
        print("  Nothing here that the empty dish does not also do. That is not")
        print("  proof of no organism -- it is proof this measurement cannot see")
        print("  one. Check electrode contact before changing the analysis.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
