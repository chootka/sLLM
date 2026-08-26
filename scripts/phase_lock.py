#!/usr/bin/env python3
"""Did the stimulus arrive at a preferred phase of the organism's rhythm?

Thin wrapper. The computation lives in llm/filters/phaselock.py so the number
here and the number on the dashboard cannot drift apart.

    ./scripts/py scripts/phase_lock.py data/readings/electrodes_20260826.csv
    ./scripts/py scripts/phase_lock.py <readings.csv> --channel ch0_mv --bins 12
"""

import argparse
import csv
import glob
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]
                       / 'llm' / 'filters'))

from phaselock import analyse  # noqa: E402


def load_switch_onsets(paths):
    """Unix timestamps where the panel actually lit, from the switches log."""
    out = []
    for path in paths:
        with open(path, encoding='utf-8') as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get('event') == 'on' and row.get('timestamp'):
                    out.append(float(row['timestamp']))
    return sorted(out)


def load(path, channel):
    stamps, values = [], []
    with open(path, newline='', encoding='utf-8') as handle:
        for row in csv.DictReader(handle):
            if channel not in row:
                sys.exit(f"no column {channel}; have {', '.join(row)}")
            try:
                stamps.append(float(row['timestamp']))
                values.append(float(row[channel]))
            except (TypeError, ValueError):
                continue
    return stamps, values


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('readings')
    parser.add_argument('--switches', default=None,
                        help='switches_*.jsonl with the applied light events; '
                             'defaults to data/logs next to the readings')
    parser.add_argument('--channel', default='ch0_mv')
    parser.add_argument('--period', type=float, default=None,
                        help='contraction period in seconds; estimated if omitted')
    parser.add_argument('--bins', type=int, default=12)
    parser.add_argument('--shuffles', type=int, default=1000)
    args = parser.parse_args()

    stamps, values = load(args.readings, args.channel)
    pattern = args.switches or str(
        pathlib.Path(args.readings).resolve().parents[2] / 'logs' / 'switches_*.jsonl')
    onsets = load_switch_onsets(sorted(glob.glob(pattern)))
    out = analyse(stamps, values, onsets, period_s=args.period,
                  bins=args.bins, shuffles=args.shuffles)

    if out['verdict'] == 'insufficient':
        sys.exit(out['detail'] or 'not enough to say anything')

    print(f"period {out['period_s']:.0f}s, {len(stamps)} samples")
    print(f"\n{out['n_onsets']} light onsets")
    print(f"vector strength R = {out['R']:.3f}")
    print(f"null R = {out['null_mean']:.3f} +/- {out['null_sd']:.3f}"
          f"   p = {out['p']:.3f}")
    print("clustered" if out['verdict'] == 'clustered'
          else "not distinguishable from arbitrary")

    counts = out['bins']
    width = max(max(counts), 1)
    print()
    for i, count in enumerate(counts):
        lo = out['bin_edges_deg'][i]
        print(f"{lo:+7.0f} deg {'#' * int(40 * count / width)} {count}")


if __name__ == '__main__':
    main()
