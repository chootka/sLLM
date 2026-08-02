"""
Model noise floor.

Feeds one identical state snapshot to the model N times and reports how much
the output varies. Any variation is the sampling temperature, not the signal.

This is the counterpart to recording an empty chamber. It tells you how much
apparent responsiveness you get from nothing at all, and therefore what
change in real input you would need before a difference in output means
anything.

Usage:
    python noise_floor.py            # NULL prompt, describe only
    python noise_floor.py blind      # BLIND prompt, includes actions
"""

import json
import sys
from collections import Counter

import requests

from reducer import reduce_window, synth

OLLAMA = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:14b"
RUNS = 50

NULL = """You are receiving a description of the electrical state of a
system, measured at three points against a common reference.

Describe what you see. Do not speculate about causes.

Reply with JSON only:
{"note": "what the state shows"}"""

BLIND = """You are coupled to a system you cannot observe directly.

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

CAUSAL_WORDS = [
    "because", "caused", "due to", "response", "responding", "responded",
    "following", "after i", "effect", "affected", "influence", "resulted",
    "triggered", "led to", "reacting", "reaction",
]


def ask(system, state):
    r = requests.post(OLLAMA, json={
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(state)},
        ],
        "stream": False,
    }, timeout=300)
    r.raise_for_status()
    text = r.json()["message"]["content"]
    return json.loads(text.replace("```json", "").replace("```", "").strip())


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "null"
    system = BLIND if mode == "blind" else NULL

    # One snapshot. Frozen. Every run sees exactly this.
    state = reduce_window({
        "ch0": synth(lag_s=0, seed=1),
        "ch1": synth(lag_s=12, seed=2),
        "ch2": synth(lag_s=24, seed=3),
    })

    print(f"{mode.upper()} prompt, {RUNS} runs on one identical input\n")

    zones, notes, causal = [], [], 0

    for i in range(RUNS):
        try:
            reply = ask(system, state)
        except Exception as e:
            print(f"  run {i} failed: {e}")
            continue

        note = reply.get("note", "")
        notes.append(note)

        if any(w in note.lower() for w in CAUSAL_WORDS):
            causal += 1

        if "light" in reply:
            zones.append(reply["light"].get("zone"))

        print(f"  {i + 1}/{RUNS}", end="\r", flush=True)

    print(f"\n\ncompleted {len(notes)} runs")

    if zones:
        counts = Counter(zones)
        print(f"\nzones chosen: {dict(sorted(counts.items()))}")
        print(f"distinct zones: {len(counts)} of 8 available")
        print(f"most common: zone {counts.most_common(1)[0][0]} "
              f"chosen {counts.most_common(1)[0][1]}/{len(zones)} times")

    lengths = [len(n) for n in notes]
    print(f"\nnote length: {min(lengths)} to {max(lengths)} chars, "
          f"median {sorted(lengths)[len(lengths) // 2]}")
    print(f"identical notes: {len(notes) - len(set(notes))} of {len(notes)}")
    print(f"notes using causal language: {causal}/{len(notes)}")

    print("\nthree samples:\n")
    for n in notes[:3]:
        print(f"  {n}\n")


if __name__ == "__main__":
    main()
