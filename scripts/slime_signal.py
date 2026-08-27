#!/usr/bin/env python3
"""Slime-attributable drive streams from an electrode run, at 1 Hz.

Emits, per channel per second:
  presence      0-1   organism bridging this electrode (from per-sample noise)
  activity_dex  dex   90-200 s peak above local spectral background
  gate          0/1   presence AND activity
  phase_rad     rad   90-200 s analytic phase   -- only meaningful while gate = 1
  amp_mv        mV    90-200 s analytic envelope -- only meaningful while gate = 1

Method and rationale: documentation/signal_processing.md

Validated 2026-08-27, gate open as a fraction of run:
                        blank (step 7, 11.5 h)   organism (run 6)
  ch0 never colonised            0.7%                  1.0%
  ch1                            0.0%                 95.5%
  ch2                            0.0%                 66.0%

    ./scripts/py scripts/slime_signal.py RUN_ID FILE.csv [FILE.csv ...]
"""
import csv, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from processing.slime import chain, P_THRESH, WIN   # noqa: E402


def load(run, files):
    ts, ch = [], [[], [], []]
    for p in files:
        for r in csv.DictReader(x.replace('\x00', '') for x in open(p, errors='replace')):
            try:
                if r['run_id'] != run:
                    continue
                v = [float(r[f'ch{i}_mv']) for i in range(3)]
                t = float(r['timestamp'])
            except Exception:
                continue
            ts.append(t)
            [ch[i].append(v[i]) for i in range(3)]
    ts = np.array(ts)
    X = np.array(ch)
    g = np.arange(ts[0], ts[-1], 1.0)
    return g, np.array([np.interp(g, ts, X[i]) for i in range(3)])


def main():
    run, files = sys.argv[1], sys.argv[2:]
    g, C = load(run, files)
    print("t_s,channel,presence,activity_dex,gate,phase_rad,amp_mv")
    for i in range(3):
        r = chain(C[i])
        for k in range(len(g)):
            print(f"{k},{i},{r['presence'][k]:.3f},{r['activity'][k]:.3f},"
                  f"{r['gate'][k]},{r['phase'][k]:.4f},{r['envelope'][k]:.4f}")


if __name__ == '__main__':
    main()
