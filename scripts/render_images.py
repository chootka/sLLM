#!/usr/bin/env python3
"""Render the captured frames: false-colour stills, or growth as one image.

Frames are IR-lit, so they are not grey -- IR passes the sensor's red filter far
more than its blue, and a typical frame reads around R 58 / G 52 / B 6. That
channel separation is real signal, so colour here is a remap of what was
recorded rather than anything invented.

Exposure drifts a lot across the record (median luminance by day has run 17 to
180), so every mode normalises per frame before doing anything else. All-black
and zero-byte frames are skipped.

    ./scripts/py scripts/render_images.py colour --day 20260827
    ./scripts/py scripts/render_images.py colour --last 200 --out /tmp/frames
    ./scripts/py scripts/render_images.py trails --since 20260814 --scale 0.5

Modes:
  colour   one output frame per input frame, false-coloured on the organism's
           own yellow. Feed the result to ffmpeg for a timelapse.
  trails   the whole range collapsed into a single image, hue = when. Shows
           where the organism has been over days rather than what it looks
           like now.
"""

import argparse
import glob
import os
import sys

import numpy as np
from PIL import Image

SRC = '/var/www/sllm/data/images'

# Anchored on Physarum's actual colour rather than a generic heat map: near
# black through dark amber to the bright yellow the organism really is.
STOPS = [
    (0.00, (10, 7, 5)),
    (0.35, (74, 47, 8)),
    (0.65, (200, 144, 26)),
    (1.00, (255, 233, 138)),
]


def ramp(n=256):
    xs = np.linspace(0, 1, n)
    out = np.zeros((n, 3))
    for i in range(len(STOPS) - 1):
        a, ca = STOPS[i]
        b, cb = STOPS[i + 1]
        m = (xs >= a) & (xs <= b)
        t = ((xs[m] - a) / (b - a))[:, None]
        out[m] = np.array(ca) * (1 - t) + np.array(cb) * t
    return out


LUT = ramp()


def frames(day=None, since=None, last=None, step=1):
    fs = sorted(glob.glob(os.path.join(SRC, 'slime_*.jpg')))
    if day:
        fs = [f for f in fs if os.path.basename(f)[6:14] == day]
    if since:
        fs = [f for f in fs if os.path.basename(f)[6:14] >= since]
    if last:
        fs = fs[-last:]
    return fs[::step]


def load(path, scale=1.0, size=None):
    """Normalised luminance in 0..1, or None if the frame carries nothing.

    `size` forces (w, h). The archive changes resolution partway through --
    2304x1296 and 1920x1080 both appear -- so anything combining frames has to
    pin one shape.
    """
    try:
        if os.path.getsize(path) == 0:
            return None
        im = Image.open(path)
        if size is not None:
            im = im.resize(size, Image.BILINEAR)
        elif scale != 1.0:
            im = im.resize((int(im.width * scale), int(im.height * scale)), Image.BILINEAR)
        a = np.asarray(im.convert('RGB')).astype(np.float32)
    except Exception:
        return None
    lum = a @ np.array([0.5, 0.4, 0.1], dtype=np.float32)   # IR-weighted, not Rec.709
    if lum.max() <= 0:
        return None                                          # all-black capture
    lo, hi = np.percentile(lum, 1), np.percentile(lum, 99.5)
    if hi - lo < 1:
        return None
    return np.clip((lum - lo) / (hi - lo), 0, 1)


def colour_mode(args):
    fs = frames(args.day, args.since, args.last, args.step)
    os.makedirs(args.out, exist_ok=True)
    kept = skipped = 0
    for f in fs:
        v = load(f, args.scale)
        if v is None:
            skipped += 1
            continue
        rgb = LUT[(v * 255).astype(np.uint8)].astype(np.uint8)
        Image.fromarray(rgb).save(os.path.join(args.out, os.path.basename(f)), quality=92)
        kept += 1
    print(f"  {kept} written to {args.out}, {skipped} skipped (black or unreadable)")
    if kept:
        print(f"  ffmpeg -framerate 24 -pattern_type glob -i '{args.out}/*.jpg' "
              f"-c:v libx264 -pix_fmt yuv420p timelapse.mp4")


def trails_mode(args):
    fs = frames(args.day, args.since, args.last, args.step)
    acc = None
    age = None
    size = None
    used = 0
    for i, f in enumerate(fs):
        v = load(f, args.scale, size)
        if v is None:
            continue
        if acc is None:
            acc = np.zeros_like(v)
            age = np.zeros_like(v)
            size = (v.shape[1], v.shape[0])   # pin every later frame to this
        # Brightest-wins, carrying when it happened. A later frame only
        # overwrites where the organism is actually brighter than anything
        # before it, so the map reads as "first arrival", not "last frame".
        hit = v > acc
        acc[hit] = v[hit]
        age[hit] = i / max(1, len(fs) - 1)
        used += 1
    if acc is None:
        print("  no usable frames")
        return
    # Hue carries time, value carries how strongly the organism was ever there.
    import colorsys
    h = (0.14 + 0.72 * age) % 1.0            # yellow -> green -> blue -> magenta
    s = np.clip(0.35 + 0.5 * acc, 0, 1)
    val = np.clip(acc ** 0.75, 0, 1)
    flat = np.stack([h.ravel(), s.ravel(), val.ravel()], axis=1)
    rgb = np.array([colorsys.hsv_to_rgb(*p) for p in flat]).reshape(*acc.shape, 3)
    Image.fromarray((rgb * 255).astype(np.uint8)).save(args.out)
    print(f"  {used} frames -> {args.out}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('mode', choices=['colour', 'trails'])
    p.add_argument('--day', help='YYYYMMDD, one day only')
    p.add_argument('--since', help='YYYYMMDD, this day onward')
    p.add_argument('--last', type=int, help='only the newest N frames')
    p.add_argument('--step', type=int, default=1, help='use every Nth frame')
    p.add_argument('--scale', type=float, default=1.0, help='resize factor')
    p.add_argument('--out', help='output dir (colour) or file (trails)')
    args = p.parse_args()
    if not args.out:
        args.out = 'rendered' if args.mode == 'colour' else 'trails.png'
    (colour_mode if args.mode == 'colour' else trails_mode)(args)


if __name__ == '__main__':
    main()
