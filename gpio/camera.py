"""Camera: stills taken inside the matrix blank/flash sequence.

Two backends, because the imaging camera is not fixed hardware:

    csi   picamera2 on the CSI ribbon -- Camera Module 3 and relatives
    usb   any UVC device on /dev/video*, through OpenCV's V4L2 capture

Both offer the API the same three operations -- capture(), stream_frame() and
close() -- so nothing above this module knows or cares which is fitted. Which
one is live is chosen at runtime by CameraManager, so changing camera is a
dropdown in the admin page rather than a config edit and a service restart.

Capture sequence, from the build notes: blue off, red on, expose, red off,
blue restored. All 256 pixels flashed red backlight the agar and the
plasmodium reads as a dark silhouette. The blue stimulus must be blanked or a
lit zone blows out the frame; the 100ms gap is imperceptible to an organism
responding over minutes.

The matrix is optional. With no matrix the capture still works, it just has no
backlight and no blanking -- useful for focusing and framing.

    ./scripts/py gpio/camera.py info        # every source, and which is live
    sudo ./scripts/py gpio/camera.py shot   # one capture through the flash sequence
"""

import io
import json
import os
import pathlib
import sys
import threading
import time
import syspath  # noqa: F401  (path setup, must precede hardware imports)
import leds  # zone geometry and the Matrix type; touches no hardware on import

from datetime import datetime

# Capture filenames are what api/app.py parses back into timestamps, so this
# format is load-bearing on both sides. Millisecond precision because the
# timelapse can capture faster than once a second during testing.
FILENAME_FORMAT = "slime_%Y%m%d_%H%M%S.jpg"

# The CSI ribbon is one slot, so it needs no more identity than this. USB
# cameras are identified by their /dev/v4l/by-id path instead -- see
# list_sources() for why not /dev/videoN.
CSI_SOURCE = 'csi'

BY_ID_DIR = '/dev/v4l/by-id'


class CameraUnavailable(Exception):
    """No camera could be opened on the requested source."""


# --- backends ---------------------------------------------------------------

class _CameraBase:
    """Shared capture plumbing. Backends supply _expose and _frame_bytes."""

    kind = None

    def __init__(self, config, matrix=None):
        self.matrix = matrix
        self.image_dir = config.IMAGE_DIR
        self.source_id = None
        self.model = None
        # Re-entrant so a backend can call its own locked helpers from inside
        # an exposure without deadlocking against itself.
        self._lock = threading.RLock()
        os.makedirs(self.image_dir, exist_ok=True)

    @property
    def available(self):
        raise NotImplementedError

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
                self.matrix.capture_flash(lambda: self._expose(path))
            else:
                self._expose(path)

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

        with self._lock:
            return self._frame_bytes()

    def _expose(self, path):
        raise NotImplementedError

    def _frame_bytes(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError


class CsiCamera(_CameraBase):
    """A picamera2 still camera on the CSI ribbon.

    picamera2 is the only option on a Pi 5 -- the legacy picamera stack does
    not work on this hardware at all. Which module is fitted only changes the
    sensor name and its native resolution, so nothing here is hardcoded to a
    module version: the sensor is read off the hardware at startup and the
    largest still mode it offers is used unless config pins a resolution.
    """

    kind = 'csi'

    def __init__(self, config, matrix=None):
        super().__init__(config, matrix=matrix)
        self.source_id = CSI_SOURCE
        self._picam = None
        self.warmup = getattr(config, 'CAMERA_WARMUP_TIME', 2)

        try:
            from picamera2 import Picamera2
        except ImportError as exc:
            raise CameraUnavailable(f"picamera2 not installed: {exc}") from exc

        if not _csi_cameras():
            raise CameraUnavailable("no CSI camera detected")

        self.model = _csi_cameras()[0].get('Model', 'unknown')
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
        self._set_controls(config)
        # The sensor needs a moment for AE and AWB to settle before the first
        # frame is worth keeping.
        time.sleep(self.warmup)

        size = self._picam.camera_configuration()['main']['size']
        print(f"✓ camera {self.model} at {size[0]}x{size[1]} on CSI")

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

    def _set_controls(self, config):
        """Apply the fixed exposure and tone controls from config.

        Everything here exists because the capture happens inside a 100ms
        flash. Auto exposure meters the blanked panel and then the red comes
        up, so the frame it chose for darkness arrives blown; auto white
        balance chases a monochromatic source and lands somewhere new every
        time. Both have to be pinned or the timelapse is unusable as a series.

        Unknown control names are dropped one at a time rather than failing the
        whole block, because the control set differs between sensors and a
        module swap should cost a warning, not a camera that will not open.
        """
        controls = getattr(config, 'CAMERA_CONTROLS', None)
        if not controls:
            return

        available = self._picam.camera_controls
        wanted, skipped = {}, []
        for name, value in controls.items():
            if name in available:
                wanted[name] = value
            else:
                skipped.append(name)

        if skipped:
            print(f"· sensor has no {', '.join(sorted(skipped))} -- skipped")

        if not wanted:
            return

        try:
            self._picam.set_controls(wanted)
        except Exception as exc:  # noqa: BLE001 -- a bad value must not stop capture
            print(f"· camera controls rejected ({exc}); staying on auto")
            return

        summary = ", ".join(f"{k}={v}" for k, v in sorted(wanted.items()))
        print(f"· controls {summary}")

    @property
    def available(self):
        return self._picam is not None

    def _expose(self, path):
        self._picam.capture_file(path)

    def _frame_bytes(self):
        buffer = io.BytesIO()
        self._picam.capture_file(buffer, format='jpeg')
        return buffer.getvalue()

    def close(self):
        with self._lock:
            if self._picam is not None:
                self._picam.stop()
                self._picam.close()
                self._picam = None


class UsbCamera(_CameraBase):
    """A UVC camera on /dev/video*, driven through OpenCV's V4L2 backend.

    No focus control here on purpose. A USB camera either has a fixed lens or
    hides its focus behind UVC controls that vary per device, so framing and
    focus are set by hand on the camera itself. Everything the API asks for --
    a still through the flash, a preview frame -- works the same either way.
    """

    kind = 'usb'

    def __init__(self, config, device, matrix=None):
        super().__init__(config, matrix=matrix)
        try:
            import cv2
        except ImportError as exc:
            raise CameraUnavailable(f"opencv not installed: {exc}") from exc

        self._cv2 = cv2
        self._cap = None
        self.device = device
        self.source_id = device
        self.model = _device_name(device) or os.path.basename(device)
        self.quality = getattr(config, 'USB_CAMERA_JPEG_QUALITY', 92)
        self.flush_frames = getattr(config, 'USB_CAMERA_FLUSH_FRAMES', 6)

        cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
        if not cap.isOpened():
            raise CameraUnavailable(f"could not open {device}")
        self._cap = cap

        # MJPG rather than the YUYV default. Uncompressed 1080p is around
        # 50MB/s on the wire and the driver quietly drops the frame rate to
        # fit; the frames end up JPEG anyway, since that is what gets written.
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

        resolution = getattr(config, 'USB_CAMERA_RESOLUTION', None)
        if resolution:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(resolution[0]))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(resolution[1]))

        # Shortest queue the driver will accept, so _fresh_frame has less to
        # throw away. Not every driver honours it, which is why the flush
        # below is what actually guarantees a current frame.
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Prove it delivers before reporting success. A UVC node opens whether
        # or not anything is on the other end -- an HDMI capture stick with no
        # source attached opens fine and then hands out nothing -- and finding
        # that out here beats finding it out at the first timelapse frame.
        try:
            self._fresh_frame()
        except CameraUnavailable:
            cap.release()
            self._cap = None
            raise

        size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        print(f"✓ camera {self.model} at {size[0]}x{size[1]} on {device}")

    @property
    def available(self):
        return self._cap is not None

    def _fresh_frame(self, flush=None):
        """A frame that is actually from now, not from the queue.

        V4L2 hands out frames that were captured while nobody was reading, so
        the first read after the red comes up is easily one exposed a moment
        before it -- an unlit frame, which in a timelapse is worse than no
        frame. Grab and discard a few, then keep the next.

        It doubles as exposure settling. A UVC camera runs its own auto
        exposure and needs a few frames to react to the flash, where picamera2
        holds a fixed exposure and does not.
        """
        flush = self.flush_frames if flush is None else flush
        for _ in range(max(0, flush)):
            self._cap.grab()

        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise CameraUnavailable(f"no frame from {self.device}")
        return frame

    def _encode(self, frame):
        ok, encoded = self._cv2.imencode(
            '.jpg', frame, [int(self._cv2.IMWRITE_JPEG_QUALITY), self.quality]
        )
        if not ok:
            raise CameraUnavailable("could not encode frame as JPEG")
        return encoded.tobytes()

    def _expose(self, path):
        data = self._encode(self._fresh_frame())
        with open(path, 'wb') as handle:
            handle.write(data)

    def _frame_bytes(self):
        # A shorter flush than a capture: the preview only needs the queue
        # drained, not an exposure settled, and every frame here is one the
        # timelapse is waiting behind.
        return self._encode(self._fresh_frame(flush=2))

    def close(self):
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None


# --- what is attached -------------------------------------------------------

def _device_name(device):
    """The card name the driver reports, e.g. 'HDMI USB Camera'."""
    try:
        node = os.path.basename(os.path.realpath(device))
        with open(f"/sys/class/video4linux/{node}/name", encoding='utf-8') as handle:
            return handle.read().strip()
    except OSError:
        return None


def _csi_cameras():
    """picamera2's view of the CSI slot, with USB devices filtered back out.

    libcamera enumerates UVC cameras too, through its uvcvideo pipeline
    handler, so the USB camera turns up in global_camera_info() alongside any
    real CSI sensor. Those belong to the usb backend -- OpenCV drives them
    with fewer surprises -- and one camera listed twice under two different
    names is its own kind of wrong.
    """
    try:
        from picamera2 import Picamera2

        cameras = Picamera2.global_camera_info()
    except Exception:  # noqa: BLE001 -- no picamera2, no libcamera, no CSI
        return []

    return [cam for cam in cameras if 'usb@' not in cam.get('Id', '')]


def _usb_cameras():
    """Every UVC capture device, addressed by a path that survives a replug."""
    found = []
    try:
        names = sorted(os.listdir(BY_ID_DIR))
    except OSError:
        return found

    for name in names:
        # A UVC device publishes several nodes and index0 is the capture one;
        # the rest carry metadata streams and hand out no frames at all.
        if not name.endswith('-video-index0'):
            continue
        path = os.path.join(BY_ID_DIR, name)
        found.append({
            'id': path,
            'kind': 'usb',
            'label': _device_name(path) or name,
            'node': os.path.realpath(path),
        })
    return found


def list_sources():
    """Every camera that could be selected right now.

    USB cameras are identified by their /dev/v4l/by-id path rather than
    /dev/videoN. Node numbers are handed out in enumeration order and move
    when something is replugged, so a remembered selection would silently
    start pointing at a different camera.
    """
    sources = [{
        'id': CSI_SOURCE,
        'kind': 'csi',
        'label': cam.get('Model', 'CSI camera'),
        'node': cam.get('Id'),
    } for cam in _csi_cameras()]

    sources.extend(_usb_cameras())
    return sources


# --- which one is live ------------------------------------------------------

def _source_path(config):
    return os.path.join(config.DATA_DIR, 'camera_source.json')


def _remembered_source(config):
    try:
        with open(_source_path(config), encoding='utf-8') as handle:
            return json.load(handle).get('source')
    except (OSError, ValueError):
        return None


def _remember_source(config, source_id):
    """Persist the choice, so a restart does not quietly undo it."""
    path = _source_path(config)
    tmp = path + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as handle:
            json.dump({'source': source_id}, handle, indent=2)
        os.replace(tmp, path)
    except OSError as exc:
        print(f"· could not remember camera source: {exc}")


def _open_source(config, source_id, matrix=None):
    if source_id == CSI_SOURCE:
        return CsiCamera(config, matrix=matrix)
    return UsbCamera(config, source_id, matrix=matrix)


def _choose_source(config):
    """Which source to open at startup.

    Order: whatever the admin page last selected, then CAMERA_SOURCE from
    config, then whatever is attached. The remembered choice outranks config
    because it is the more recent statement of intent -- config is what was
    true when the machine was set up, the admin page is what someone said
    while standing at the bench.
    """
    attached = [source['id'] for source in list_sources()]
    if not attached:
        return None

    for preference in (_remembered_source(config),
                       getattr(config, 'CAMERA_SOURCE', 'auto')):
        if not preference or preference == 'auto':
            continue
        if preference in attached:
            return preference
        print(f"· camera {preference} is not attached, falling back")

    return attached[0]


class CameraManager:
    """Owns whichever camera is live, and swaps it without a restart.

    The API holds one of these for the life of the process, so `camera` stays
    a valid reference across a source change -- including inside the timelapse
    thread, which would otherwise go on capturing from the camera that was
    fitted when it started.
    """

    def __init__(self, config, matrix=None):
        self.config = config
        self.matrix = matrix
        self.last_error = None
        self._camera = None
        self._switch = threading.RLock()

    # The API talks to these four as if they were the camera itself.

    @property
    def available(self):
        camera = self._camera
        return camera is not None and camera.available

    @property
    def model(self):
        camera = self._camera
        return camera.model if camera is not None else None

    def capture(self, filename=None):
        camera = self._camera
        if camera is None:
            raise CameraUnavailable("no camera selected")
        return camera.capture(filename)

    def stream_frame(self):
        camera = self._camera
        if camera is None:
            raise CameraUnavailable("no camera selected")
        return camera.stream_frame()

    @property
    def source_id(self):
        camera = self._camera
        return camera.source_id if camera is not None else None

    @property
    def kind(self):
        camera = self._camera
        return camera.kind if camera is not None else None

    def select(self, source_id, remember=True):
        """Switch to a source. Restores the previous one if the new one fails.

        The old camera is closed before the new one opens: a UVC node cannot
        be held twice, and the CSI sensor is just as exclusive. That means a
        failed switch has already given up the working camera, so it is
        reopened before the error goes back to the caller -- an admin picking
        a camera that turns out to be dead should not lose the one that works.
        """
        with self._switch:
            previous_id = self.source_id
            if self._camera is not None:
                self._camera.close()
                self._camera = None

            try:
                self._camera = _open_source(self.config, source_id, self.matrix)
                self.last_error = None
            except CameraUnavailable as exc:
                self.last_error = str(exc)
                if previous_id is not None and previous_id != source_id:
                    try:
                        self._camera = _open_source(
                            self.config, previous_id, self.matrix)
                        print(f"· stayed on {previous_id}")
                    except CameraUnavailable:
                        pass
                raise

            if remember:
                _remember_source(self.config, source_id)
            return self.status()

    def sources(self):
        """Attached cameras, with the live one flagged."""
        current = self.source_id
        found = list_sources()
        for source in found:
            source['active'] = source['id'] == current
        return found

    def status(self):
        return {
            "available": self.available,
            "source": self.source_id,
            "kind": self.kind,
            "model": self.model,
            "error": self.last_error,
        }

    def close(self):
        with self._switch:
            if self._camera is not None:
                self._camera.close()
                self._camera = None


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
                if self.camera.available:
                    self.last_path = self.camera.capture()
                    self.last_error = None
                    self.count += 1
                else:
                    # No camera selected. Not worth a line every interval: a
                    # source can be chosen from the admin page at any time and
                    # this thread picks it up on the next pass by itself.
                    self.last_error = "no camera selected"
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
    """A CameraManager, always. Never raises -- the API must start regardless.

    A manager comes back even with nothing attached, so a camera plugged in
    later can be selected from the admin page without restarting the service.
    """
    manager = CameraManager(config, matrix=matrix)
    source = _choose_source(config)

    if source is None:
        print("· no camera detected (CSI ribbon and USB both empty)")
        return manager

    try:
        # remember=False: this is what was found, not what anyone chose, and
        # writing it down would let an automatic fallback outrank config for
        # good.
        manager.select(source, remember=False)
    except CameraUnavailable as exc:
        print(f"· camera unavailable: {exc}")

    return manager


def main():
    # Config lives beside this module's parent, so the deployed copy at
    # /var/www/sllm finds its own config rather than the checkout's.
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'api'))
    import config

    mode = sys.argv[1] if len(sys.argv) > 1 else "info"

    if mode == "info":
        sources = list_sources()
        if not sources:
            print("no camera detected")
            print("  CSI: ribbon seated both ends, contacts toward the board?")
            print("       check with: rpicam-hello --list-cameras")
            print("  USB: check with: v4l2-ctl --list-devices")
            return 1

        chosen = _choose_source(config)
        for source in sources:
            mark = "*" if source['id'] == chosen else " "
            print(f"{mark} {source['kind']:4} {source['label']}")
            print(f"       id: {source['id']}")
        print("\n* is what would be opened now "
              f"(remembered: {_remembered_source(config)}, "
              f"config: {getattr(config, 'CAMERA_SOURCE', 'auto')})")
        return 0

    if mode == "shot":
        matrix = None
        try:
            from matrix_client import open_matrix

            matrix, matrix_error = open_matrix()
            if matrix is None:
                print(f"· no matrix ({matrix_error}); capturing without backlight")
            else:
                print("matrix ready, capture will use the blank/flash sequence")
        except Exception as exc:
            print(f"· no matrix ({exc}); capturing without backlight")

        camera = open_camera(config, matrix=matrix)
        if not camera.available:
            return 1
        try:
            print(f"captured {camera.capture()}")
        finally:
            camera.close()
            # Only blank the panel if this process owns it. Through matrixd the
            # panel outlives this command and other clients are using it, so
            # off() here would drop the barrier zone out from under them --
            # and the barrier is what keeps the plasmodium off the reference
            # electrode. The daemon blanks on its own shutdown instead.
            if matrix is not None and isinstance(matrix, leds.Matrix):
                matrix.off()
        return 0

    print(f"usage: python3 {sys.argv[0]} [info|shot]")
    return 1


if __name__ == "__main__":
    sys.exit(main())
