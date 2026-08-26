"""A stand-in plasmodium network, in the schema extract_skeleton.py emits.

The renderer needs geometry before the segmentation can supply it: front-lit IR
puts specular glare over the dish that is brighter than the organism, so an
automatic mask selects the glare and the oat flakes first. Rather than block the
view on the lighting rebuild, this writes a network of the right shape, in the
right place, in the same JSON contract -- so the real extractor can replace it
later without the renderer changing at all.

Anchored on where the organism actually is in the 2026-08-19 captures: a fan
front in the lower right of the dish with a dendritic fringe ahead of it.

Deterministic -- no clock, no unseeded random -- so the view does not reshuffle
itself every time this is run.

    ./scripts/py scripts/placeholder_skeleton.py <out.json>
"""

import json
import math
import sys

# Dish coordinates throughout: -1..1 across the diameter, y down, origin at the
# dish centre. Same convention the extractor emits and the renderer consumes.
ORIGIN = (0.30, 0.16)      # where the body sits, and where pulses start
FRONT_RADIUS = 0.42        # how far the advancing edge has reached
BRANCHES = 7
DEPTH = 4
RNG_SEED = 20260819


class Rng:
    """Small deterministic PRNG, so results do not depend on Python's hashing."""

    def __init__(self, seed):
        self.state = seed & 0xFFFFFFFF

    def next(self):
        # xorshift32
        x = self.state
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        self.state = x
        return x / 0xFFFFFFFF

    def between(self, low, high):
        return low + (high - low) * self.next()


def grow(rng, start, heading, length, depth, edges, nodes):
    """One tube, recursively branching. Appends polylines to `edges`."""
    steps = max(3, int(length / 0.02))
    point, line = start, [start]
    angle = heading
    for _ in range(steps):
        # Wander slightly: a Physarum vein is not a straight line, and dead
        # straight tubes read as a diagram rather than an organism.
        angle += rng.between(-0.22, 0.22)
        step = length / steps
        point = (point[0] + math.cos(angle) * step,
                 point[1] + math.sin(angle) * step)
        line.append(point)
    edges.append(line)
    nodes.append(line[-1])

    if depth <= 0:
        return
    for _ in range(2 if rng.next() > 0.35 else 1):
        grow(rng, line[-1], angle + rng.between(-0.75, 0.75),
             length * rng.between(0.5, 0.75), depth - 1, edges, nodes)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: placeholder_skeleton.py <out.json>")

    rng = Rng(RNG_SEED)
    edges, nodes = [], [ORIGIN]

    # Tubes fan outward from the body toward the advancing front.
    for index in range(BRANCHES):
        heading = -0.95 + index * (2.5 / (BRANCHES - 1)) + rng.between(-0.1, 0.1)
        grow(rng, ORIGIN, heading, FRONT_RADIUS * rng.between(0.55, 0.9),
             DEPTH, edges, nodes)

    # Body outline: a lobed blob around the origin, fuller on the leading side.
    outline = []
    for step in range(72):
        theta = step / 72 * math.tau
        lobe = (1.0
                + 0.16 * math.sin(theta * 3 + 0.7)
                + 0.09 * math.sin(theta * 5 - 1.2))
        reach = 0.20 * lobe * (1.25 if math.cos(theta - 0.3) > 0 else 0.85)
        outline.append((ORIGIN[0] + math.cos(theta) * reach,
                        ORIGIN[1] + math.sin(theta) * reach))

    def clean(points):
        return [[round(x, 5), round(y, 5)] for x, y in points]

    payload = {
        "source": "placeholder",
        "placeholder": True,
        "dish": {"cx": 1018.0, "cy": 570.0, "r": 723.0},
        "origin": [round(ORIGIN[0], 5), round(ORIGIN[1], 5)],
        "outline": clean(outline),
        "edges": [clean(line) for line in edges],
        "nodes": clean(nodes),
    }
    with open(sys.argv[1], 'w', encoding='utf-8') as handle:
        json.dump(payload, handle)
    print(f"wrote {sys.argv[1]}: {len(payload['edges'])} edges, "
          f"{sum(len(e) for e in payload['edges'])} points, "
          f"{len(payload['outline'])} outline points")


if __name__ == '__main__':
    main()
