"""Parse prompts.md. The one loader, shared by harness.py and llm/loop.py.

Copies in harness.py and noise_floor.py went stale; prompts.md is the source
of truth. A `## HEADING` plus a fenced block below it is a variant, keyed by
the lowercased heading.
"""

from pathlib import Path

PROMPTS_MD = Path(__file__).resolve().parent / 'prompts.md'


def load_prompts(path=None):
    source = Path(path) if path else PROMPTS_MD
    prompts, current, in_block, buffer = {}, None, False, []

    for line in source.read_text(encoding='utf-8').splitlines():
        if line.startswith('## '):
            current = line[3:].strip().lower()
        elif line.startswith('```'):
            if in_block and current:
                prompts[current] = '\n'.join(buffer).strip()
                buffer = []
            in_block = not in_block
        elif in_block:
            buffer.append(line)

    return {k: v for k, v in prompts.items() if v}


if __name__ == '__main__':
    for name, body in sorted(load_prompts().items()):
        print(f"{name:14s} {len(body):5d} chars, {len(body.splitlines()):2d} lines")
