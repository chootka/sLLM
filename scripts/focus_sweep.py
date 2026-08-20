"""Find the lens position that puts the dish in focus, by measurement.

The Module 3 lens is pinned in config (CAMERA_FOCUS_DIOPTRES) because the dish
does not move and continuous AF hunts between frames. When the dish *does*
move -- a taller stand, a different lid -- that pinned number is wrong and the
only honest way to the new one is to sweep the lens and measure sharpness on
the frames themselves.

Sharpness is Tenengrad (mean squared gradient) over a centre crop, computed on
whichever colour channel carries the most signal. Under the red backlight that
is the red channel; the other two are gain-amplified noise and their gradient
is noise energy, not detail.

Two passes: coarse over the lens's whole usable range, then fine around the
coarse peak. The peak of a focus curve is broad, so the coarse pass finds the
neighbourhood and the fine pass finds the number worth writing down.

Frames go to a scratch directory, never to IMAGE_DIR -- a sweep must not leave
thirty junk frames in the middle of a timelapse.

    sudo ./scripts/py scripts/focus_sweep.py
    sudo ./scripts/py scripts/focus_sweep.py --coarse-only
"""

import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'api'))
sys.path.insert(0, str(ROOT / 'gpio'))

import numpy as np

import config
import camera as camera_mod

OUT_DIR = pathlib.Path('/tmp/claude-1000/-home-chootka/'
                       '66e1b49e-d2b6-48c6-b7f0-ca1c5bc3f8d8/scratchpad/focus')

# Fraction of the frame measured. The dish is centred and the chamber walls at
# the edge are at a different distance, so measuring the whole frame would let
# a sharp wall outvote a soft dish.
CROP = 0.5

# Frames to throw away after moving the lens. The VCM takes a few frames to
# settle and a frame caught mid-travel reads as blur at the wrong position.
SETTLE_FRAMES = 2


def sharpness(frame):
    """Tenengrad: mean squared gradient magnitude over the centre crop."""
    h, w = frame.shape[:2]
    ch, cw = int(h * CROP), int(w * CROP)
    y0, x0 = (h - ch) // 2, (w - cw) // 2
    crop = frame[y0:y0 + ch, x0:x0 + cw].astype(np.float64)

    if crop.ndim == 3:
        # Pick the channel with the most signal rather than a luminance mix:
        # under a monochromatic backlight the other channels are amplified
        # noise, and averaging them in dilutes the measurement with it.
        crop = crop[:, :, int(np.argmax(crop.reshape(-1, crop.shape[2]).mean(0)))]

    gy, gx = np.gradient(crop)
    return float((gx ** 2 + gy ** 2).mean())


def grab(picam, matrix, dioptres):
    """Move the lens, let it settle, return one flash-lit frame."""
    from libcamera import controls

    picam.set_controls({"AfMode": controls.AfModeEnum.Manual,
                        "LensPosition": dioptres})
    time.sleep(0.4)
    for _ in range(SETTLE_FRAMES):
        picam.capture_array("main")

    held = {}

    def expose():
        held['frame'] = picam.capture_array("main")

    if matrix is not None:
        matrix.capture_flash(expose)
    else:
        expose()
    return held['frame']


def sweep(picam, matrix, positions, label):
    scores = []
    for pos in positions:
        frame = grab(picam, matrix, pos)
        score = sharpness(frame)
        scores.append((pos, score, frame))
        print(f"  {label} {pos:5.2f} D  ({100 / pos if pos else float('inf'):5.1f} cm)"
              f"  sharpness {score:10.1f}")
    return scores


def main():
    coarse_only = '--coarse-only' in sys.argv

    matrix = None
    try:
        from matrix_client import open_matrix
        matrix, matrix_error = open_matrix()
        if matrix is None:
            print(f"· no matrix ({matrix_error}); sweeping without backlight")
        else:
            print("· matrix ready, sweeping with the red flash")
    except Exception as exc:  # noqa: BLE001
        print(f"· no matrix ({exc}); sweeping without backlight")

    cam = camera_mod.CsiCamera(config, matrix=matrix)
    picam = cam._picam

    try:
        if "LensPosition" not in picam.camera_controls:
            print("this sensor has no focus control -- nothing to sweep")
            return 1

        lo, hi, default = picam.camera_controls["LensPosition"]
        print(f"· lens range {lo:.2f} to {hi:.2f} D (default {default:.2f})")
        print(f"· config currently pins "
              f"{getattr(config, 'CAMERA_FOCUS_DIOPTRES', None)} D\n")

        start = max(lo, 2.0)
        coarse_positions = np.arange(start, hi + 0.001, 0.5)
        print("coarse sweep:")
        scores = sweep(picam, matrix, coarse_positions, "coarse")

        best = max(scores, key=lambda s: s[1])
        print(f"\ncoarse peak: {best[0]:.2f} D\n")

        if not coarse_only:
            fine_positions = np.arange(max(lo, best[0] - 0.6),
                                       min(hi, best[0] + 0.6) + 0.001, 0.1)
            print("fine sweep:")
            scores += sweep(picam, matrix, fine_positions, "fine  ")
            best = max(scores, key=lambda s: s[1])

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        from PIL import Image
        for pos, score, frame in sorted(scores, key=lambda s: -s[1])[:3]:
            path = OUT_DIR / f"focus_{pos:0.2f}D.jpg"
            Image.fromarray(frame).save(path, quality=88)
            print(f"· wrote {path}")

        worst = min(s[1] for s in scores)
        print(f"\nbest focus: {best[0]:.2f} dioptres "
              f"({100 / best[0]:.1f} cm), "
              f"{best[1] / worst:.1f}x the sharpness of the worst position")
        print(f"\nset in api/config.py:  CAMERA_FOCUS_DIOPTRES = {best[0]:.2f}")
        return 0
    finally:
        cam.close()


if __name__ == "__main__":
    sys.exit(main())
