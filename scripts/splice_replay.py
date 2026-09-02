#!/usr/bin/env python3
"""Join exported replay windows end to end into one file the page can play.

    ./scripts/py scripts/splice_replay.py a.json b.json c.json \
        --out exhibit/replay.json --note '...'

Each input is whatever export_replay.py produced for one window, so the signal
chain has already run on each with its own warmup. Nothing is recomputed here
and no sample is altered; the segments are concatenated in the order given.

Two details that matter:

- Every segment is trimmed to a whole number of minutes. The page reads period
  as `period[floor(i / 60)]`, so a segment whose length is not a multiple of 60
  would slide every later segment's period out of step with its signal.
- `gate_runs` are index ranges, so each segment's runs are shifted by the
  number of samples already written. A gate that is open at a join stays open
  across it rather than re-firing, which would otherwise read as a pin
  connecting a second time.

t0 is the first segment's, so the date the page displays is where the piece
starts. Later segments are not at t0 + their offset in real time.
"""

import argparse
import json

STEP = 60


def load(path):
    d = json.load(open(path))
    n = (d['n'] // STEP) * STEP          # whole minutes only
    return d, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('inputs', nargs='+')
    ap.add_argument('--out', required=True)
    ap.add_argument('--note', default='')
    a = ap.parse_args()

    segs = [load(p) for p in a.inputs]
    first = segs[0][0]
    total = sum(n for _, n in segs)
    nch = len(first['channels'])

    out = {
        't0': first['t0'],
        'dt': 1,
        'n': total,
        'step': STEP,
        'note': a.note or first.get('note', ''),
        'exported': first.get('exported', ''),
        'channels': [{'signal': [], 'gate_runs': [], 'period': []} for _ in range(nch)],
    }

    # Runs shorter than this are window-edge fragments, not events. The chain
    # already discards anything under an hour (MIN_RUN); what survives to here
    # is a run clipped by a segment boundary. Left in, a 36 s fragment reads to
    # the page as a pin connecting -- yellow bloom and all -- for a connection
    # that never happened.
    MIN_RUN = 300

    off = 0
    for d, n in segs:
        for c in range(nch):
            src, dst = d['channels'][c], out['channels'][c]
            dst['signal'].extend(src['signal'][:n])
            dst['period'].extend(src['period'][:n // STEP])
            for r in (src.get('gate_runs') or []):
                s, e = min(r[0], n), min(r[1], n)
                if e > s:
                    dst['gate_runs'].append([s + off, e + off])
        off += n

    # Merge runs that meet exactly at a join, so a gate already open when a
    # segment ends is not reported as opening again, then drop the fragments.
    for c in range(nch):
        ch = out['channels'][c]
        merged = []
        for r in sorted(ch['gate_runs']):
            if merged and r[0] <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], r[1])
            else:
                merged.append(list(r))
        ch['gate_runs'] = [r for r in merged if r[1] - r[0] >= MIN_RUN]

    for c in range(nch):
        ch = out['channels'][c]
        assert len(ch['signal']) == total, 'signal length'
        assert len(ch['period']) == total // STEP, 'period length'

    with open(a.out, 'w') as f:
        json.dump(out, f, separators=(',', ':'))

    print('%s: %d s (%.1f h) from %d segment(s)' % (a.out, total, total / 3600, len(segs)))
    for c in range(nch):
        on = sum(r[1] - r[0] for r in out['channels'][c]['gate_runs'])
        print('  ch%d: gated %5.1f%%' % (c, 100 * on / total))


if __name__ == '__main__':
    main()
