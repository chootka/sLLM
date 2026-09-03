#!/usr/bin/env python3
"""Trim the quiet opening of a spliced replay down to a short lead-in.

The shipped recording opened an hour before the organism first reached an
electrode. At speed 12 that is five minutes of drone before anything happens,
which is a long time to ask of someone standing in front of the object. This
cuts the front so the first connection arrives shortly after the piece starts.

Reads and writes the derived replay file only. The original electrode logs are
never touched.

    python3 scripts/trim_lead_in.py exhibit/replay.json --lead 300
"""
import argparse, json

def main():
    p = argparse.ArgumentParser()
    p.add_argument('path')
    p.add_argument('--lead', type=int, default=300,
                   help='seconds of recording to keep before first contact')
    a = p.parse_args()

    d = json.load(open(a.path))
    step = d['step']

    starts = [r[0] for ch in d['channels'] for r in (ch.get('gate_runs') or [])]
    if not starts:
        raise SystemExit('no gate runs: nothing to trim to')
    first = min(starts)

    # Whole minutes only. The period array holds one value per `step` seconds,
    # so a cut that is not a multiple of it slides period out of alignment with
    # signal and every rhythm the panel reports is then wrong.
    cut = max(0, ((first - a.lead) // step) * step)
    if cut == 0:
        print('first contact at %d s, lead already <= %d s; nothing to do'
              % (first, a.lead))
        return

    for ch in d['channels']:
        ch['signal'] = ch['signal'][cut:]
        ch['period'] = ch['period'][cut // step:]
        runs = []
        for s, e in (ch.get('gate_runs') or []):
            s, e = s - cut, e - cut
            if e > 0:
                runs.append([max(0, s), e])
        ch['gate_runs'] = runs

    n = len(d['channels'][0]['signal'])
    n = (n // step) * step
    for ch in d['channels']:
        ch['signal'] = ch['signal'][:n]
        ch['period'] = ch['period'][:n // step]
        ch['gate_runs'] = [[s, min(e, n)] for s, e in ch['gate_runs'] if s < n]
        assert len(ch['signal']) == n
        assert len(ch['period']) == n // step

    d['t0'] = d['t0'] + cut
    d['n'] = n
    d['note'] = 'run 6 and run 8, opening trimmed to just before the first connection'

    with open(a.path, 'w') as f:
        json.dump(d, f, separators=(',', ':'))

    print('cut %d s (%.1f min); first contact now at %d s (%.1f min of recording, '
          '%.0f s of playback at speed 12); %d s left (%.1f h)'
          % (cut, cut / 60, first - cut, (first - cut) / 60,
             (first - cut) / 12, n, n / 3600))

main()
