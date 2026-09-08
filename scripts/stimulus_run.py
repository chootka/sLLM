#!/usr/bin/env python3
"""Step 9: alternate dark and blue blocks on a fixed schedule, and log the edges.

The point of the run is a comparison, so the light has to go off as reliably as
it goes on, and every transition has to be timestamped by the thing that made
it rather than remembered afterwards. Analysis cuts on this log.

    ./scripts/py scripts/stimulus_run.py --dry-run
    ./scripts/py scripts/stimulus_run.py

Blocks alternate starting dark. Six pairs of 60 min is 12 h. All nine zones
are driven.
"""

import argparse
import datetime as dt
import json
import os
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'gpio'))

DATA_DIR = '/var/www/sllm/data'

matrix = None
log_path = None


def recovery_active():
    try:
        with open(os.path.join(DATA_DIR, 'recovery.json')) as handle:
            return bool(json.load(handle).get('active'))
    except (OSError, ValueError):
        return False


def stamp(at):
    return dt.datetime.fromtimestamp(at).astimezone().isoformat()


def record(state, intensity, block, run_id):
    entry = {'t': time.time(), 'iso': stamp(time.time()), 'state': state,
             'intensity': intensity, 'block': block, 'run_id': run_id}
    with open(log_path, 'a') as handle:
        handle.write(json.dumps(entry) + '\n')
    print('%s  block %2d  %-5s  intensity %.2f' % (entry['iso'][11:19], block,
                                                   state, intensity))


def light(zones, intensity):
    for zone in zones:
        matrix.set_zone(zone, intensity)


def dark():
    matrix.clear_stimulus()


def main():
    global matrix, log_path

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--block-min', type=float, default=60.0,
                        help='block length in minutes (default 60)')
    parser.add_argument('--pairs', type=int, default=6,
                        help='dark/light pairs (default 6)')
    # Default matches api/config.py STIMULUS_INTENSITY. The loop no longer
    # varies brightness; this stays settable for a deliberate block protocol.
    parser.add_argument('--intensity', type=float, default=0.5,
                        help='blue level 0.0-1.0 (default 0.5)')
    parser.add_argument('--dry-run', action='store_true',
                        help='print the schedule and exit')
    args = parser.parse_args()

    if not 0.0 <= args.intensity <= 1.0:
        sys.exit('intensity must be 0.0-1.0')

    from matrix_client import open_matrix, ZONES  # noqa: E402

    zones = list(range(ZONES))
    total_min = args.block_min * args.pairs * 2

    try:
        run = json.load(open(os.path.join(DATA_DIR, 'run.json')))
        run_id = run.get('id', 'unknown')
    except (OSError, ValueError):
        run_id = 'unknown'

    print('run          %s' % run_id)
    print('blocks       %d pairs, %.0f min each, dark first' % (args.pairs, args.block_min))
    print('duration     %.1f h, ending about %s' % (
        total_min / 60, stamp(time.time() + total_min * 60)[11:16]))
    print('intensity    %.2f on zones %s' % (args.intensity, zones))

    if args.dry_run:
        at = time.time()
        for pair in range(args.pairs):
            for state in ('dark', 'light'):
                print('  %s  %s' % (stamp(at)[11:16], state))
                at += args.block_min * 60
        return 0

    # set_zone records 0.0 while recovery is active, so the run would spend
    # twelve hours logging a stimulus the dish never received. Read the file
    # rather than importing gpio/recovery: that resolves its path from its own
    # location, so a checkout would answer for the checkout's data directory.
    if recovery_active():
        sys.exit('recovery mode is on and blocks the panel. Turn it off first.')

    matrix, error = open_matrix()
    if matrix is None:
        sys.exit('no matrix: %s' % error)

    log_path = os.path.join(DATA_DIR, 'stimulus_%s.jsonl'
                            % dt.datetime.now().strftime('%Y%m%dT%H%M%S'))
    print('log          %s' % log_path)
    print()

    # Whatever ends the run -- finished, Ctrl-C, systemd stop -- leaves the
    # panel dark and says so in the log.
    def stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)

    block = 0
    try:
        for pair in range(args.pairs):
            for state in ('dark', 'light'):
                block += 1
                if state == 'light':
                    light(zones, args.intensity)
                    record('light', args.intensity, block, run_id)
                else:
                    dark()
                    record('dark', 0.0, block, run_id)
                time.sleep(args.block_min * 60)
    except KeyboardInterrupt:
        print('\nstopped early')
    finally:
        dark()
        record('dark', 0.0, block + 1, run_id)

    return 0


if __name__ == '__main__':
    sys.exit(main())
