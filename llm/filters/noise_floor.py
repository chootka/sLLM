"""Model noise floor: one identical snapshot, N times, how much the output varies.

The counterpart to recording an empty chamber.

    python noise_floor.py            # null prompt, describe only
    python noise_floor.py blind
"""

import json
import sys
from collections import Counter
from pathlib import Path

import requests

from prompts import load_prompts
from settings import config_value
from reducer import for_model, reduce_window, synth



OLLAMA = config_value('OLLAMA_HOST', 'http://localhost:11434').rstrip('/') + '/api/chat'
MODEL = config_value('OLLAMA_MODEL', 'qwen2.5:14b')
RUNS = 50
PROMPTS = load_prompts()

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
    if mode not in PROMPTS:
        print(f"unknown prompt '{mode}'; have {sorted(PROMPTS)}")
        return 1
    system = PROMPTS[mode]

    # Frozen. Every run sees exactly this.
    state = for_model(reduce_window({
        "ch0": synth(lag_s=0, seed=1),
        "ch1": synth(lag_s=12, seed=2),
        "ch2": synth(lag_s=24, seed=3),
    }))

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

    return 0


if __name__ == "__main__":
    sys.exit(main())
