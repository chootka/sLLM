#!/usr/bin/env python3
"""Measure how even the dish illumination is, from a capture.

The IR flood is the only thing lighting the frame, so any gradient in a still
is the flood's gradient. This turns that into numbers, so a change to the
lighting rig can be judged instead of eyeballed.

    ./scripts/py scripts/flatfield.py                    # newest capture
    ./scripts/py scripts/flatfield.py path/to/shot.jpg
    ./scripts/py scripts/flatfield.py --grid 8 --crop 280,0,1560,1296

Run it once before changing the rig and once after, on frames with the same
exposure settings. RATIO and CLIPPED are the two numbers that matter:

    ratio    max cell / min cell. 1.0 is perfect. Under 2 is good enough that
             flat-field correction in software can finish the job.
    clipped  fraction of pixels at 255. Anything above ~0 is detail that no
             amount of post-processing brings back.

Baseline for comparison, single off-axis emitter, 2026-08-19: ratio 24.5,
clipped 4.6%.
"""

import glob
import os
import sys

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is not available in this interpreter. Use ./scripts/py")

# The dish does not fill the 2304x1296 frame -- there is chamber floor either
# side, and including it drags the minimum down and flatters nothing. These
# bounds are the dish's bounding box as framed on 2026-08-19; re-measure if the
# camera or the dish moves.
DEFAULT_CROP = (280, 0, 1560, 1296)
DEFAULT_GRID = 6

# The captures live wherever the *running* installation writes them, which is
# the deployed tree -- a checkout at ~/sllm has an empty data directory and
# always will. Check both, newest wins, so this works from either.
IMAGE_DIRS = (
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "images"
    ),
    "/var/www/sllm/data/images",
)


def newest_capture():
    shots = []
    for directory in IMAGE_DIRS:
        shots.extend(glob.glob(os.path.join(directory, "*.jpg")))
    if not shots:
        sys.exit("no captures in " + " or ".join(IMAGE_DIRS))
    return max(shots, key=os.path.getmtime)


def main():
    args = sys.argv[1:]
    grid, crop, path = DEFAULT_GRID, DEFAULT_CROP, None

    while args:
        arg = args.pop(0)
        if arg == "--grid":
            grid = int(args.pop(0))
        elif arg == "--crop":
            crop = tuple(int(v) for v in args.pop(0).split(","))
            if len(crop) != 4:
                sys.exit("--crop wants left,top,right,bottom")
        elif arg.startswith("-"):
            sys.exit(__doc__)
        else:
            path = arg

    path = path or newest_capture()
    full = Image.open(path).convert("L").crop(crop)

    # Downsampling to the grid averages each cell, so one specular glint off the
    # dish rim cannot masquerade as a lighting hot spot.
    cells = list(full.resize((grid, grid), Image.BOX).getdata())
    lo, hi = min(cells), max(cells)

    # Clipping is counted on the full-resolution crop, not the grid: averaged
    # cells never reach 255 even when a quarter of the dish is blown.
    pixels = list(full.getdata())
    clipped = sum(1 for p in pixels if p >= 255) / len(pixels)

    print(f"{os.path.basename(path)}  crop={crop}  grid={grid}x{grid}")
    print()
    for row in range(grid):
        print("   " + " ".join("%4d" % cells[row * grid + col] for col in range(grid)))
    print()
    print(f"   min {lo}   max {hi}   ratio {hi / max(lo, 1):.1f}   clipped {clipped:.1%}")
    print()

    if clipped > 0.005:
        print("   CLIPPED -- that area has no recoverable detail. Optics first.")
    elif hi / max(lo, 1) > 2.0:
        print("   uneven, but nothing is blown. Flat-field correction can finish it.")
    else:
        print("   even enough.")


if __name__ == "__main__":
    main()
