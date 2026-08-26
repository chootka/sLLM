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

--demo is the one mode that runs fast AND drives the panel, for watching the
hardware actually work:

    ./scripts/py llm/loop.py --demo --turns 12

It exists because nothing else could show you the physical chain. The live loop
cannot be sped up without being made meaningless -- the 30 minute window and
the 10 minute turn come from Physarum's contraction period, not from caution --
so live, a zone changes once every ten minutes. Replay is fast but refuses to
actuate. Between them there was no way to watch a zone go on and off.

--demo therefore invents data and puts real light on the panel, which is only
acceptable when the chamber is empty. It refuses to start while the recording
mode is `live`, and its turns are written to data/logs/replay/ so they can
never be confused with a real session.

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

import syspath  # noqa: E402,F401  (path setup, must precede hardware imports)

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


def validate_action(reply, zones, barrier_zone, max_duration, period_s=None):
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
    """
    light = reply.get('light')
    if not isinstance(light, dict):
        return None, "no light action"

    try:
        zone = int(light['zone'])
        intensity = float(light.get('intensity', 1.0))
        if light.get('duration_cycles') is not None:
            cycles = float(light['duration_cycles'])
            if not period_s:
                return None, "duration in cycles but no period measured"
            duration = cycles * period_s
        else:
            duration = float(light.get('duration_s', 60))
    except (KeyError, TypeError, ValueError) as exc:
        return None, f"malformed light action: {exc}"

    if zone == barrier_zone:
        return None, f"zone {zone} is the barrier and is not drivable"
    if not 0 <= zone < zones:
        return None, f"zone {zone} outside 0..{zones - 1}"

    action = {
        "zone": zone,
        "intensity": min(max(intensity, 0.0), 1.0),
        "duration_s": min(max(duration, 0.0), max_duration),
    }
    if light.get('duration_cycles') is not None:
        # Kept so the log says what was asked for as well as what it became.
        action["duration_cycles"] = float(light['duration_cycles'])
        action["period_s_at_request"] = period_s
    return action, None


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


def apply_action(matrix, action, speed=1.0, min_duration=0.0,
                 hold_until_next=False, full_intensity=False, on_switch=None):
    """Light the zone, and take it off again after the duration requested.

    `speed` compresses the duration alongside the turn interval, so a demo run
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
    if full_intensity:
        # The model's 0.5-0.8 against STIM_BRIGHTNESS lands near 31/255, twice
        # the barrier and easy to miss in a lit room. A demo shows which zone,
        # not how brightly.
        intensity = 1.0

    # Worked out before the zone is lit: a zero-length request must not light it
    # at all. Computing this after set_zone left the zone on with nothing armed
    # to clear it, so zero seconds lasted until the next turn.
    #
    # Scaling duration with the interval keeps the on/off ratio honest, but at
    # 60x a 60s pulse is a one-second blink. min_duration is the visibility
    # floor, set only in demo.
    duration = (action.get("duration_s") or 0) / max(speed, 1e-9)
    if duration > 0:
        duration = max(duration, min_duration)

    # Clear rather than light-then-clear: the zone is already dark, and a
    # set/clear pair spends a switching edge saying so. hold_until_next is
    # exempt -- a demo shows the choice whatever duration was asked for.
    if not hold_until_next and duration <= 0:
        matrix.clear_stimulus()
        return

    matrix.clear_stimulus()
    matrix.set_zone(action["zone"], intensity)
    _switch('on')

    # Demo holds the zone until the next choice, so the panel visibly moves.
    # Scaling the duration instead gave ~13% duty, which nobody can watch.
    if hold_until_next:
        return

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
    parser.add_argument('--prompt', default=getattr(config, 'LLM_PROMPT', 'blind'))
    parser.add_argument('--turns', type=int, default=0, help='0 runs forever')
    parser.add_argument('--interval', type=int,
                        default=getattr(config, 'LLM_TURN_INTERVAL', 600))
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
    parser.add_argument('--sham-rate', type=float, default=None)
    parser.add_argument('--num-ctx', type=int, default=None,
                        help='context window in tokens; pins the denominator '
                             'the adversarial prompt reports to the model')
    parser.add_argument('--demo', action='store_true',
                        help='synthetic data at speed, DRIVING the panel. For '
                             'exercising the hardware; refuses if the chamber '
                             'is occupied. Turns go to the replay log.')
    args = parser.parse_args()

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

    window_s = getattr(config, 'LLM_WINDOW_S', 1800)
    history_turns = getattr(config, 'LLM_HISTORY_TURNS', 8)

    # Each variant that changes the loop, not only the wording, is wired here.
    # Adversarial needs all three of pinned window, no truncation and compact
    # state; mimic needs all four of no history, trail, changes-only and no
    # note. Any one missing and the prompt describes something that is not
    # happening.
    adversarial = args.prompt == 'adversarial'
    mimic = args.prompt == 'mimic'
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
    sham_rate = (args.sham_rate if args.sham_rate is not None
                 else getattr(config, 'LLM_SHAM_RATE', 0.25))
    channels = tuple(getattr(config, 'ADC_CHANNELS', (0, 1, 2)))

    # Replay implies dry run: driving the panel from a recording puts real light
    # on the organism from data that is not about it.
    #
    # --demo is the one exception, and exists because the live loop cannot be
    # sped up without becoming meaningless. It is safe because it is loud, gated
    # on an empty chamber, and logs to data/logs/replay/.
    if args.demo:
        # Read fresh every start from the recording mode: `live` means a real
        # session, which means something is in the chamber. A separate occupancy
        # flag used to say the same thing and went stale, because nothing broke
        # when it did.
        if run_state.current(config).get('mode') == 'live':
            print("refusing --demo: recording is live, so the chamber is taken\n"
                  "to be occupied. This mode invents data and puts real light on\n"
                  "the panel. Switch recording to test in the admin panel, and\n"
                  "only when there is nothing alive in the chamber.")
            return 1
        if not args.replay:
            args.replay = 'synthetic'
        if args.speed == 1.0:
            # 60x turns a 600s interval into 10s, which is watchable.
            args.speed = 60.0
        args.dry_run = False
        # No shams in a demo. A sham is a control condition and a demonstration
        # has nothing to control for -- all it does is make a quarter of the
        # turns light nothing, which reads as broken hardware to whoever is
        # watching. That is the opposite of what this mode is for.
        if args.sham_rate is None:
            args.sham_rate = 0.0
    elif args.replay:
        args.dry_run = True

    # In demo, hold each zone for a visible fraction of the effective turn
    # interval -- long enough to see, short enough to still go off before the
    # next turn. Zero outside demo: a real run must apply exactly what the model
    # asked for and nothing else.
    min_stimulus_s = 0.0
    if args.demo:
        min_stimulus_s = max(6.0, (args.interval / max(args.speed, 1e-9)) * 0.5)

    # sham_rate above still holds the config default, so take the demo value
    # from args. A demo has nothing to control for, and a sham reads as broken
    # hardware to a viewer.
    #
    # Do not test `args.sham_rate is None` here -- the --demo block has already
    # set it to 0.0, so the override never fires and a hand-run demo gets 25%.
    if args.demo:
        sham_rate = args.sham_rate

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
                "intensity": act["intensity"],
                "requested_s": act.get("duration_s"),
            })
        return record

    # Zone geometry comes from leds.py so there is one definition of how many
    # zones exist and which one is the barrier.
    import leds

    if args.replay:
        source = ReplaySource(args.replay, window_s, args.interval, channels)
    else:
        source = LiveSource(config, window_s, channels)

    print(f"model    {args.model} at {args.host}")
    ok, detail = ollama.reachable()
    print(f"ollama   {'OK' if ok else 'UNREACHABLE'}: {detail}")
    print(f"source   {source.describe()}")
    print(f"prompt   {args.prompt}")
    print(f"sham     {sham_rate:.0%} of turns")
    if args.replay:
        if args.demo:
            print(f"speed    {args.speed}x")
            print("\n*** DEMO MODE ***\n"
                  "Invented data, driving the real panel. Turns are written to\n"
                  "data/logs/replay/ and are NOT part of the experimental record.\n"
                  "Never run this with anything alive in the chamber.\n")
        else:
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
            if num_ctx:
                remaining = max(0, num_ctx - context_used)
                sending["context"] = {
                    "tokens_remaining": remaining,
                    "tokens_total": num_ctx,
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
            if history_turns < 0:
                recent = []
            elif history_turns == 0:
                recent = history
            else:
                recent = history[-history_turns * 2:]

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
            action, refusal = validate_action(
                reply, leds.ZONES, leds.BARRIER_ZONE,
                getattr(config, 'MAX_STIMULUS_DURATION', 300),
                period_s=period_s)
            record["action_refused"] = refusal

            # Decided before the action is applied, and never revealed to the
            # model. The reply is already in hand either way, so a sham turn
            # costs exactly what a real one does.
            is_sham = random.random() < sham_rate
            record["sham"] = is_sham
            record["applied"] = False

            if action and not is_sham and not args.dry_run:
                try:
                    apply_action(matrix, action, speed=args.speed,
                                 min_duration=min_stimulus_s,
                                 hold_until_next=args.demo,
                                 full_intensity=args.demo,
                                 on_switch=switch_recorder(turn))
                    record["applied"] = True
                except Exception as exc:
                    record["apply_error"] = str(exc)
                    print(f"[turn {turn}] apply failed: {exc}")

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
                    trail.mark(action["zone"], action["intensity"])
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
