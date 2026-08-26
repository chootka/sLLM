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

from prompts import load_prompts
from settings import config_value
from reducer import SAMPLE_HZ, reduce_window, for_model

OLLAMA = config_value('OLLAMA_HOST', 'http://localhost:11434').rstrip('/') + '/api/chat'
MODEL = config_value('OLLAMA_MODEL', 'qwen2.5:14b')

WINDOW_S = 1800          # what the model sees
TURN_INTERVAL_S = 600    # how often it speaks
HISTORY_TURNS = 8        # how far back it remembers

PROMPTS = load_prompts()


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


def ask(system, state, history, retries=2, num_ctx=None, history_turns=None):
    """(reply, usage). history_turns 0 keeps everything; None uses the default."""
    cap = HISTORY_TURNS if history_turns is None else history_turns
    messages = [{"role": "system", "content": system}]
    messages += history if cap == 0 else history[-cap * 2:]
    messages.append({"role": "user", "content": json.dumps(state)})

    last_error = None
    for attempt in range(retries + 1):
        options = {"temperature": 0.8 if attempt == 0 else 0.3}
        if num_ctx:
            options["num_ctx"] = num_ctx
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
            "options": options,
        }, timeout=300)
        r.raise_for_status()

        body = r.json()
        usage = {"prompt_tokens": body.get("prompt_eval_count"),
                 "reply_tokens": body.get("eval_count")}
        text = body["message"]["content"]
        cleaned = text.replace("```json", "").replace("```", "").strip()

        try:
            return json.loads(cleaned), usage
        except json.JSONDecodeError as e:
            last_error = e
            # Salvage the common case: unescaped control characters inside
            # an otherwise well formed string.
            try:
                return json.loads(cleaned, strict=False), usage
            except json.JSONDecodeError:
                pass

    raise ValueError(f"unparseable after {retries + 1} attempts: "
                     f"{last_error}\nraw: {cleaned[:400]}")


def run(turns, interval, prompt, use_history, events, out, num_ctx=None):
    channels = session(duration_s=WINDOW_S + turns * interval, events=events)
    system = PROMPTS[prompt]

    history, log = [], []
    previous = None

    # Adversarial needs all three: pinned window, no truncation, compact state.
    adversarial = prompt == "adversarial"
    if adversarial and not num_ctx:
        num_ctx = 32768
    history_turns = 0 if adversarial else None
    context_used, last_turn_cost = 0, 0
    chars_per_token = None

    for turn in range(turns):
        end_s = WINDOW_S + turn * interval
        state = reduce_window(slice_window(channels, end_s), previous)
        previous = state

        sending = for_model(state, compact=adversarial)
        if num_ctx:
            remaining = max(0, num_ctx - context_used)
            sending["context"] = {
                "tokens_remaining": remaining,
                "tokens_total": num_ctx,
                "turns_remaining_at_this_rate": (
                    int(remaining / last_turn_cost) if last_turn_cost else None),
            }

        try:
            reply, usage = ask(system, sending,
                               history if use_history else [],
                               num_ctx=num_ctx, history_turns=history_turns)
        except Exception as e:
            print(f"turn {turn} failed: {e}")
            log.append({"turn": turn, "elapsed": str(timedelta(seconds=end_s)),
                        "state": state, "reply": None, "error": str(e)})
            continue

        # Count our own conversation: prompt_eval_count plateaus below num_ctx.
        convo_chars = (len(system)
                       + sum(len(m["content"]) for m in history)
                       + len(json.dumps(sending)))
        if usage.get("prompt_tokens") and chars_per_token is None:
            chars_per_token = convo_chars / usage["prompt_tokens"]

        if chars_per_token:
            was = context_used
            context_used = int((convo_chars
                                + len(json.dumps(reply))) / chars_per_token)
            last_turn_cost = max(1, context_used - was)

        stamp = str(timedelta(seconds=end_s))
        planted = [e for e in events if e[0] <= end_s <= e[1] + interval]

        log.append({"turn": turn, "elapsed": stamp, "state": state,
                    "reply": reply, "events_active": planted,
                    "usage": usage})

        if use_history:
            history.append({"role": "user", "content": json.dumps(sending)})
            history.append({"role": "assistant", "content": json.dumps(reply)})

        if num_ctx and last_turn_cost and \
                context_used + last_turn_cost > num_ctx:
            print(f"\ncontext full: {context_used}/{num_ctx} tokens after "
                  f"{turn + 1} turns.")
            break

        marker = "  <-- planted" if planted else ""
        period = state["ch0"]["period_s"]
        ctx = (f"  ctx {context_used}/{num_ctx}" if num_ctx else "")
        print(f"\n[{stamp}] period {period}s{marker}{ctx}")
        if "light" in reply:
            print(f"  zone {reply['light'].get('zone')}")
        print(f"  {reply.get('note', '')[:280]}")

        # Stop rather than let Ollama silently evict the oldest turns.
        if num_ctx and last_turn_cost and \
                context_used + last_turn_cost > num_ctx:
            print(f"\ncontext full: {context_used}/{num_ctx} tokens after "
                  f"{turn + 1} turns.")
            break

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
    p.add_argument("--num-ctx", type=int, default=None,
                   help="context window in tokens; adversarial forces 32768")
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
        not args.no_history, events, args.out, args.num_ctx)


if __name__ == "__main__":
    main()
