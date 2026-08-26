"""Plasmodium skeleton from one capture, as JSON for the WebGL view.

Provisional by design. Clean segmentation wants an even backlight and the rig
is front-lit by an IR flood, so the agar surface returns specular glare that is
brighter than the organism. Brightness thresholding therefore cannot separate
them -- it selects the glare first.

What does separate is texture. The plasmodium has a scalloped advancing front
and a dendritic fringe; glare is smooth at every scale. So the mask here is
local standard deviation after a high-pass, which fires on venation and ignores
the hotspot entirely.

The output schema is the contract with the frontend and is meant to outlive this
particular extraction method:

    {"dish": {"cx","cy","r"},           # circle in image pixels
     "outline": [[x,y], ...],           # body boundary, dish coords -1..1
     "edges":   [[[x,y], ...], ...],    # tube polylines, dish coords -1..1
     "nodes":   [[x,y], ...]}           # junctions and tips

Dish coordinates are -1..1 across the dish diameter, y down, so the renderer
never has to know the image resolution or where the dish sat in frame.

    ./scripts/py scripts/extract_skeleton.py <image.jpg> <out.json>
"""

import json
import sys

import cv2
import numpy as np

# The organism is in this corner of the dish. A whole-dish search picks up the
# electrode wires and the oat flakes, which have texture too; until the mask can
# reject those on their own merits, the region is given rather than found.
ROI = (1200, 1800, 660, 1000)   # x0, x1, y0, y1
TEXTURE_PERCENTILE = 96.0
RIM_FRACTION = 0.90             # ignore anything closer to the wall than this
MIN_COMPONENT = 150             # px; below this it is speckle


def dish_circle(gray):
    """Find the petri dish rim. Returns (cx, cy, r) in full-resolution pixels.

    The accumulator threshold is swept rather than fixed: the rim contrast
    changes with the flood and with how much condensation is on the lid, and a
    single value that works tonight silently finds nothing next week.
    """
    h, w = gray.shape
    small = cv2.medianBlur(cv2.resize(gray, (w // 4, h // 4)), 5)
    for param2 in (60, 50, 42, 35, 28):
        found = cv2.HoughCircles(
            small, cv2.HOUGH_GRADIENT, dp=1, minDist=200,
            param1=80, param2=param2, minRadius=110, maxRadius=200,
        )
        if found is not None:
            cx, cy, r = found[0][0] * 4
            print(f"dish rim at ({cx:.0f}, {cy:.0f}) r {r:.0f} (param2 {param2})")
            return float(cx), float(cy), float(r)
    raise SystemExit("no dish rim found; pass --circle cx,cy,r")


def texture(gray):
    """Local standard deviation of the high-passed image."""
    image = gray.astype(np.float32)
    high = image - cv2.GaussianBlur(image, (0, 0), 45)
    mean = cv2.blur(high, (13, 13))
    power = cv2.blur(high * high, (13, 13))
    return np.sqrt(np.maximum(power - mean * mean, 0))


def thin(mask):
    """Zhang-Suen thinning to a one-pixel skeleton.

    Vectorised over the whole image per pass rather than per pixel; OpenCV's own
    thinning lives in ximgproc, which is not in the contrib build here.
    """
    work = (mask > 0).astype(np.uint8)
    while True:
        removed = False
        for step in (0, 1):
            p = np.pad(work, 1)
            # 8-neighbourhood, clockwise from north
            n = [p[:-2, 1:-1], p[:-2, 2:], p[1:-1, 2:], p[2:, 2:],
                 p[2:, 1:-1], p[2:, :-2], p[1:-1, :-2], p[:-2, :-2]]
            count = sum(n)
            ring = n + [n[0]]
            crossings = sum(((ring[i] == 0) & (ring[i + 1] == 1)).astype(np.uint8)
                            for i in range(8))
            if step == 0:
                a = n[0] * n[2] * n[4]
                b = n[2] * n[4] * n[6]
            else:
                a = n[0] * n[2] * n[6]
                b = n[0] * n[4] * n[6]
            drop = ((work == 1) & (count >= 2) & (count <= 6) &
                    (crossings == 1) & (a == 0) & (b == 0))
            if drop.any():
                work[drop] = 0
                removed = True
        if not removed:
            return work


def trace(skeleton):
    """One-pixel skeleton -> (polylines, node coordinates).

    Walks each run between junctions and tips. Pixels of degree two are
    interior; anything else ends a segment.
    """
    points = {(int(y), int(x)) for y, x in zip(*np.nonzero(skeleton))}

    def around(point):
        y, x = point
        return [(y + dy, x + dx)
                for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if (dy or dx) and (y + dy, x + dx) in points]

    degree = {p: len(around(p)) for p in points}
    ends = {p for p, d in degree.items() if d != 2}

    polylines, walked = [], set()
    for start in ends:
        for first in around(start):
            if (start, first) in walked:
                continue
            line, previous, current = [start, first], start, first
            walked.add((start, first))
            while degree.get(current, 0) == 2:
                nxt = [q for q in around(current) if q != previous]
                if not nxt:
                    break
                previous, current = current, nxt[0]
                line.append(current)
            walked.add((current, previous))
            if len(line) > 4:
                polylines.append(line)

    # Closed loops touch no endpoint, so nothing above reaches them. They are
    # real structure -- Physarum networks contain cycles -- so pick them up by
    # walking whatever is left over.
    seen = {p for line in polylines for p in line}
    for start in points - seen:
        if start in seen:
            continue
        line, current, previous = [start], start, None
        seen.add(start)
        while True:
            nxt = [q for q in around(current) if q != previous and q not in seen]
            if not nxt:
                break
            previous, current = current, nxt[0]
            seen.add(current)
            line.append(current)
        if len(line) > 8:
            polylines.append(line)

    return polylines, sorted(ends)


def main():
    argv = list(sys.argv[1:])
    override = None
    if '--circle' in argv:
        at = argv.index('--circle')
        override = tuple(float(v) for v in argv[at + 1].split(','))
        del argv[at:at + 2]
    if len(argv) != 2:
        raise SystemExit(
            "usage: extract_skeleton.py [--circle cx,cy,r] <image.jpg> <out.json>")
    sys.argv = [sys.argv[0]] + argv
    source, target = sys.argv[1], sys.argv[2]

    gray = cv2.imread(source, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise SystemExit(f"could not read {source}")
    height, width = gray.shape
    if override:
        cx, cy, r = override
        print(f"dish rim given: ({cx:.0f}, {cy:.0f}) r {r:.0f}")
    else:
        cx, cy, r = dish_circle(gray)

    tex = texture(gray)
    ys, xs = np.mgrid[0:height, 0:width]
    x0, x1, y0, y1 = ROI
    region = np.zeros((height, width), np.uint8)
    region[y0:y1, x0:x1] = 1
    region &= (((xs - cx) ** 2 + (ys - cy) ** 2) < (r * RIM_FRACTION) ** 2)

    mask = ((tex > np.percentile(tex[region > 0], TEXTURE_PERCENTILE)) &
            (region > 0)).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))

    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    keep = np.zeros_like(mask)
    for index in range(1, count):
        if stats[index, cv2.CC_STAT_AREA] >= MIN_COMPONENT:
            keep[labels == index] = 1
    mask = keep
    print(f"mask {int(mask.sum())} px from {count - 1} components")

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    outline = max(contours, key=cv2.contourArea).reshape(-1, 2) if contours else np.empty((0, 2))
    outline = cv2.approxPolyDP(outline.astype(np.int32).reshape(-1, 1, 2),
                               2.0, True).reshape(-1, 2)

    skeleton = thin(mask)
    polylines, nodes = trace(skeleton)
    print(f"skeleton {int(skeleton.sum())} px -> {len(polylines)} edges, "
          f"{len(nodes)} nodes")

    def to_dish(x, y):
        return [round((float(x) - cx) / r, 5), round((float(y) - cy) / r, 5)]

    # Douglas-Peucker per polyline: a traced run is one point per pixel, which
    # is far more than the renderer needs to draw a smooth tube.
    edges = []
    for line in polylines:
        pts = np.array([[x, y] for y, x in line], np.int32).reshape(-1, 1, 2)
        simple = cv2.approxPolyDP(pts, 1.5, False).reshape(-1, 2)
        edges.append([to_dish(x, y) for x, y in simple])

    payload = {
        "source": source.split('/')[-1],
        "dish": {"cx": cx, "cy": cy, "r": r},
        "outline": [to_dish(x, y) for x, y in outline],
        "edges": edges,
        "nodes": [to_dish(x, y) for y, x in nodes],
    }
    with open(target, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle)
    print(f"wrote {target}: {len(payload['outline'])} outline points, "
          f"{sum(len(e) for e in edges)} edge points")


if __name__ == '__main__':
    main()
