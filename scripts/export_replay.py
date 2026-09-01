#!/usr/bin/env python3
"""Freeze a recorded window into a file the page can play with no API.

The exhibition object has no rig behind it, so the signal chain runs once here
and the result ships as data. Output matches what /api/readings/processed
would have produced at 1 Hz, in a columnar form small enough to keep in git.

    ./scripts/py scripts/export_replay.py \
        --start '2026-08-27 23:08:34' --end '2026-08-29 00:00:00' \
        --out exhibit/replay.json

Times are local. The chain needs WARMUP seconds of record before --start; the
export fails rather than shipping a false gate at the left edge.
"""

import argparse
import csv
import glob
import json
import os
import sys
from datetime import datetime

import numpy as np

HERE = os.path.dirname(os.path.abspath(HERE_FILE := __file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from processing.slime import chain, step_for, WARMUP  # noqa: E402

SEARCH = ['/var/www/sllm/data/readings', os.path.join(ROOT, 'data', 'readings')]
CHANNELS = (0, 1, 2)


def load(t0, t1):
    """Every row in [t0, t1], from whichever tree has the readings."""
    rows = []
    for root in SEARCH:
        for sub in ('', 'test'):
            for path in sorted(glob.glob(os.path.join(root, sub, 'electrodes_*.csv'))):
                with open(path, errors='replace') as f:
                    for r in csv.DictReader(x.replace('\x00', '') for x in f):
                        try:
                            t = float(r['timestamp'])
                            if not t0 <= t <= t1:
                                continue
                            v = [float(r[f'ch{c}_mv']) for c in CHANNELS]
                        except (KeyError, TypeError, ValueError):
                            continue
                        rows.append((t, v))
        if rows:
            break
    rows.sort(key=lambda r: r[0])
    return np.array([r[0] for r in rows]), np.array([r[1] for r in rows])


def runs(gate):
    """Gate as [start, end) index pairs. It is binary and mostly flat."""
    out, on = [], None
    for i, g in enumerate(gate):
        if g and on is None:
            on = i
        elif not g and on is not None:
            out.append([on, i]); on = None
    if on is not None:
        out.append([on, len(gate)])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--start', required=True)
    ap.add_argument('--end', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--note', default='')
    a = ap.parse_args()

    start = datetime.fromisoformat(a.start).timestamp()
    end = datetime.fromisoformat(a.end).timestamp()
    if end <= start:
        raise SystemExit('end must be after start')

    stamps, values = load(start - WARMUP, end)
    if len(stamps) < 2:
        raise SystemExit('no readings in that window')
    if stamps[0] > start - WARMUP + 60:
        raise SystemExit(
            f'need {WARMUP} s of record before --start; earliest row is '
            f'{datetime.fromtimestamp(stamps[0])}')

    grid = np.arange(stamps[0], stamps[-1], 1.0)
    step = step_for(end - start, 2000)
    keep = (grid >= start) & (grid <= end)
    n = int(keep.sum())

    channels = []
    for i, c in enumerate(CHANNELS):
        r = chain(np.interp(grid, stamps, values[:, i]), step=step)
        gate = (r['gate'][keep] > 0.5).astype(int)
        sig = np.round(r['signal'][keep], 3)
        per = np.round(r['period'][keep][::60], 1)
        channels.append({
            'signal': [float(x) for x in sig],
            'gate_runs': runs(gate),
            'period': [float(x) for x in per],   # one per minute
        })
        print(f'  ch{c}: gated {gate.mean() * 100:5.1f}%  '
              f'signal {sig.min():+.3f}..{sig.max():+.3f} mV')

    payload = {
        't0': float(grid[keep][0]),
        'dt': 1,
        'n': n,
        'step': step,
        'note': a.note,
        'exported': datetime.now().isoformat(timespec='seconds'),
        'channels': channels,
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, 'w') as f:
        json.dump(payload, f, separators=(',', ':'))
    print(f'{a.out}: {n} s ({n / 3600:.1f} h), '
          f'{os.path.getsize(a.out) / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
