"""The live loop: real electrodes -> reducer -> model -> the matrix.

Same shape as llm/filters/harness.py, which is the replay version of this
against synthetic data. The reduction layer and the prompts are imported from
there rather than reimplemented -- if the two ever disagree, the replay
harness stops being evidence about what the live loop does.

What is different from the harness:

  * the window comes off disk, from the CSV that gpio/adc.py writes, so the
    loop survives a restart and picks up mid-run instead of waiting 30 minutes
  * the action is applied to real hardware, or deliberately withheld
  * every turn is appended to a JSONL log whether or not anything happened

Turn timing. Turns fire when the reducer reports a change above threshold, not
on a clock (--trigger state, the default). The model also names its own next
delay. Two systems entrain each other without either knowing anything about the
other -- the earth and the moon do it -- but only if each one's timing depends
on the other's. On a fixed tick the rhythm was ours and this was a driver with a
model attached. See documentation/method_basis.md.

Sham blocks. Some fraction of turns are run with the action logged and not
applied. The model is never told which turn it is in -- that is the whole
point, and it is why `applied` lives in the log and never in the prompt. A
sham block is not an error path; it is the control.

    ./scripts/py llm/loop.py --check      # connectivity and window, no turns
    ./scripts/py llm/loop.py --dry-run    # full loop, never drives the matrix
    ./scripts/py llm/loop.py              # live (matrixd owns the panel, no sudo)

Testing without waiting on an organism. --replay slides the same loop along a
fixed session and --speed compresses the clock, so a 24-turn run that would
take four hours live takes under a minute. Replay always implies --dry-run.

    ./scripts/py llm/loop.py --replay synthetic --speed 600 --turns 24
    ./scripts/py llm/loop.py --replay data/readings/electrodes_20260805.csv --speed 600

Replay never drives the panel: putting real light on the organism from a
recording that is not about it would be a stimulus nothing recorded as one.
Its turns are written to data/logs/replay/ so they can never be confused with
a real session.

Synthetic sessions carry a planted event at a known turn and log it alongside
the model's note, so a claim can be checked against whether anything happened.
A recording cannot do that -- you do not know what was in it -- but it is the
only way to see how the loop behaves on real noise. Use both.
"""

import argparse
import json
import os
import pathlib
import random
import signal
import sys
import threading
import time
from datetime import datetime, timezone

import requests

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'api'))
sys.path.insert(0, str(ROOT / 'gpio'))
sys.path.insert(0, str(HERE / 'filters'))
sys.path.insert(0, str(ROOT))

import syspath  # noqa: E402,F401  (path setup, must precede hardware imports)
import experiments  # noqa: E402

import config  # noqa: E402
from reducer import NO_CHANGE, reduce_window, for_model  # noqa: E402
from trail import Trail  # noqa: E402
from store import channels_from_rows, electrode_log  # noqa: E402

# Recovery state only, never the panel -- a live run drives it through matrixd.
# Pure stdlib on purpose: importing leds.py here would put the refusal below
# behind the CircuitPython stack, where an ImportError silently disables it.
import recovery as recovery_state  # noqa: E402

# Which run a turn belongs to, so turn records carry the same run_id and mode
# that store.py stamps on every reading. Stdlib only, same reasoning as above.
import run as run_state  # noqa: E402

from prompts import load_prompts  # noqa: E402
import prediction  # noqa: E402


class LiveSource:
    """Windows off the CSV that gpio/adc.py is writing right now."""

    label = "live"

    def __init__(self, config, window_s, channels):
        self.log = electrode_log(config)
        self.window_s = window_s
        self.channels = channels
        # Set on every window() so a turn record can name the readings it was
        # computed from. Without it a state is not traceable back to rows.
        self.last_bounds = None

    def describe(self):
        rows = self.log.recent(self.window_s)
        span = (float(rows[-1]['timestamp']) - float(rows[0]['timestamp'])
                if rows else 0.0)
        return f"{len(rows)} samples spanning {span / 60:.1f} min"

    def window(self, turn):
        rows = self.log.recent(self.window_s)
        self.last_bounds = ({"start": float(rows[0]['timestamp']),
                             "end": float(rows[-1]['timestamp'])}
                            if rows else None)
        return channels_from_rows(rows, self.channels)


class ReplaySource:
    """Windows slid along a fixed session, so a run can be tested in minutes.

    The point is to exercise this file -- the reduction, the validation, the
    sham draw, the logging -- without waiting on an organism that reconfigures
    over hours. Two sources:

      synthetic   generated by llm/filters/harness.py, with a planted event at
                  a known time, so anything else the model reports is its own
                  invention
      a CSV path  a previously recorded run out of data/readings

    Real recordings cannot tell you whether the model confabulated, because
    you do not know what was in them. Synthetic can. Use both.
    """

    def __init__(self, spec, window_s, interval_s, channels, sample_hz=1):
        self.window_s = window_s
        self.interval_s = interval_s
        self.channels = channels
        self.sample_hz = sample_hz

        if spec == 'synthetic':
            from harness import session

            # One planted event: the period lengthens 90s -> 140s across turns
            # 10 to 14. Nothing happens anywhere else in the session.
            start = window_s + 10 * interval_s
            self.events = [(start, start + 4 * interval_s, 'period_s', 140.0)]
            duration = window_s + 40 * interval_s
            raw = session(duration_s=duration, events=self.events,
                          n_channels=len(channels))
            self.series = {f'ch{c}': raw[f'ch{i}']
                           for i, c in enumerate(channels)}
            self.label = f"synthetic, event planted at turn 10-14"
        else:
            import csv as _csv

            path = pathlib.Path(spec)
            if not path.exists():
                raise FileNotFoundError(f"no such recording: {spec}")
            with open(path, newline='', encoding='utf-8') as handle:
                rows = list(_csv.DictReader(handle))
            self.series = channels_from_rows(rows, channels)
            self.events = []
            self.label = f"{path.name}, {len(rows)} samples"

        self.length = min((len(v) for v in self.series.values()), default=0)

    def describe(self):
        total = self.length / self.sample_hz
        turns = max(0, int((total - self.window_s) // self.interval_s))
        return f"{self.label}; {total / 60:.0f} min = {turns} turns"

    def window(self, turn):
        """The window ending `turn` intervals after the first full window."""
        end = int((self.window_s + turn * self.interval_s) * self.sample_hz)
        start = max(0, end - int(self.window_s * self.sample_hz))
        if end > self.length:
            return None
        return {name: values[start:end] for name, values in self.series.items()}

    def planted_at(self, turn):
        """Whether a planted event is active at this turn, for the log."""
        moment = self.window_s + turn * self.interval_s
        return [e for e in self.events
                if e[0] <= moment <= e[1] + self.interval_s]


class Ollama:
    """Chat client for the model running on the laptop."""

    def __init__(self, host, model, timeout=300, num_ctx=None, top_logprobs=3):
        self.url = host.rstrip('/') + '/api/chat'
        self.model = model
        self.timeout = timeout
        # None leaves it to the model's Modelfile.
        self.num_ctx = num_ctx
        # Per-token probabilities. The one measure of the model's uncertainty
        # that does not depend on what it says about itself -- fluent text over
        # a wide distribution is exactly the case a note cannot report. Free to
        # ask for at request time and unrecoverable afterwards, so it is always
        # on. 0 disables it.
        self.top_logprobs = top_logprobs

    def reachable(self):
        """(ok, detail). Checks the server answers and has the model."""
        tags = self.url.replace('/api/chat', '/api/tags')
        try:
            response = requests.get(tags, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            return False, str(exc)

        names = [m.get('name', '') for m in response.json().get('models', [])]
        if not any(n == self.model or n.startswith(self.model + ':')
                   for n in names):
            return False, (f"{self.model} not pulled; available: "
                           f"{', '.join(names) or 'none'}")
        return True, f"{self.model} available"

    def ask(self, system, state, history, retries=2):
        """(reply, usage, logprobs).

        usage is Ollama's own token counts; logprobs is its per-token list for
        the reply that parsed, or None if the server did not return any.
        """
        messages = [{"role": "system", "content": system}]
        messages += history
        messages.append({"role": "user", "content": json.dumps(state)})

        last_error = None
        for attempt in range(retries + 1):
            # A retry at a lower temperature is a genuine second try rather
            # than the same dice roll again.
            options = {"temperature": 0.8 if attempt == 0 else 0.3}
            if self.num_ctx:
                options["num_ctx"] = self.num_ctx

            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                # Constrains sampling to valid JSON. Without it the model
                # occasionally emits a literal newline inside a string and
                # the parse fails, which loses the turn.
                "format": "json",
                "options": options,
            }
            if self.top_logprobs:
                payload["logprobs"] = True
                payload["top_logprobs"] = self.top_logprobs

            response = requests.post(self.url, json=payload,
                                     timeout=self.timeout)
            response.raise_for_status()

            body = response.json()
            usage = {
                "prompt_tokens": body.get("prompt_eval_count"),
                "reply_tokens": body.get("eval_count"),
            }
            # Absent on servers older than the logprobs support; a missing key
            # is not an error, it just means that run has no entropy channel.
            logprobs = body.get("logprobs")
            text = body["message"]["content"]
            cleaned = text.replace("```json", "").replace("```", "").strip()
            try:
                return json.loads(cleaned), usage, logprobs
            except json.JSONDecodeError as exc:
                last_error = exc
                try:
                    return json.loads(cleaned, strict=False), usage, logprobs
                except json.JSONDecodeError:
                    pass

        raise ValueError(f"unparseable after {retries + 1} attempts: "
                         f"{last_error}\nraw: {cleaned[:400]}")


class TurnLog:
    """Append-only JSONL of every turn, sham or not.

    Replay and dry runs write to a `replay/` subdirectory rather than
    alongside the real record. Synthetic turns look exactly like live ones
    once they are in a file -- same shape, same fields, plausible numbers --
    and anything later reading data/logs to ask what the organism did must not
    have to guess which rows were about an organism at all.
    """

    def __init__(self, directory, replay=False, prefix='turns'):
        if replay:
            directory = os.path.join(directory, 'replay')
        os.makedirs(directory, exist_ok=True)
        self.directory = directory
        self.prefix = prefix

    def append(self, record):
        day = datetime.now(timezone.utc).strftime('%Y%m%d')
        path = os.path.join(self.directory, f'{self.prefix}_{day}.jsonl')
        with open(path, 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(record) + '\n')
        return path


def wait_for_turn(source, turn, previous, window_s, args, requested_s):
    """Block until the next turn should run. Returns what triggered it.

    Two systems only count as coupled if each one's timing depends on the
    other. On a fixed tick the forcing is periodic no matter what the organism
    does, which makes this a driver with a model attached rather than a loop:
    the model picks the zone, but the rhythm is mine. So in state mode the
    organism sets the tempo. The window is re-reduced every `poll` seconds
    against the state as it stood at the last turn, and the turn fires as soon
    as the reducer reports something above threshold. A quiet organism means no
    turns for hours, which is the correct behaviour and not a stall.

    The model's own `next_turn_s` is the second trigger, so both sides have a
    say. `min_gap` is a floor, because a noisy patch would otherwise fire turns
    back to back and swamp the record.

    Replay always uses the clock. A replay window is indexed by turn number, so
    polling without advancing `turn` returns identical data forever and nothing
    would ever cross threshold.
    """
    if args.trigger == 'clock' or args.replay:
        time.sleep(max(0.0, args.interval / args.speed))
        return 'clock'

    speed = max(args.speed, 1e-9)
    floor = args.min_gap / speed
    ceiling = (requested_s if requested_s else args.max_gap or 0) / speed
    waited = 0.0

    while True:
        time.sleep(args.poll / speed)
        waited += args.poll / speed

        if waited < floor:
            continue
        if ceiling and waited >= ceiling:
            return 'requested' if requested_s else 'ceiling'

        series = source.window(turn)
        if series is None:
            return 'exhausted'
        if min((len(v) for v in series.values()), default=0) < window_s * 0.5:
            continue

        # `previous` is deliberately not updated here. Change is always
        # measured against the last turn, not the last poll, or a slow trend
        # would be invisible one poll at a time.
        state = reduce_window(series, previous)
        if state.get('changes_since_last_turn', [NO_CHANGE]) != [NO_CHANGE]:
            return 'state'


# Reference period for metered budgets. The established line on this rig runs
# 106-164 s; 130 s sits in the middle and is the point where metering returns
# the configured defaults unchanged.
METER_REFERENCE_S = 130.0
METER_MIN = 0.25
METER_MAX = 4.0


def metered_budget(period_s, base_ctx, base_history):
    """Scale the model's context and memory by the organism's current period.

    A faster organism buys a bigger budget, a slower one shrinks it. Blue light
    is assumed to lengthen the period, so every pulse the model orders costs it
    capacity -- it can only think at full width by leaving the organism alone.
    The model is not told this; it has to read it off the telemetry history.

    That blue light shifts the period at all is sourced; which way it shifts is
    not. See documentation/metered_loop.md, Direction. The inverse mapping was
    built first and is the one to restore if the sign turns out backwards.

    Clamped either side so a bad period estimate cannot ask Ollama for a
    context it cannot allocate or starve the model to nothing.

    Returns (num_ctx, history_turns), either unchanged if there is no period or
    no configured base to scale.
    """
    if not period_s:
        return base_ctx, base_history
    scale = min(METER_MAX, max(METER_MIN, METER_REFERENCE_S / period_s))
    ctx = int(base_ctx * scale) if base_ctx else base_ctx
    # 0 means uncapped and -1 means none; neither is a quantity to scale.
    history = (max(1, int(round(base_history * scale)))
               if base_history and base_history > 0 else base_history)
    return ctx, history


def measured_period(state):
    """Median contraction period across channels that reported one, or None.

    One number for the organism's current tempo, used to express a stimulus in
    its own time base rather than in seconds off the wall clock.
    """
    periods = [ch.get('period_s') for name, ch in state.items()
               if isinstance(ch, dict) and ch.get('period_s')]
    if not periods:
        return None
    periods = sorted(periods)
    middle = len(periods) // 2
    if len(periods) % 2:
        return float(periods[middle])
    return (periods[middle - 1] + periods[middle]) / 2.0


def cycle_error(gap_s, believed_period_s, measured_period_s):
    """How far the model's estimate of the tempo put it out over one gap.

    A period that is wrong by a little slips by a lot once a gap is several
    cycles long, which is what makes this worth telling the model rather than
    the period itself. Returns None where either period is missing.
    """
    if not gap_s or not believed_period_s or not measured_period_s:
        return None
    expected = gap_s / believed_period_s
    actual = gap_s / measured_period_s
    return {
        "gap_s": round(gap_s, 1),
        "cycles_expected": round(expected, 2),
        "cycles_actual": round(actual, 2),
        "error_cycles": round(actual - expected, 2),
    }


def believed_period(reply):
    """The model's own estimate of the rhythm, or None if it gave none."""
    value = reply.get('believed_period_s')
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    # A period outside this cannot be a contraction cycle and would make a
    # duration in cycles either instant or hours long.
    return value if 10.0 <= value <= 1800.0 else None


def validate_action(reply, zones, max_duration, intensity, period_s=None,
                    whole_dish=False):
    """Pull a usable light action out of the reply, or None.

    The model is asked for JSON but is not constrained to sensible values, so
    everything is bounded here rather than trusted. A refused action is still
    logged -- what the model asked for is data even when it is unusable.

    Duration is asked for in cycles of the organism's own contraction period,
    not in seconds. Three cycles is 270s at a 90s period and 420s at 140s, so
    the stimulus stays scaled to the organism as its tempo drifts rather than
    being fixed against a clock that has nothing to do with it. duration_s is
    still accepted, for replaying older sessions and for the case where no
    period was measured.

    Intensity is NOT taken from the reply. Every stimulus goes out at
    STIMULUS_INTENSITY. Dose used to be intensity x seconds, which assumes
    reciprocity -- that a dim long pulse and a bright short one do the same
    thing to the organism. Nothing establishes that for Physarum. Holding
    intensity makes dose seconds, and leaves the model one quantity to reason
    about instead of two.

    `whole_dish` drops the zone: the action lights every zone, and the reply is
    not expected to name one. Used by METERED, where the metered quantity is a
    median across all three electrodes and a single zone cannot move it.
    """
    light = reply.get('light')
    if not isinstance(light, dict):
        return None, "no light action"

    try:
        zone = None if whole_dish else int(light['zone'])
        if light.get('duration_cycles') is not None:
            cycles = float(light['duration_cycles'])
            if not period_s:
                return None, "duration in cycles but no period measured"
            duration = cycles * period_s
        else:
            duration = float(light.get('duration_s', 60))
    except (KeyError, TypeError, ValueError) as exc:
        return None, f"malformed light action: {exc}"

    if zone is not None and not 0 <= zone < zones:
        return None, f"zone {zone} outside 0..{zones - 1}"

    action = {
        "zone": zone,
        "intensity": intensity,
        "duration_s": min(max(duration, 0.0), max_duration),
    }
    if light.get('duration_cycles') is not None:
        # Kept so the log says what was asked for as well as what it became.
        action["duration_cycles"] = float(light['duration_cycles'])
        action["period_s_at_request"] = period_s
    return action, None


class DoseLedger:
    """Rolling cap on how much light the model can put on the organism.

    Dose is SECONDS of light, summed over the last hour. It was intensity x
    seconds until 2026-09-08; intensity is now fixed at STIMULUS_INTENSITY, so
    the product carried no information and implied a reciprocity assumption
    nothing establishes for this organism.

    Nothing else in the rig bounds cumulative exposure: MAX_STIMULUS_DURATION
    caps one stimulus, so a model that asks for the maximum every turn is
    inside every existing limit and still floods the dish.

    The cap trims the duration rather than refusing the action, and both the
    asked-for and the allowed value are logged. A refusal would leave the trace
    reasoning about a stimulus that never happened; a trim leaves a record of
    the difference.

    Spent only when a stimulus is actually applied. A sham turn lights nothing
    and costs nothing.
    """

    WINDOW_S = 3600.0

    def __init__(self, budget):
        self.budget = float(budget)
        self.entries = []

    def _prune(self, now):
        cutoff = now - self.WINDOW_S
        self.entries = [(t, d) for t, d in self.entries if t > cutoff]

    def spent(self, now=None):
        now = time.time() if now is None else now
        self._prune(now)
        return sum(d for _, d in self.entries)

    def remaining(self, now=None):
        return max(0.0, self.budget - self.spent(now))

    def allowed_duration(self, duration_s, now=None):
        """The most of this request the hour's budget will carry, in seconds."""
        if duration_s <= 0:
            return duration_s
        return min(duration_s, self.remaining(now))

    def spend(self, duration_s, now=None):
        now = time.time() if now is None else now
        dose = max(0.0, duration_s)
        if dose > 0:
            self.entries.append((now, dose))
        return dose


def apply_dose_cap(action, ledger):
    """Trim an action to the hour's remaining dose. Returns a record, or None.

    Mutates the action's duration in place, which is what then gets applied and
    logged, so the turn log says what reached the organism rather than what was
    asked for.
    """
    if not action or ledger is None:
        return None
    asked = action["duration_s"]
    allowed = ledger.allowed_duration(asked)
    if allowed >= asked:
        return None
    action["duration_s"] = allowed
    return {
        "duration_asked_s": round(asked, 1),
        "duration_allowed_s": round(allowed, 1),
        "remaining_dose": round(ledger.remaining(), 1),
        "budget": ledger.budget,
    }


def open_matrix(dry_run):
    """The panel, preferring the root-owned daemon.

    With matrixd running this works unprivileged, so a live run no longer needs
    sudo. Without it, the direct fallback still opens the panel in-process,
    which needs both root and the system interpreter.
    """
    if dry_run:
        return None, "dry run"
    try:
        from matrix_client import open_matrix as _open

        return _open()
    except Exception as exc:
        return None, str(exc)


_stimulus_timer = None


def apply_action(matrix, action, speed=1.0, min_duration=0.0, on_switch=None,
                 zones=9):
    """Light the zone, and take it off again after the duration requested.

    `speed` compresses the duration alongside the turn interval, so a fast run
    keeps the same on/off rhythm as a live one instead of holding every zone
    lit straight through to the next turn.

    The duration used to be parsed, validated, logged -- and never applied. The
    zone was set and simply left until the next turn overwrote it, so a model
    asking for a 30 second pulse got a 600 second one, twenty times longer.

    That is worse than a cosmetic bug. The model reasons about each new window
    on the belief that it applied a brief stimulus, and those inferences are the
    experimental record. Every causal claim it made rested on a false premise
    about its own action.
    """
    global _stimulus_timer

    def _switch(event):
        """Record that light actually started or stopped, if anyone is listening.

        Never lets a logging failure reach the caller: this runs on the timer
        thread as well as the turn thread, and a broken log must not take the
        stimulus with it.
        """
        if on_switch is None:
            return
        try:
            on_switch(event, action)
        except Exception as exc:  # noqa: BLE001 -- a record is not worth the run
            print(f"could not record {event} switch: {exc}")

    if _stimulus_timer is not None:
        _stimulus_timer.cancel()
        _stimulus_timer = None

    intensity = action["intensity"]

    # Worked out before the zone is lit: a zero-length request must not light it
    # at all. Computing this after set_zone left the zone on with nothing armed
    # to clear it, so zero seconds lasted until the next turn.
    #
    # Scaling duration with the interval keeps the on/off ratio honest.
    duration = (action.get("duration_s") or 0) / max(speed, 1e-9)
    if duration > 0:
        duration = max(duration, min_duration)

    # Clear rather than light-then-clear: the zone is already dark, and a
    # set/clear pair spends a switching edge saying so.
    if duration <= 0:
        matrix.clear_stimulus()
        return

    matrix.clear_stimulus()
    if action["zone"] is None:
        # Whole dish. One set_zone per zone rather than a new panel command,
        # so matrixd's protocol and the direct Matrix stay one implementation.
        for z in range(zones):
            matrix.set_zone(z, intensity)
    else:
        matrix.set_zone(action["zone"], intensity)
    _switch('on')

    def _expire():
        try:
            matrix.clear_stimulus()
        except Exception as exc:  # noqa: BLE001 -- a timer thread must not die
            print(f"could not clear stimulus after {duration}s: {exc}")
        else:
            # Only on success. A failed clear means the zone is still lit, and
            # a row claiming it went dark would be worse than no row at all.
            _switch('off')

    _stimulus_timer = threading.Timer(duration, _expire)
    _stimulus_timer.daemon = True
    _stimulus_timer.start()


def cancel_stimulus_timer():
    global _stimulus_timer
    if _stimulus_timer is not None:
        _stimulus_timer.cancel()
        _stimulus_timer = None


def install_signal_handlers():
    """Make SIGTERM unwind the stack instead of killing the process outright.

    systemd stops a service with SIGTERM, and Python's default action for it
    terminates immediately without running `finally` blocks. That matters here:
    the `finally` at the end of main() is what clears the stimulus. Without
    this, `systemctl stop sllm-loop` would leave whichever zone the model last
    chose lit indefinitely, with nothing left running that knows to turn it off.
    """
    def _interrupt(_sig, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _interrupt)


def main():
    install_signal_handlers()
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true',
                        help='verify Ollama and the data window, run no turns')
    parser.add_argument('--dry-run', action='store_true',
                        help='run turns but never drive the matrix')
    parser.add_argument('--experiment', metavar='NAME',
                        help='an experiments/<name>/ folder. Supplies the '
                             'prompt and parameters, and tags the run with '
                             'the dish it assumes. Explicit flags win.')
    parser.add_argument('--prompt', default=None)
    parser.add_argument('--turns', type=int, default=0, help='0 runs forever')
    parser.add_argument('--interval', type=int,
                        default=getattr(config, 'LLM_TURN_INTERVAL', 600))
    parser.add_argument('--window', type=int,
                        default=getattr(config, 'LLM_WINDOW_S', 1800),
                        help='seconds of readings each turn summarises')
    parser.add_argument('--host', default=getattr(config, 'OLLAMA_HOST', ''))
    parser.add_argument('--model', default=getattr(config, 'OLLAMA_MODEL', ''))
    parser.add_argument('--replay', metavar='SOURCE',
                        help="'synthetic', or a path to a recorded "
                             "data/readings/electrodes_*.csv")
    parser.add_argument('--speed', type=float, default=1.0,
                        help='time compression in replay, e.g. 600 runs a '
                             '10 min turn interval in 1 s')
    parser.add_argument('--trigger', choices=('state', 'clock'), default='state',
                        help="what decides when a turn happens. 'state' waits "
                             "for the reducer to report a change above "
                             "threshold, so the organism sets the tempo; "
                             "'clock' uses --interval. Replay forces clock.")
    parser.add_argument('--poll', type=int, default=60,
                        help='seconds between checks of the window while '
                             'waiting for a state change')
    parser.add_argument('--min-gap', type=int,
                        default=getattr(config, 'LLM_MIN_TURN_GAP', 300),
                        help='floor on seconds between turns, so a noisy '
                             'patch cannot fire them back to back')
    parser.add_argument('--max-gap', type=int,
                        default=getattr(config, 'LLM_MAX_TURN_GAP', 0),
                        help='ceiling on seconds between turns; 0 means a '
                             'quiet organism produces no turns at all, which '
                             'is the intended behaviour')
    parser.add_argument('--metered', action='store_true',
                        help="scale context and history by the organism's "
                             'measured period rather than holding them fixed')
    parser.add_argument('--sham-rate', type=float, default=None)
    parser.add_argument('--num-ctx', type=int, default=None,
                        help='context window in tokens; pins the denominator '
                             'the adversarial prompt reports to the model')
    args = parser.parse_args()

    # An experiment supplies defaults; anything given on the command line wins,
    # and the override is logged so the record cannot claim the config drove a
    # run that it did not.
    experiment = None
    electrode_config = None
    overrides = {}

    # With no --experiment, fall back to whatever the current run says it is.
    # The admin page's experiment selector writes that field, so choosing an
    # experiment there and starting sllm-loop runs it -- without this the unit
    # would have to name one on its command line and the two could disagree.
    # run_state is imported at module level. Importing it again here would
    # make the name local to main() and leave it unbound on every path that
    # skips this branch -- which is what --experiment does.
    if not args.experiment:
        try:
            args.experiment = run_state.current(config).get('experiment') or ''
        except Exception:
            args.experiment = ''

    if args.experiment:
        try:
            experiment = experiments.require(args.experiment, 'loop')
            electrode_config = experiment.get('electrodes')
        except experiments.UnknownExperiment as exc:
            print(exc)
            return 2
        params = experiment.get('params', {})
        for flag, key in (('prompt', 'prompt'), ('model', 'model'),
                          ('min_gap', 'min_gap_s'), ('sham_rate', 'sham_rate'),
                          ('interval', 'interval_s'), ('num_ctx', 'num_ctx'),
                          ('window', 'window_s'), ('metered', 'metered')):
            value = experiment.get(key) if key == 'prompt' else params.get(key)
            if value is None:
                continue
            given = getattr(args, flag)
            if given in (None, parser.get_default(flag)):
                setattr(args, flag, value)
            elif given != value:
                overrides[flag] = {"config": value, "used": given}

    if args.prompt is None:
        args.prompt = getattr(config, 'LLM_PROMPT', 'blind')

    # Only for a run that actually records and actuates. --check, --dry-run and
    # --replay must not switch the run or move recovery: they are inspections.
    actuating = not (args.check or args.dry_run or args.replay)
    if experiment and actuating:
        try:
            _, changes = experiments.enter(config, experiment)
        except Exception as exc:
            print(f"could not enter {experiment['name']}: {exc}")
            return 2
        for line in changes:
            print(f"   {line}")

    # In recovery the panel is dark, so a live turn would be logged as real
    # against something that was never lit. A gap is visibly a gap; a fake turn
    # is not. Refuse.
    #
    # Exit 0, not an error: sllm-loop.service is Restart=on-failure, so a clean
    # exit stops it rather than retrying for as long as recovery lasts.
    #
    # --dry-run, --check and --replay stay allowed; none actuate.
    if recovery_state.active(fresh=True) and not (
            args.dry_run or args.check or args.replay):
        print('recovery mode is on: the panel is dark and the organism is '
              'coming back from sclerotium. Refusing to run live turns. Turn '
              'recovery off from the admin page (or `python3 '
              'gpio/recovery.py off`) and start sllm-loop to resume.',
              file=sys.stderr)
        return 0

    # From the experiment when it names one, else --window, else config. An
    # experiment that declares a window has to get the one it declares: the
    # window is what the model's whole view of the organism is built from, and
    # a config.py edit must not quietly reinterpret every past run at once.
    window_s = args.window
    history_turns = getattr(config, 'LLM_HISTORY_TURNS', 8)

    # Each variant that changes the loop, not only the wording, is wired here.
    # Adversarial needs all three of pinned window, no truncation and compact
    # state; mimic needs all four of no history, trail, changes-only and no
    # note. Any one missing and the prompt describes something that is not
    # happening.
    adversarial = args.prompt == 'adversarial'
    mimic = args.prompt == 'mimic'
    # CYCLES withholds the measured period and scores the model's own estimate
    # of it. Everything the model expresses in cycles is converted with its
    # estimate rather than with the measurement.
    cycles_mode = args.prompt == 'cycles'

    # METERED lights the whole dish, not a zone. The budget it meters is the
    # median period across the three electrodes, and a median is the statistic
    # that discards the odd one out -- so a single lit zone, reaching at most
    # one electrode, barely moves the number it is supposed to move. Lighting
    # everything also removes the escape route: photoavoidance is a movement
    # response, and with the whole dish lit a response has to appear
    # physiologically rather than as relocation.
    whole_dish = args.prompt == 'metered'
    believed_s = None      # the model's period from the previous turn
    last_turn_at = None
    num_ctx = args.num_ctx or getattr(config, 'LLM_NUM_CTX', None)
    compact_state = adversarial

    trail = None
    if mimic:
        trail = Trail(os.path.join(config.DATA_DIR, 'trail.json'))
        history_turns = -1          # no history at all, not a window of it

    if adversarial:
        if not num_ctx:
            num_ctx = 32768
        history_turns = 0
    elif history_turns == 0 and not num_ctx:
        print("history is uncapped with no num_ctx set: the context will fill\n"
              "and Ollama will silently drop the oldest turns. Set LLM_NUM_CTX.")

    # Metering scales a base, so it needs one. LLM_NUM_CTX is None by default
    # and there would be nothing to scale; this base applies only under
    # --metered and leaves the unmetered loop exactly as it was.
    if args.metered and not num_ctx:
        num_ctx = 8192
    sham_rate = (args.sham_rate if args.sham_rate is not None
                 else getattr(config, 'LLM_SHAM_RATE', 0.25))
    channels = tuple(getattr(config, 'ADC_CHANNELS', (0, 1, 2)))

    # Replay implies dry run: driving the panel from a recording puts real light
    # on the organism from data that is not about it.
    if args.replay:
        args.dry_run = True

    # A real run applies exactly what the model asked for and nothing else.
    min_stimulus_s = 0.0

    prompts = load_prompts()
    if args.prompt not in prompts:
        print(f"unknown prompt '{args.prompt}'; have {sorted(prompts)}")
        return 1
    system = prompts[args.prompt]

    ollama = Ollama(args.host, args.model, num_ctx=num_ctx)
    turns_log = TurnLog(config.LOG_DIR, replay=bool(args.replay) or args.dry_run)

    # When the light actually moved. The turn record cannot say: it is written
    # while the stimulus is still on, so the off time does not exist yet.
    #
    # These rows let analysis drop ADC samples caught in a switching transient.
    # bus.SwitchGate only covers the API process; loop.py drives matrixd, which
    # is outside that lock, so a zone change can land mid-conversion.
    switch_log = TurnLog(config.LOG_DIR, replay=bool(args.replay) or args.dry_run,
                         prefix='switches')

    def switch_recorder(turn_index):
        """Build the on_switch callback for one turn."""
        def record(event, act):
            switch_log.append({
                "turn": turn_index,
                "event": event,
                "datetime": datetime.now(timezone.utc).astimezone().isoformat(),
                # Epoch seconds too: matching these against ADC sample times is
                # the whole point, and that is arithmetic, not string parsing.
                "timestamp": time.time(),
                "zone": act["zone"],
                "whole_dish": act["zone"] is None,
                "intensity": act["intensity"],
                "requested_s": act.get("duration_s"),
            })
        return record

    # Zone geometry comes from leds.py so there is one definition of how many
    # zones exist.
    import leds

    if args.replay:
        source = ReplaySource(args.replay, window_s, args.interval, channels)
    else:
        source = LiveSource(config, window_s, channels)

    print(f"model    {args.model} at {args.host}")
    ok, detail = ollama.reachable()
    print(f"ollama   {'OK' if ok else 'UNREACHABLE'}: {detail}")
    print(f"source   {source.describe()}")
    if experiment:
        print(f"experiment {experiment['name']}  dish {electrode_config}")
        for flag, both in overrides.items():
            print(f"   override {flag}: config {both['config']!r}, "
                  f"using {both['used']!r}")
    print(f"prompt   {args.prompt}")
    print(f"sham     {sham_rate:.0%} of turns")
    if args.replay:
        print(f"speed    {args.speed}x  (dry run: the matrix is never driven)")

    if args.check:
        return 0 if ok else 1
    if not ok:
        print("\nrefusing to start with the model unreachable")
        return 1

    matrix, matrix_error = open_matrix(args.dry_run)
    print(f"matrix   {'ready' if matrix else 'NOT DRIVEN (' + str(matrix_error) + ')'}")
    if matrix is None and not args.dry_run:
        print("\nActions will be logged but not applied. That is a permanent\n"
              "sham block, not an experiment -- fix the matrix first or pass\n"
              "--dry-run to say so deliberately.")
        return 1

    history, previous, turn = [], None, 0
    # Carried between turns: what the model asked for as its next delay, and
    # what actually caused this turn to fire. Both go in the record.
    requested_s, trigger_why = None, 'start'
    context_used, last_turn_cost = 0, 0
    chars_per_token = None
    # The trend the model predicted last turn and the period it predicted
    # from, held until the next measurement can settle it.
    pending_trend, pending_period_s = None, None
    prediction_scores = []
    # What the previous turn's stimulus actually came to. The dose cap trims
    # silently, so without this the model reasons from what it asked for
    # rather than from what the organism received -- and under a tight cap
    # most turns deliver nothing.
    last_stimulus = None
    dose = DoseLedger(
        getattr(config, 'MAX_DOSE_PER_HOUR_WHOLE_DISH', 30.0) if whole_dish
        else getattr(config, 'MAX_DOSE_PER_HOUR', 300.0))
    if args.trigger == 'clock' or args.replay:
        print(f"\nrunning, a turn every {args.interval}s. ctrl-c to stop.\n")
    else:
        print(f"\nrunning; turns fire when the state changes, no sooner than "
              f"{args.min_gap}s apart. ctrl-c to stop.\n")

    try:
        while args.turns == 0 or turn < args.turns:
            started = time.monotonic()
            series = source.window(turn)

            if series is None:
                print(f"\nreplay exhausted after {turn} turns")
                break

            shortest = min((len(v) for v in series.values()), default=0)
            if shortest < window_s * 0.5:
                print(f"[turn {turn}] only {shortest}s of data, waiting")
                time.sleep(min(args.interval, 60))
                continue

            state = reduce_window(series, previous)
            previous = state

            # Model-facing view; the full state is what gets logged.
            sending = for_model(state, compact=compact_state)
            if mimic:
                # Changes only, plus the trail. No absolute values, and the
                # trail is the only thing that carries across turns.
                trail.step()
                sending = {
                    "changed": state.get("changes_since_last_turn",
                                         ["nothing measurable changed"]),
                    "trail": trail.view(),
                }
            if cycles_mode:
                # The period is the answer, so it cannot be in the question.
                for value in sending.values():
                    if isinstance(value, dict):
                        value.pop('period_s', None)
                sending.pop('reference_period_s', None)
                drift = cycle_error(
                    (time.time() - last_turn_at) if last_turn_at else None,
                    believed_s, measured_period(state))
                if drift:
                    sending['since_last_turn'] = drift

            # What the last stimulus actually came to, not what was asked
            # for. METERED only: its task is to infer the effect of light from
            # its own history, and a trimmed action makes that history false.
            if whole_dish and last_stimulus is not None:
                sending['last_stimulus'] = last_stimulus

            # Metering is recomputed every turn, not once at startup: the
            # point is that the budget moves when the organism's tempo moves.
            turn_ctx, turn_history = num_ctx, history_turns
            metered_info = None
            if args.metered:
                turn_ctx, turn_history = metered_budget(
                    measured_period(state), num_ctx, history_turns)
                ollama.num_ctx = turn_ctx
                metered_info = {
                    'period_s': measured_period(state),
                    'num_ctx': turn_ctx,
                    'history_turns': turn_history,
                }

            if turn_ctx:
                remaining = max(0, turn_ctx - context_used)
                sending["context"] = {
                    "tokens_remaining": remaining,
                    "tokens_total": turn_ctx,
                    "turns_remaining_at_this_rate": (
                        int(remaining / last_turn_cost) if last_turn_cost
                        else None),
                }

            # Consulted every turn rather than once at startup, so a mode
            # change from the admin page lands on the next record. Same
            # reasoning as store.py's run_provider.
            active_run = run_state.current(config)

            record = {
                "turn": turn,
                # Unix float as well as the readable form: this is the same key
                # the readings CSV is written under, so a turn joins to the rows
                # it came from without parsing anything.
                "timestamp": time.time(),
                "datetime": datetime.now(timezone.utc).astimezone().isoformat(),
                "run_id": active_run.get('id', ''),
                "mode": active_run.get('mode', 'test'),
                "prompt": args.prompt,
                # What the run was, and the dish it assumed. Recorded per turn
                # rather than only per run: a run's config can be edited, a
                # turn log is append-only.
                "experiment": experiment['name'] if experiment else None,
                "electrodes": electrode_config,
                "model": {"name": args.model, "num_ctx": num_ctx},
                "source": getattr(source, 'label', 'live'),
                # What caused this turn: a state change above threshold, the
                # delay the model asked for last time, the clock, or a
                # ceiling. The distribution of these over a run says how much
                # of the tempo belonged to the organism.
                "trigger": trigger_why,
                "window_samples": shortest,
                # First and last reading timestamps behind this state, when the
                # source knows them. Replay windows are sample indices into a
                # fixed series and have no wall clock of their own.
                "window": getattr(source, 'last_bounds', None),
                "state": state,
            }
            if args.replay and hasattr(source, 'planted_at'):
                # What was actually in the data, so a note claiming an event
                # can be checked against whether one happened.
                record["events_planted"] = source.planted_at(turn)

            # -1 sends nothing, 0 keeps everything, n keeps the last n turns.
            if turn_history < 0:
                recent = []
            elif turn_history == 0:
                recent = history
            else:
                recent = history[-turn_history * 2:]

            try:
                reply, usage, logprobs = ollama.ask(system, sending, recent)
            except Exception as exc:
                print(f"[turn {turn}] model failed: {exc}")
                record["error"] = str(exc)
                turns_log.append(record)
                turn += 1
                if args.turns and turn >= args.turns:
                    break    # no point waiting for a turn that will not run
                trigger_why = wait_for_turn(source, turn, previous, window_s,
                                            args, requested_s)
                continue

            record["reply"] = reply
            record["usage"] = usage
            record["logprobs"] = logprobs

            # Count our own conversation, not prompt_eval_count: Ollama caps
            # and caches that, so it plateaus below num_ctx and never crosses.
            # Turn 0 calibrates chars-per-token.
            convo_chars = (len(system)
                           + sum(len(m["content"]) for m in history)
                           + len(json.dumps(sending)))
            if usage.get("prompt_tokens") and chars_per_token is None:
                chars_per_token = convo_chars / usage["prompt_tokens"]

            if chars_per_token:
                previous_used = context_used
                context_used = int((convo_chars
                                    + len(json.dumps(reply))) / chars_per_token)
                last_turn_cost = max(1, context_used - previous_used)
                record["context_used"] = context_used

            period_s = measured_period(state)
            record["measured_period_s"] = period_s
            if metered_info:
                record["metered"] = metered_info

            if cycles_mode:
                # Its estimate, not ours: a wrong belief makes a wrong-length
                # stimulus, which is the point.
                stated = believed_period(reply)
                record["believed_period_s"] = stated
                record["cycle_error"] = cycle_error(
                    (time.time() - last_turn_at) if last_turn_at else None,
                    believed_s, period_s)
                believed_s = stated
                last_turn_at = time.time()
                conversion_period = stated
            else:
                conversion_period = period_s

            # Last turn's prediction, now that the period it was about has
            # been measured. Scored here rather than in analysis so the run is
            # self-contained and a miss cannot be reinterpreted after the fact.
            scored = prediction.score(pending_trend, pending_period_s,
                                      period_s, window_s)
            if scored:
                prediction_scores.append(scored)
                record["prediction"] = scored
                record["prediction_tally"] = prediction.tally(prediction_scores)
            pending_trend = prediction.parse_trend(
                reply.get('expected_period_trend'))
            pending_period_s = period_s
            record["expected_period_trend"] = pending_trend

            action, refusal = validate_action(
                reply, leds.ZONES,
                getattr(config, 'MAX_STIMULUS_DURATION', 300),
                getattr(config, 'STIMULUS_INTENSITY', 0.5),
                period_s=conversion_period, whole_dish=whole_dish)
            record["action_refused"] = refusal
            record["dose_capped"] = apply_dose_cap(action, dose)

            # Decided before the action is applied, and never revealed to the
            # model. The reply is already in hand either way, so a sham turn
            # costs exactly what a real one does.
            is_sham = random.random() < sham_rate
            record["sham"] = is_sham
            record["applied"] = False

            if action and not is_sham and not args.dry_run:
                try:
                    apply_action(matrix, action, speed=args.speed,
                                 zones=leds.ZONES,
                                 min_duration=min_stimulus_s,
                                 on_switch=switch_recorder(turn))
                    record["applied"] = True
                    dose.spend(action["duration_s"])
                    record["dose_spent_hour"] = round(dose.spent(), 1)
                except Exception as exc:
                    record["apply_error"] = str(exc)
                    print(f"[turn {turn}] apply failed: {exc}")

            # Told to the model next turn. A sham, a dry run, a refusal or an
            # exhausted budget all come to the same thing from the organism's
            # side: no light. Say so rather than let it assume otherwise.
            if whole_dish:
                asked = 0.0
                light = reply.get('light')
                if isinstance(light, dict):
                    try:
                        asked = float(light.get('duration_s') or 0)
                    except (TypeError, ValueError):
                        asked = 0.0
                delivered = (action["duration_s"]
                             if action and record["applied"] else 0.0)
                last_stimulus = {
                    "requested_s": round(asked, 1),
                    "delivered_s": round(delivered, 1),
                }

            record["action"] = action

            # The model's say in the tempo. Bounded to the same floor and a
            # day's ceiling, so a bad number cannot stall or flood the run.
            requested_s = None
            asked = reply.get('next_turn_s')
            if asked is not None:
                try:
                    requested_s = min(max(float(asked), args.min_gap), 86400)
                except (TypeError, ValueError):
                    record["next_turn_refused"] = f"unusable: {asked!r}"
            record["requested_next_turn_s"] = requested_s

            if mimic:
                # Marked by acting, not by choosing. A sham lays nothing -- the
                # trail is on the surface, and nothing reached it. A dry run is
                # hypothetical throughout, so a valid non-sham action counts,
                # or the trail could never be exercised without an organism.
                laid = record["applied"] or (args.dry_run and action
                                             and not is_sham)
                if laid:
                    trail.mark(action["zone"])
                trail.save()
                record["trail"] = trail.view()

            path = turns_log.append(record)

            history.append({"role": "user", "content": json.dumps(sending)})
            history.append({"role": "assistant", "content": json.dumps(reply)})

            stamp = datetime.now().strftime('%H:%M:%S')
            mark = "SHAM" if is_sham else ("applied" if record["applied"] else "--")
            zone = action["zone"] if action else "none"
            period = state.get(f'ch{channels[0]}', {}).get('period_s')
            planted = "  <-- planted" if record.get("events_planted") else ""
            print(f"[{stamp}] turn {turn}  period {period}s  "
                  f"zone {zone}  {mark}{planted}")
            if mimic:
                print(f"           trail {record['trail']}")
            else:
                print(f"           {str(reply.get('note', ''))[:200]}")
            if num_ctx:
                print(f"           context {context_used}/{num_ctx} tokens, "
                      f"{max(0, num_ctx - context_used)} left")

            turn += 1

            # Stop rather than let Ollama silently evict the oldest turns.
            if num_ctx and last_turn_cost and \
                    context_used + last_turn_cost > num_ctx:
                print(f"\ncontext full: {context_used}/{num_ctx} tokens after "
                      f"{turn} turns. Stopping.")
                break

            # In replay --speed compresses this; live it is always 1.0.
            if args.turns and turn >= args.turns:
                break        # no point waiting for a turn that will not run
            trigger_why = wait_for_turn(source, turn, previous, window_s,
                                        args, requested_s)
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        cancel_stimulus_timer()
        if matrix is not None:
            matrix.clear_stimulus()
        print(f"turns logged under {turns_log.directory}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
