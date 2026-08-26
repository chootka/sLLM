"""Live sharpness meter that reads the API's own preview stream.

The point of this one is that it needs no exclusive access to the camera. It
consumes /api/stream over HTTP exactly like the browser does, so the preview
keeps working in the browser while this prints a number beside it -- you get
the picture and the measurement at the same time, and the timelapse keeps
running throughout.

That matters because focusing by eye on a live preview is hard to call: the
difference between nearly-sharp and sharp is not obvious on screen, and the
number is not.

Sharpness is the 99.9th percentile of gradient magnitude over the frame -- the
sharpest edges present, wherever they are. Not a centre crop; the middle of
this scene is flat agar with no detail to measure.

    ./scripts/py scripts/focus_meter.py
    ./scripts/py scripts/focus_meter.py http://otherhost:5000/api/stream
"""

import io
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'gpio'))

import syspath  # noqa: F401
import numpy as np
from PIL import Image

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000/api/stream"


def frames(url):
    """Yield JPEG payloads from a multipart/x-mixed-replace stream."""
    stream = urllib.request.urlopen(url, timeout=15)
    buf = b""
    while True:
        chunk = stream.read(8192)
        if not chunk:
            return
        buf += chunk
        # JPEG SOI..EOI, rather than trusting the boundary marker or a
        # Content-Length the server does not always send.
        start = buf.find(b"\xff\xd8")
        end = buf.find(b"\xff\xd9", start + 2)
        if start != -1 and end != -1:
            yield buf[start:end + 2]
            buf = buf[end + 2:]


def sharpness(jpeg):
    a = np.array(Image.open(io.BytesIO(jpeg)).convert('L')).astype(np.float64)
    gy, gx = np.gradient(a)
    return float(np.percentile(np.sqrt(gx ** 2 + gy ** 2), 99.9))


def main():
    print(f"\n  reading {URL}")
    print("  Move the camera. Watch for the number to PEAK. ctrl-c when done.\n")
    best, scale = 0.0, 20.0
    try:
        for jpeg in frames(URL):
            s = sharpness(jpeg)
            best = max(best, s)
            scale = max(scale, best)
            bar = "#" * int(min(s / scale, 1.0) * 50)
            flag = "  <-- BEST" if s >= best else ""
            print(f"  {s:7.2f} |{bar:<50}|  best {best:7.2f}{flag}", flush=True)
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        print(f"\n  stream ended: {exc}")
        print("  is sllm-api running?  systemctl is-active sllm-api")
        return 1
    print(f"\n  best sharpness seen: {best:.2f}")
    print("  blurred baseline measured 2026-08-20 was 10-12\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
