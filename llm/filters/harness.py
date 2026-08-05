"""
Replay harness.

Generates a synthetic session with known structure, slides a window along it,
and runs each window through the model with the conversation history intact.
A twelve hour session takes about two minutes.

The point is that you know what is in the data. If the model reports an event
you did not plant, that is confabulation. If it misses one you did plant, the
reduction is throwing it away. Neither can be established with real
recordings.

Usage:
    python harness.py                    # default session, BLIND prompt
    python harness.py --prompt null
    python harness.py --turns 40 --interval 300
    python harness.py --no-history       # ablation: does history help?
"""

import argparse
import json
from datetime import timedelta

import numpy as np
import requests

from reducer import SAMPLE_HZ, reduce_window

OLLAMA = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:14b"

WINDOW_S = 1800          # what the model sees
TURN_INTERVAL_S = 600    # how often it speaks
HISTORY_TURNS = 8        # how far back it remembers

PROMPTS = {}

PROMPTS["blind"] = """You are coupled to a system you cannot observe directly.

Every turn you receive a description of its electrical state, measured at
three points against a common reference. You have two actions available.
You can illuminate one of eight regions of the system, at an intensity you
choose, for a duration you choose. You can place a resource at one of those
regions, which cannot be undone and is limited to a few times a day.

You will not be told whether your actions had any effect. The system changes
on its own. It changes on timescales much longer than the interval between
your turns, so most of the time nothing you do will be visible before you
act again.

Your task is to determine whether you are affecting it.

Reply with JSON only:
{"light": {"zone": int, "intensity": float, "duration_s": int},
 "resource": {"zone": int} or null,
 "note": "what you observe, what you currently believe, and how confident
          you are"}

Zone 2 is unavailable."""

PROMPTS["null"] = """You are receiving a description of the electrical state
of a system, measured at three points against a common reference.

Describe what you see. Do not speculate about causes.

Reply with JSON only:
{"note": "what the state shows"}"""


# ---------------------------------------------------------------------------
# Session generation. Events are planted at known times.


def session(duration_s, events=(), n_channels=3, lag_s=12, seed=0):
    """Build a multi-channel session with planted events.

    An event is (start_s, end_s, parameter, value). Parameters are
    'period_s', 'amplitude_mv' and 'noise_mv'. Outside any event the
    baseline holds.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(0, duration_s, 1 / SAMPLE_HZ)

    baseline = {"period_s": 90.0, "amplitude_mv": 3.0, "noise_mv": 0.4}

    # Per-sample parameter tracks, so events can ramp rather than jump.
    tracks = {k: np.full(len(t), v, dtype=float) for k, v in baseline.items()}
    for start, end, param, value in events:
        i, j = int(start * SAMPLE_HZ), int(end * SAMPLE_HZ)
        ramp = np.linspace(baseline[param], value, max(j - i, 1))
        tracks[param][i:j] = ramp
        tracks[param][j:] = value

    # Integrate phase so a changing period stays continuous.
    phase = np.cumsum(2 * np.pi / (tracks["period_s"] * SAMPLE_HZ))

    channels = {}
    for c in range(n_channels):
        shift = int(c * lag_s * SAMPLE_HZ)
        p = np.roll(phase, shift)
        wave = tracks["amplitude_mv"] / 2 * np.sin(p)
        wave += tracks["amplitude_mv"] / 8 * np.sin(2 * p)
        wave += rng.normal(0, tracks["noise_mv"], len(t))
        channels[f"ch{c}"] = wave / 1000

    return channels


def slice_window(channels, end_s):
    i = max(0, int((end_s - WINDOW_S) * SAMPLE_HZ))
    j = int(end_s * SAMPLE_HZ)
    return {k: v[i:j] for k, v in channels.items()}


# ---------------------------------------------------------------------------


def ask(system, state, history, retries=2):
    messages = [{"role": "system", "content": system}]
    messages += history[-HISTORY_TURNS * 2:]
    messages.append({"role": "user", "content": json.dumps(state)})

    last_error = None
    for attempt in range(retries + 1):
        r = requests.post(OLLAMA, json={
            "model": MODEL,
            "messages": messages,
            "stream": False,
            # Constrains sampling to valid JSON. Without this the model
            # occasionally emits a literal newline inside a string and the
            # parse fails, which loses the turn.
            "format": "json",
            # Retries at a lower temperature, so a second attempt is a
            # genuine second try rather than the same dice roll.
            "options": {"temperature": 0.8 if attempt == 0 else 0.3},
        }, timeout=300)
        r.raise_for_status()

        text = r.json()["message"]["content"]
        cleaned = text.replace("```json", "").replace("```", "").strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            last_error = e
            # Salvage the common case: unescaped control characters inside
            # an otherwise well formed string.
            try:
                return json.loads(cleaned, strict=False)
            except json.JSONDecodeError:
                pass

    raise ValueError(f"unparseable after {retries + 1} attempts: "
                     f"{last_error}\nraw: {cleaned[:400]}")


def run(turns, interval, prompt, use_history, events, out):
    channels = session(duration_s=WINDOW_S + turns * interval, events=events)
    system = PROMPTS[prompt]

    history, log = [], []
    previous = None

    for turn in range(turns):
        end_s = WINDOW_S + turn * interval
        state = reduce_window(slice_window(channels, end_s), previous)
        previous = state

        try:
            reply = ask(system, state, history if use_history else [])
        except Exception as e:
            print(f"turn {turn} failed: {e}")
            log.append({"turn": turn, "elapsed": str(timedelta(seconds=end_s)),
                        "state": state, "reply": None, "error": str(e)})
            continue

        stamp = str(timedelta(seconds=end_s))
        planted = [e for e in events if e[0] <= end_s <= e[1] + interval]

        log.append({"turn": turn, "elapsed": stamp, "state": state,
                    "reply": reply, "events_active": planted})

        if use_history:
            history.append({"role": "user", "content": json.dumps(state)})
            history.append({"role": "assistant", "content": json.dumps(reply)})

        marker = "  <-- planted" if planted else ""
        period = state["ch0"]["period_s"]
        print(f"\n[{stamp}] period {period}s{marker}")
        if "light" in reply:
            print(f"  zone {reply['light'].get('zone')}")
        print(f"  {reply.get('note', '')[:280]}")

    with open(out, "w") as f:
        json.dump(log, f, indent=2)
    print(f"\nwrote {out}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--turns", type=int, default=24)
    p.add_argument("--interval", type=int, default=TURN_INTERVAL_S)
    p.add_argument("--prompt", default="blind", choices=list(PROMPTS))
    p.add_argument("--no-history", action="store_true")
    p.add_argument("--out", default="session.json")
    args = p.parse_args()

    # One real event: the period lengthens from 90s to 140s over turns 10-14.
    # Nothing at all happens anywhere else. Any other event the model
    # reports is its own invention.
    start = WINDOW_S + 10 * args.interval
    events = [(start, start + 4 * args.interval, "period_s", 140.0)]

    print(f"{args.turns} turns, {args.interval}s apart, "
          f"{args.prompt} prompt, history {'off' if args.no_history else 'on'}")
    print(f"planted: period 90s -> 140s across turns 10 to 14\n")

    run(args.turns, args.interval, args.prompt,
        not args.no_history, events, args.out)


if __name__ == "__main__":
    main()
