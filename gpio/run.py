"""Which run is in progress, and what kind of run it is.

Everything this rig records is continuous. The ADC does not stop for a demo, a
maintenance window, or the twenty minutes the lid is off -- and it should not,
because holes punched in a 1 Hz series are harder to reason about afterwards
than labelled stretches are. So nothing is ever withheld from the record. It is
labelled, and analysis filters on the label.

A run is `{id, mode, started_at, note}`. Modes:

    live    the real run. Nothing has been recorded in this mode yet.
    test    building, bench work, anything that is not the real run. The
            default, because mislabelling development as `live` would put
            bench noise into the scientific record.
    demo    invented data driving the panel, for showing people.

Three is the whole vocabulary. A finer taxonomy would be guessing at
distinctions nobody will maintain -- and a label nobody keeps accurate is worse
than no label, because it is trusted.

Two things follow from a mode that is not `live`:

1. Every row carries `run_id` and `mode`, so a filter can exclude it.
2. Readings are written to a subdirectory. This is the part that matters more
   than the labelling: `ReadingLog.recent()` is what hands the model its window,
   and it reads a directory. Without routing, a demo would feed invented light
   and its consequences back into a real turn as though it came from the
   organism -- and the turn record would look entirely normal.

Switching mode ends one run and starts another, appending the closed run to
`data/runs.jsonl`. That history is the record of when the lid was open, when
the organism was out, and when a demo was given -- which is exactly what you
want a week later when a reading looks strange.
"""

import json
import os
import threading
import time
from datetime import datetime, timezone

MODES = ('live', 'test', 'demo')
DEFAULT_MODE = 'test'

_lock = threading.Lock()


def _state_path(config):
    return os.path.join(config.DATA_DIR, 'run.json')


def _history_path(config):
    return os.path.join(config.DATA_DIR, 'runs.jsonl')


def _new_run(mode, note=''):
    now = time.time()
    stamp = datetime.fromtimestamp(now, timezone.utc)
    return {
        'id': f"{stamp:%Y%m%dT%H%M%SZ}-{mode}",
        'mode': mode,
        'started_at': now,
        'started_at_iso': stamp.isoformat(),
        'note': note,
    }


def current(config):
    """The run in progress. Creates a default experiment run if none exists.

    Read on every append, so a mode change takes effect immediately without
    restarting anything. At 1 Hz the cost of a small JSON read is irrelevant
    next to being able to switch mode from a web page mid-run.
    """
    path = _state_path(config)
    try:
        with open(path, encoding='utf-8') as handle:
            run = json.load(handle)
        if run.get('mode') in MODES and run.get('id'):
            return run
    except (OSError, ValueError):
        pass

    run = _new_run(DEFAULT_MODE, note='auto-created')
    try:
        _write(config, run)
    except OSError:
        pass  # A read-only moment must not stop the recorders.
    return run


def _write(config, run):
    path = _state_path(config)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as handle:
        json.dump(run, handle, indent=2)
    os.replace(tmp, path)


def switch(config, mode, note=''):
    """End the current run and start one in `mode`. Returns the new run."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")

    with _lock:
        previous = current(config)
        if previous['mode'] == mode:
            # Already there. Do not manufacture a run boundary that did not
            # happen -- a spurious boundary is itself misleading history.
            return previous

        previous = dict(previous)
        previous['ended_at'] = time.time()
        previous['ended_at_iso'] = datetime.now(timezone.utc).isoformat()
        try:
            with open(_history_path(config), 'a', encoding='utf-8') as handle:
                handle.write(json.dumps(previous) + '\n')
        except OSError:
            pass

        run = _new_run(mode, note)
        _write(config, run)
        return run


def history(config, limit=50):
    try:
        with open(_history_path(config), encoding='utf-8') as handle:
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


def subdirectory(mode):
    """Where a mode's readings live, relative to the readings directory.

    `live` writes at the top level -- it is the record everything else is a
    deviation from. Every other mode gets its own directory, so the top level
    stays empty until something real is actually running.
    """
    return '' if mode == 'live' else mode
