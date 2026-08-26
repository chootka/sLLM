"""Whether the organism is in recovery, and how dark the panel is held.

Recovery is a state of the *organism*, not a run mode: the plasmodium is coming
back from sclerotium and should be left alone. While it is set the panel shows
no stimulus and llm/loop.py refuses to run live turns, so nothing is written to
the record against something that was never lit and could not have answered.

## Why this is a file and not a constant

It used to be `RECOVERY = False` in gpio/leds.py, which meant every change was
an edit to a source file on the deployed tree followed by a matrixd restart --
by hand, over SSH, at whatever hour the organism happened to need it. Worse,
the edit lived only in /var/www/sllm, so the checkout and the deployment
disagreed about what the panel was doing.

State in `data/recovery.json` instead, read live. gpio/matrixd.py re-renders
every REFRESH_INTERVAL_S, so a toggle takes effect on the panel within a few
seconds with nothing restarted, and the admin page can own it.

## Shape

    {active, dark, since, since_iso, note}

`dark` takes the barrier out too, leaving the panel entirely unlit. Blue is the
band Physarum avoids most strongly, so holding the barrier lit through
rehydration risks suppressing the emergence it is there to protect -- and it is
safe to drop, because the barrier guards a journey the organism cannot make
yet. Relight it once the plasmodium is actually moving. It is a sub-setting of
`active`, never on its own: a dark panel with the loop still driving it would
be a session logged in the dark.

Closed recovery periods are appended to `data/recovery.jsonl`, for the same
reason runs.jsonl exists -- a week later, when a reading looks strange, the
question is what the organism was being put through at the time.
"""

import json
import os
import threading
import time
from datetime import datetime, timezone

# Derived from this file's own location, so a checkout at ~/sllm and a deploy
# at /var/www/sllm each resolve to their own data directory. leds.py runs under
# the system interpreter as root and cannot import api/config, so the path is
# worked out here rather than passed in the way gpio/run.py takes it.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(PROJECT_ROOT, 'data', 'recovery.json')
HISTORY_PATH = os.path.join(PROJECT_ROOT, 'data', 'recovery.jsonl')

# Held briefly rather than read from disk on every frame. Half a second keeps a
# toggle from the page within one refresh interval, and costs a burst of
# set_zone calls one read rather than nine.
CACHE_S = 0.5

OFF = {'active': False, 'dark': False, 'since': None, 'since_iso': None,
       'note': ''}

_lock = threading.Lock()
_cache = None
_cache_at = 0.0


def _read():
    try:
        with open(STATE_PATH, encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        # No file, unreadable or half-written: not in recovery. Failing the
        # other way is a silently dead installation. The file is written
        # atomically, so a truncated read should not arise.
        return dict(OFF)
    if not isinstance(data, dict):
        return dict(OFF)
    active = bool(data.get('active'))
    return {
        'active': active,
        # dark is meaningless without active, and letting it stand alone would
        # allow a state that reads "not in recovery" while blanking the barrier.
        'dark': active and bool(data.get('dark')),
        'since': data.get('since'),
        'since_iso': data.get('since_iso'),
        'note': data.get('note') or '',
    }


def state(fresh=False):
    """Current recovery state. Cached for CACHE_S unless `fresh`."""
    global _cache, _cache_at

    now = time.monotonic()
    if not fresh and _cache is not None and now - _cache_at < CACHE_S:
        return _cache
    _cache = _read()
    _cache_at = now
    return _cache


def active(fresh=False):
    return state(fresh)['active']


def dark(fresh=False):
    return state(fresh)['dark']


def _write(data):
    global _cache, _cache_at

    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, indent=2)
    try:
        # The API writes this as `sllm` and a shell on the box writes it as a
        # human in the sllm group. Whoever gets there first must not lock the
        # other out of turning recovery back off.
        os.chmod(tmp, 0o664)
    except OSError:
        pass
    os.replace(tmp, STATE_PATH)
    _cache = None
    _cache_at = 0.0


def set_state(active_, dark_=True, note=''):
    """Turn recovery on or off. Returns the new state.

    Idempotent: setting a state that is already current does not restamp
    `since`, so the duration on the page stays the real duration and no
    boundary is written to the history that did not happen. Changing `dark`
    within an active recovery is not a new period either.
    """
    active_ = bool(active_)
    dark_ = bool(dark_) and active_

    with _lock:
        previous = state(fresh=True)
        if previous['active'] == active_:
            if previous['dark'] == dark_:
                return previous
            if not active_:
                return previous
            current = dict(previous, dark=dark_)
            if note:
                current['note'] = note
            _write(current)
            return current

        if not active_:
            closed = dict(previous)
            closed['ended_at'] = time.time()
            closed['ended_at_iso'] = datetime.now(timezone.utc).isoformat()
            if note:
                closed['ended_note'] = note
            try:
                with open(HISTORY_PATH, 'a', encoding='utf-8') as handle:
                    handle.write(json.dumps(closed) + '\n')
            except OSError:
                pass  # History is a record, not an interlock. Never block on it.
            new = dict(OFF)
            _write(new)
            return new

        now = time.time()
        new = {
            'active': True,
            'dark': dark_,
            'since': now,
            'since_iso': datetime.fromtimestamp(now, timezone.utc).isoformat(),
            'note': note or '',
        }
        _write(new)
        return new


def history(limit=20):
    try:
        with open(HISTORY_PATH, encoding='utf-8') as handle:
            lines = handle.readlines()[-limit:]
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


if __name__ == '__main__':
    import sys

    argv = sys.argv[1:]
    if not argv or argv[0] == 'status':
        print(json.dumps(state(fresh=True), indent=2))
    elif argv[0] in ('on', 'dark'):
        print(json.dumps(set_state(True, dark_=True,
                                   note=' '.join(argv[1:])), indent=2))
    elif argv[0] == 'barrier':
        print(json.dumps(set_state(True, dark_=False,
                                   note=' '.join(argv[1:])), indent=2))
    elif argv[0] == 'off':
        print(json.dumps(set_state(False, note=' '.join(argv[1:])), indent=2))
    else:
        print(__doc__)
        print("usage: recovery.py [status|on|barrier|off] [note...]")
        sys.exit(2)
