"""Load experiment definitions. See experiments/README.md.

The definition names a prompt variant rather than holding a copy of one, and
names an electrode configuration rather than describing the wiring inline. A
copy is a thing that goes stale while still claiming to be the original, which
is what happened to the prompt copies in harness.py.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ELECTRODES_DIR = os.path.join(HERE, 'electrodes')

DRIVERS = ('loop', 'stimulus', 'none')
MODES = ('test', 'live')


class UnknownExperiment(Exception):
    pass


def names():
    """Every experiment holding a config.json, sorted.

    Calibration tests sit one level down and are named by their path, so
    `calibration/noise-floor` reads as what it is wherever it is logged.
    """
    out = []
    for name in sorted(os.listdir(HERE)):
        if name == 'electrodes' or name.startswith('_') or name.startswith('.'):
            continue
        folder = os.path.join(HERE, name)
        if not os.path.isdir(folder):
            continue
        if os.path.exists(os.path.join(folder, 'config.json')):
            out.append(name)
            continue
        for leaf in sorted(os.listdir(folder)):
            if os.path.exists(os.path.join(folder, leaf, 'config.json')):
                out.append('%s/%s' % (name, leaf))
    return out


def load(name):
    """One experiment's config.json, validated enough to launch from."""
    # A name is a path under experiments/, so it must not climb out of it
    if os.path.isabs(name) or '..' in name.split('/'):
        raise UnknownExperiment("bad experiment name %r" % name)
    path = os.path.join(HERE, *name.split('/'), 'config.json')
    try:
        with open(path, encoding='utf-8') as handle:
            config = json.load(handle)
    except FileNotFoundError:
        raise UnknownExperiment(
            "no experiment %r; have %s" % (name, ', '.join(names()))) from None
    except ValueError as exc:
        raise UnknownExperiment("%s is not valid JSON: %s" % (path, exc)) from None

    if config.get('driver') not in DRIVERS:
        raise UnknownExperiment(
            "%s: driver must be one of %s" % (path, ', '.join(DRIVERS)))
    # The folder name is what a run records, so a config claiming another name
    # would make the run untraceable.
    # Calibration establishes the signal; it is not the experimental record,
    # so it records under test and its readings land in readings/test/.
    # An experiment that uses the signal records live. The driver switches the
    # run to this before it starts, so the mode cannot disagree with what is
    # actually running.
    if config.get('mode') not in MODES:
        raise UnknownExperiment(
            "%s: mode must be one of %s" % (path, ', '.join(MODES)))
    if name.startswith('calibration/') and config['mode'] != 'test':
        raise UnknownExperiment(
            "%s: calibration records under test, not %r" % (path, config['mode']))
    config['name'] = name
    config.setdefault('params', {})
    return config


def electrodes(name):
    """One electrode configuration, or None if the experiment names none."""
    if not name:
        return None
    path = os.path.join(ELECTRODES_DIR, '%s.json' % name)
    try:
        with open(path, encoding='utf-8') as handle:
            return json.load(handle)
    except (OSError, ValueError):
        raise UnknownExperiment("no electrode configuration %r" % name) from None


def enter(app_config, spec):
    """Put the rig into the state `spec` declares, and tag the run.

    Applied by the driver at start rather than left to whoever launched it:
    a run whose mode or panel state disagrees with its own definition is worse
    than one with no definition at all.

    Returns (run, changes) -- changes lists what was moved, for the log.
    """
    import recovery as recovery_state
    import run as run_state

    changes = []

    want_recovery = spec.get('recovery')
    if want_recovery is not None:
        now = recovery_state.state(fresh=True)
        if bool(now.get('active')) != bool(want_recovery):
            recovery_state.set_state(bool(want_recovery), dark_=True,
                                     note='experiment %s' % spec['name'])
            changes.append('recovery %s -> %s'
                           % (now.get('active'), bool(want_recovery)))

    run = run_state.switch(app_config, spec['mode'],
                           note='experiment %s' % spec['name'],
                           experiment=spec['name'],
                           electrodes=spec.get('electrodes'))
    if run.get('mode') != spec['mode'] or run.get('experiment') != spec['name']:
        raise UnknownExperiment(
            "could not switch the run to %s/%s" % (spec['mode'], spec['name']))
    changes.append('run %s %s' % (run['id'], run['mode']))
    return run, changes


def require(name, driver):
    """Load `name` and refuse it if it is not driven by `driver`."""
    config = load(name)
    if config['driver'] != driver:
        raise UnknownExperiment(
            "%s is a %r experiment, not %r" % (name, config['driver'], driver))
    if config.get('electrodes'):
        electrodes(config['electrodes'])   # raises if it is missing
    return config
