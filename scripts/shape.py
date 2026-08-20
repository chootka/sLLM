#!/usr/bin/env python3
"""Look at the shape of a recording before computing anything about it.

Statistics over short windows hide shape. A slope fitted to five hours of an
exponential settle looks like a straight line that will run forever, and a
median depth per window says nothing about whether a channel plateaued. Plot
first.

    ./scripts/py scripts/shape.py                 # today
    ./scripts/py scripts/shape.py 20260820        # a day
    ./scripts/py scripts/shape.py 20260819 20260821
    ./scripts/py scripts/shape.py 20260820 --minutes 10
"""

import argparse
import csv
import datetime
import glob
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SEARCH = ['/var/www/sllm/data/readings',
          os.path.join(os.path.dirname(HERE), 'data', 'readings')]
ROWS = 22
COLS = 74


def files(days):
    out = []
    for day in days:
        hit = []
        for root in SEARCH:
            for sub in ('', 'test'):
                hit += glob.glob(os.path.join(root, sub, f'electrodes_{day}.csv'))
        if not hit:
            print(f"  no recording for {day}")
        out += sorted(set(hit))
    return out


def load(paths):
    t, ch = [], [[], [], []]
    for p in paths:
        with open(p, errors='replace') as f:
            for r in csv.DictReader(x.replace('\x00', '') for x in f):
                try:
                    ts = float(r['timestamp'])
                    v = [float(r[f'ch{i}_mv']) for i in range(3)]
                except (TypeError, ValueError, KeyError):
                    continue
                t.append(ts)
                for i in range(3):
                    ch[i].append(v[i])
    return np.array(t), np.array(ch)


def bucket(t, ch, minutes):
    """Mean per bucket, plus min and max so a spike is not averaged away."""
    width = minutes * 60
    edges = np.arange(t[0], t[-1] + width, width)
    idx = np.digitize(t, edges) - 1
    out = []
    for b in range(len(edges) - 1):
        m = idx == b
        if not m.any():
            continue
        out.append((edges[b], [(ch[i][m].mean(), ch[i][m].min(), ch[i][m].max())
                               for i in range(3)]))
    return out


def plot(buckets, channel, label):
    means = np.array([b[1][channel][0] for b in buckets])
    lows = np.array([b[1][channel][1] for b in buckets])
    highs = np.array([b[1][channel][2] for b in buckets])

    step = max(1, len(means) // COLS)
    means, lows, highs = means[::step], lows[::step], highs[::step]
    times = [b[0] for b in buckets][::step]

    lo, hi = float(lows.min()), float(highs.max())
    span = hi - lo or 1.0

    print(f"\n  {label}   {lo:+.1f} to {hi:+.1f} mV")
    for r in range(ROWS):
        y = hi - span * r / (ROWS - 1)
        line = ''
        for m, l, h in zip(means, lows, highs):
            if abs(m - y) < span / (2 * (ROWS - 1)):
                line += '#'
            elif l <= y <= h:
                line += ':'
            else:
                line += ' '
        print(f"  {y:+8.1f} |{line}")

    ticks = ' ' * 11
    last = ''
    for ts in times:
        stamp = datetime.datetime.fromtimestamp(ts).strftime('%H')
        ticks += stamp[0] if stamp != last and int(stamp) % 3 == 0 else ' '
        last = stamp
    print(ticks)
    first = datetime.datetime.fromtimestamp(times[0])
    print(f"{' ' * 11}{first:%Y-%m-%d %H:%M} to "
          f"{datetime.datetime.fromtimestamp(times[-1]):%m-%d %H:%M}, "
          f"# mean, : min-max")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('days', nargs='*', help='YYYYMMDD, default today')
    p.add_argument('--minutes', type=int, default=15, help='bucket width')
    p.add_argument('--channel', type=int, help='just one channel')
    args = p.parse_args()

    days = args.days or [datetime.date.today().strftime('%Y%m%d')]
    paths = files(days)
    if not paths:
        return 1
    t, ch = load(paths)
    if not len(t):
        print("  no usable rows")
        return 1
    print(f"  {len(t)} samples over {(t[-1]-t[0])/3600:.1f} h "
          f"from {len(paths)} file(s), {args.minutes} min buckets")

    buckets = bucket(t, ch, args.minutes)
    for i in ([args.channel] if args.channel is not None else range(3)):
        plot(buckets, i, f'ch{i}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
