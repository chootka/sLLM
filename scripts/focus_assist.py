"""Live sharpness meter -- focus by moving the camera, not the lens.

The Module 3 focus motor is commanded correctly but does not move the glass
(see the 2026-08-20 measurements). A lens stuck at one fixed focus still takes
a sharp picture -- of whatever happens to sit at that distance. So the working
adjustment is mechanical: change the camera-to-dish distance until the image
comes good, and use this to see when it does.

Prints a sharpness number and a bar about twice a second, with a running best,
so you can move the camera and watch for the peak without needing to judge
blur by eye on a small preview.

Sharpness is the 99.9th percentile of gradient magnitude over the whole frame:
the sharpest edges present, wherever they are. Not a centre crop -- the middle
of this scene is flat agar and carries no detail to measure.

Exposure is left on auto here, unlike the timelapse. This runs under whatever
light is in the chamber, not the imaging flash, and a fixed 60ms would clip.

Needs sllm-api stopped -- it holds the camera.

    sudo ./scripts/py scripts/focus_assist.py
"""

import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'api'))
sys.path.insert(0, str(ROOT / 'gpio'))

import syspath  # noqa: F401  (puts the system libcamera bindings on the path)
import numpy as np

BAR_FULL = 60.0   # sharpness that fills the bar; rescales if beaten


def sharpness(frame):
    g = frame[:, :, 1].astype(np.float64)
    gy, gx = np.gradient(g)
    return float(np.percentile(np.sqrt(gx ** 2 + gy ** 2), 99.9))


def main():
    from picamera2 import Picamera2

    picam = Picamera2()
    picam.configure(picam.create_still_configuration(main={"size": (1152, 648)}))
    picam.start()
    time.sleep(1.5)

    print("\n  Move the camera up or down. Watch for the number to PEAK.")
    print("  ctrl-c when you have it.\n")

    best, best_at, scale = 0.0, None, BAR_FULL
    try:
        while True:
            s = sharpness(picam.capture_array("main"))
            if s > best:
                best, best_at = s, time.strftime("%H:%M:%S")
            scale = max(scale, best)
            bar = "#" * int(min(s / scale, 1.0) * 50)
            flag = "  <-- BEST" if s >= best else ""
            print(f"  {s:7.2f} |{bar:<50}|  best {best:7.2f} @ {best_at}{flag}", flush=True)
            time.sleep(0.4)
    except KeyboardInterrupt:
        print(f"\n  best sharpness seen: {best:.2f}")
        print("  for reference, every lens position measured 11-12 while blurred\n")
    finally:
        picam.stop()
        picam.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
