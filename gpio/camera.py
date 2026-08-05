"""Camera: picamera2 stills, taken inside the matrix blank/flash sequence.

picamera2 is the only option on a Pi 5 -- the legacy picamera stack does not
work on this hardware at all. Which NoIR module is fitted only changes the
sensor name and its native resolution, so nothing here is hardcoded to a
module version: the sensor is read off the hardware at startup and the largest
still mode it offers is used unless config pins a resolution.

Capture sequence, from the build notes: blue off, red on, expose, red off,
blue restored. The camera is NoIR and sees red fine, so all 256 pixels flashed
red backlight the agar and the plasmodium reads as a dark silhouette. The blue
stimulus must be blanked or a lit zone blows out the frame; the 100ms gap is
imperceptible to an organism responding over minutes.

The matrix is optional. With no matrix the capture still works, it just has no
backlight and no blanking -- useful for focusing and framing.

    python3 gpio/camera.py info        # what camera is attached, if any
    sudo python3 gpio/camera.py shot   # one capture through the flash sequence
"""

import io
import os
import pathlib
import sys
import threading
import time
from datetime import datetime

# Capture filenames are what api/app.py parses back into timestamps, so this
# format is load-bearing on both sides. Millisecond precision because the
# timelapse can capture faster than once a second during testing.
FILENAME_FORMAT = "slime_%Y%m%d_%H%M%S.jpg"


class CameraUnavailable(Exception):
    """No CSI camera could be opened."""


class Camera:
    """A picamera2 still camera, optionally synchronised with the matrix."""

    def __init__(self, config, matrix=None):
        self.matrix = matrix
        self.image_dir = config.IMAGE_DIR
        self.warmup = getattr(config, 'CAMERA_WARMUP_TIME', 2)
        self._lock = threading.Lock()
        self._picam = None
        self.model = None

        os.makedirs(self.image_dir, exist_ok=True)

        try:
            from picamera2 import Picamera2
        except ImportError as exc:
            raise CameraUnavailable(f"picamera2 not installed: {exc}") from exc

        cameras = Picamera2.global_camera_info()
        if not cameras:
            raise CameraUnavailable("no CSI camera detected")

        self.model = cameras[0].get('Model', 'unknown')
        try:
            self._picam = Picamera2()
        except Exception as exc:
            raise CameraUnavailable(f"could not open camera: {exc}") from exc

        resolution = getattr(config, 'CAMERA_RESOLUTION', None)
        if resolution:
            still_config = self._picam.create_still_configuration(
                main={"size": tuple(resolution)}
            )
        else:
            # Largest mode the fitted sensor actually offers, rather than a
            # size guessed from a module version that may not be what is here.
            still_config = self._picam.create_still_configuration()

        self._picam.configure(still_config)
        self._picam.start()
        self._set_focus(config)
        # The sensor needs a moment for AE and AWB to settle before the first
        # frame is worth keeping.
        time.sleep(self.warmup)

        size = self._picam.camera_configuration()['main']['size']
        print(f"✓ camera {self.model} at {size[0]}x{size[1]}")

    def _set_focus(self, config):
        """Lock focus if the fitted module has an autofocus lens.

        The Camera Module 3 (IMX708) does. The dish sits at a fixed distance
        under a fixed lid, so continuous AF has nothing to track and will hunt
        between frames -- which in a timelapse shows up as the whole arena
        breathing in and out of focus. Fixed lens modules (v1, v2, HQ) have no
        AfMode control at all, hence the capability check rather than a
        module-version test.
        """
        if "AfMode" not in self._picam.camera_controls:
            print("· fixed-focus lens, nothing to lock")
            return

        from libcamera import controls

        dioptres = getattr(config, 'CAMERA_FOCUS_DIOPTRES', None)
        if dioptres is None:
            # One autofocus sweep, then hold wherever it landed.
            self._picam.set_controls({"AfMode": controls.AfModeEnum.Auto})
            self._picam.autofocus_cycle()
            self._picam.set_controls({"AfMode": controls.AfModeEnum.Manual})
            print("· autofocus swept once and locked")
        else:
            self._picam.set_controls({
                "AfMode": controls.AfModeEnum.Manual,
                "LensPosition": dioptres,
            })
            print(f"· focus fixed at {dioptres} dioptres ({1 / dioptres:.2f}m)"
                  if dioptres else "· focus fixed at infinity")

    @property
    def available(self):
        return self._picam is not None

    def capture(self, filename=None):
        """Capture one still through the flash sequence. Returns the path."""
        if not self.available:
            raise CameraUnavailable("camera not initialised")

        filename = filename or datetime.now().strftime(FILENAME_FORMAT)
        path = os.path.join(self.image_dir, filename)

        with self._lock:
            if self.matrix is not None:
                # capture_flash restores the blue stimulus even if the exposure
                # raises, so a failed capture cannot leave the panel dark.
                self.matrix.capture_flash(lambda: self._picam.capture_file(path))
            else:
                self._picam.capture_file(path)

        return path

    def stream_frame(self):
        """One JPEG frame as bytes, for the MJPEG preview.

        Shares the capture lock with `capture`, so a preview frame can never
        land in the middle of the blank/flash sequence and a timelapse frame
        is never delayed behind a half-finished preview frame. Deliberately
        low rate -- this is a framing and focus aid, not the science data.
        """
        if not self.available:
            raise CameraUnavailable("camera not initialised")

        buffer = io.BytesIO()
        with self._lock:
            self._picam.capture_file(buffer, format='jpeg')
        return buffer.getvalue()

    def close(self):
        if self._picam is not None:
            self._picam.stop()
            self._picam.close()
            self._picam = None


class Timelapse:
    """Background thread capturing at a fixed interval."""

    def __init__(self, camera, interval):
        self.camera = camera
        self.interval = interval
        self.last_path = None
        self.last_error = None
        self.count = 0
        self._stop = threading.Event()
        self._thread = None

    def _run(self):
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                self.last_path = self.camera.capture()
                self.last_error = None
                self.count += 1
            except Exception as exc:
                self.last_error = str(exc)
                print(f"timelapse capture failed: {exc}")
            self._stop.wait(max(0.0, self.interval - (time.monotonic() - started)))

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def stop(self):
        self._stop.set()

    def status(self):
        return {
            "running": self._thread is not None and not self._stop.is_set(),
            "interval": self.interval,
            "count": self.count,
            "last_path": self.last_path,
            "last_error": self.last_error,
        }


def open_camera(config, matrix=None):
    """Camera or None. Never raises -- the API must start without a camera."""
    try:
        return Camera(config, matrix=matrix)
    except CameraUnavailable as exc:
        print(f"· camera unavailable: {exc}")
        return None


def main():
    # Config lives beside this module's parent, so the deployed copy at
    # /var/www/sllm finds its own config rather than the checkout's.
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'api'))
    import config

    mode = sys.argv[1] if len(sys.argv) > 1 else "info"

    if mode == "info":
        try:
            from picamera2 import Picamera2
        except ImportError as exc:
            print(f"picamera2 not installed: {exc}")
            return 1
        cameras = Picamera2.global_camera_info()
        if not cameras:
            print("no CSI camera detected")
            print("  ribbon seated both ends, contacts toward the board?")
            print("  check with: rpicam-hello --list-cameras")
            return 1
        for index, cam in enumerate(cameras):
            print(f"camera {index}: {cam}")
        return 0

    if mode == "shot":
        matrix = None
        try:
            import leds

            matrix = leds.Matrix()
            print("matrix ready, capture will use the blank/flash sequence")
        except Exception as exc:
            print(f"· no matrix ({exc}); capturing without backlight")

        camera = open_camera(config, matrix=matrix)
        if camera is None:
            return 1
        try:
            print(f"captured {camera.capture()}")
        finally:
            camera.close()
            if matrix is not None:
                matrix.off()
        return 0

    print(f"usage: python3 {sys.argv[0]} [info|shot]")
    return 1


if __name__ == "__main__":
    sys.exit(main())
