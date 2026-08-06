#!/usr/bin/env python3
"""sLLM API: electrode readings, chamber environment, camera, matrix stimulus.

This is the web layer only. Every piece of hardware lives in gpio/ and is
driven through a module there:

    gpio/bus.py      shared I2C bus, and the gate that keeps ADC conversions
                     away from switching events
    gpio/adc.py      ADS1115, three electrodes differential against reference
    gpio/sensor.py   SHT31 temperature and humidity, and the fan relay
    gpio/camera.py   picamera2 stills through the matrix blank/flash sequence
    gpio/leds.py     WS2812B matrix, blue stimulus by zone and red imaging light

Nothing here fabricates data. If a device is absent its readings are null and
`available` is false, and the frontend shows dashes. The previous version
generated plausible temperature and humidity whenever the sensor was missing,
which put invented numbers on the dashboard for a chamber nobody was measuring.

Removed, for the record, because none of it corresponded to hardware that is
on this machine: the Arduino serial reader (electrodes are on the ADS1115 now),
the OpenCV USB camera path (the camera is CSI), the DHT22/DHT11 fallback (the
sensor is an SHT31), and the mock environment generator.
"""

import glob
import json
import os
import re
import sys
import threading
import time
from collections import deque
from datetime import datetime

# board, picamera2 and RPi.GPIO are apt-installed system packages that pip
# cannot provide, so the venv needs the system paths too. Both of them:
# apt puts packages in /usr/lib/python3/dist-packages, while a root-level
# `pip install` puts them in /usr/local/lib/pythonX.Y/dist-packages -- which is
# where rpi_ws281x, the matrix's C extension, actually lives.
#
# Appended, not prepended. Prepending puts system packages ahead of the venv
# for *everything*, which is how a system numpy ends up shadowing the venv's.
# Appending means the venv still wins and only genuinely-missing modules fall
# through to the system.
for _system_path in (
    '/usr/lib/python3/dist-packages',
    f'/usr/local/lib/python{sys.version_info.major}.{sys.version_info.minor}/dist-packages',
):
    if _system_path not in sys.path:
        sys.path.append(_system_path)

from flask import Flask, Response, jsonify, request, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit

try:
    import config
except ImportError:
    print("config.py not found. Copy config_template.py to config.py.")
    import config_template as config

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'gpio'))

from adc import ElectrodeMonitor
from bus import SwitchGate
from camera import Timelapse, open_camera
from sensor import EnvironmentMonitor
from store import electrode_log, environment_log

app = Flask(__name__)

# The public read-only surface stays open to any origin: the dashboard is meant
# to be embeddable and none of it is secret. The admin routes are not, and are
# pinned to the site's own origin. Bearer tokens already make CSRF structurally
# impossible, so this is defence in depth rather than the only control -- but a
# wide-open preflight on a route that starts and stops the experiment is not
# something to leave lying around.
CORS(app, resources={
    r"/api/admin/*": {"origins": [getattr(config, 'ADMIN_ORIGIN',
                                          'https://sllm.visceral.systems')]},
    r"/*": {"origins": "*"},
})
socketio = SocketIO(app, cors_allowed_origins="*")

for directory in (config.IMAGE_DIR, config.LOG_DIR, config.CSV_DIR):
    os.makedirs(directory, exist_ok=True)

# One gate shared by every subsystem that either switches or samples, so the
# ADC is genuinely quiet during switching rather than merely quiet during its
# own module's switching.
gate = SwitchGate(getattr(config, 'ADC_SWITCH_SETTLE', 0.25))

# Both monitors write every sample to a daily CSV under data/readings. The
# rolling buffers are for the API; these files are the record of the run.
electrodes = ElectrodeMonitor(config, gate=gate, log=electrode_log(config))
environment = EnvironmentMonitor(config, gate=gate, log=environment_log(config))


def open_matrix():
    """The LED matrix via the root-owned daemon, or None.

    neopixel drives the WS2812 chain through /dev/mem and needs root. This
    service is a Flask app reachable from the internet through nginx and must
    not be root, so it does not open the panel itself -- gpio/matrixd.py does,
    and this talks to it over a unix socket. `allow_direct=False` because the
    fallback of driving the panel in-process is exactly what we are refusing:
    it would fail here anyway, and if it ever succeeded that would mean the API
    had been given privileges it should not have.

    None means captures happen without the red backlight, as before.
    """
    try:
        from matrix_client import open_matrix as _open

        matrix, error = _open(allow_direct=False)
        if matrix is None:
            print(f"· matrix unavailable ({error}); captures will have no backlight")
            return None
        print("✓ matrix ready via matrixd")
        return matrix
    except Exception as exc:
        print(f"· matrix unavailable ({exc}); captures will have no backlight")
        return None


def register_admin():
    """Admin controls, or a clear reason why not.

    Kept non-fatal on purpose: a missing webauthn install or a malformed
    credential file must not take the dashboard and the sampling loop down with
    it. The routes then return 503 and everything else carries on.
    """
    try:
        import admin as admin_module

        admin_module.register(app, config)
    except Exception as exc:
        print(f"· admin controls unavailable ({exc})")


register_admin()

matrix = open_matrix()
camera = open_camera(config, matrix=matrix)
timelapse = None

_stimulus_timer = None
_stimulus_lock = threading.Lock()

# Capture filenames are slime_YYYYMMDD_HHMMSS.jpg, or slime_YYYYMMDD_HHMMSS_mmm.jpg
# for captures written with millisecond precision.
IMAGE_FILENAME_RE = re.compile(r'^slime_(\d{8})_(\d{6})(?:_(\d{1,3}))?\.jpg$')


def parse_image_filename(filename):
    """Extract the capture time from an image filename, or None if it doesn't match"""
    match = IMAGE_FILENAME_RE.match(filename)
    if not match:
        return None

    date_part, time_part, ms_part = match.groups()
    try:
        captured_at = datetime.strptime(f"{date_part}_{time_part}", "%Y%m%d_%H%M%S")
    except ValueError:
        return None

    if ms_part:
        captured_at = captured_at.replace(microsecond=int(ms_part.ljust(3, '0')) * 1000)
    return captured_at


# --- readings ---------------------------------------------------------------

@app.route('/')
def serve_frontend():
    return send_file('../frontend/index.html')


@app.route('/api/readings', methods=['GET'])
def get_readings():
    """Latest electrode sample, millivolts, per differential channel"""
    return jsonify(electrodes.snapshot())


@app.route('/api/readings/history', methods=['GET'])
def get_readings_history():
    """Recent electrode samples from the rolling buffer"""
    limit = request.args.get('limit', 100, type=int)
    return jsonify(electrodes.history(limit))


@app.route('/api/environment', methods=['GET'])
def get_environment():
    """Latest chamber temperature and humidity"""
    return jsonify(environment.snapshot())


@app.route('/api/config', methods=['GET'])
def get_config():
    """Configuration the frontend needs"""
    return jsonify({
        "image_capture_interval": config.IMAGE_CAPTURE_INTERVAL,
        "chart_update_rate": config.CHART_UPDATE_RATE,
        "status_check_interval": config.STATUS_CHECK_INTERVAL,
        "websockets_enabled": config.ENABLE_WEBSOCKETS,
        "server_port": config.SERVER_PORT,
        "adc_sample_rate": getattr(config, 'ADC_SAMPLE_RATE', 1.0),
        "max_stimulus_duration": getattr(config, 'MAX_STIMULUS_DURATION', 300),
    })


@app.route('/api/status', methods=['GET'])
def get_status():
    """System status and what hardware is actually present"""
    env = environment.snapshot()

    # Public on purpose. Anyone looking at the dashboard should be able to see
    # that what they are watching is a demo rather than the organism -- and
    # more importantly, so should anyone who later finds a screenshot of it.
    try:
        import run as run_state

        active_run = run_state.current(config)
        run_info = {"id": active_run["id"], "mode": active_run["mode"]}
    except Exception:
        run_info = None

    return jsonify({
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "run": run_info,
        "readings_count": len(electrodes.buffer),
        "exposure_light": "on" if _stimulus_active() else "off",
        "sensors": {
            "electrical": electrodes.adc is not None,
            "temperature_humidity": environment.sensor is not None,
            "camera": camera is not None and camera.available,
            "matrix": matrix is not None,
            "fan": environment.fan is not None,
        },
        "environment": env if env["available"] else None,
        "camera_model": camera.model if camera is not None else None,
        "timelapse": timelapse.status() if timelapse is not None else None,
    })


# --- images -----------------------------------------------------------------

@app.route('/api/images', methods=['GET'])
# nginx's /api/images/ proxy_pass location 301-redirects /api/images to
# /api/images/, so the trailing-slash form has to be served here too
@app.route('/api/images/', methods=['GET'])
def list_images():
    """List captured images, newest first, paginated.

    Query params:
      page     - 1-indexed page number (default 1)
      per_page - images per page, 1-500 (default 100)
      date     - restrict to a single capture day, as YYYYMMDD
      order    - 'desc' for newest first (default), or 'asc'
    """
    try:
        try:
            page = max(1, int(request.args.get('page', 1)))
            per_page = min(500, max(1, int(request.args.get('per_page', 100))))
        except (TypeError, ValueError):
            return jsonify({"error": "page and per_page must be integers"}), 400

        date_filter = request.args.get('date')
        if date_filter is not None and not re.fullmatch(r'\d{8}', date_filter):
            return jsonify({"error": "date must be in YYYYMMDD format"}), 400

        order = request.args.get('order', 'desc').lower()
        if order not in ('asc', 'desc'):
            return jsonify({"error": "order must be 'asc' or 'desc'"}), 400

        entries = []
        with os.scandir(config.IMAGE_DIR) as scan:
            for entry in scan:
                if not entry.is_file():
                    continue
                captured_at = parse_image_filename(entry.name)
                if captured_at is None:
                    continue
                if date_filter and captured_at.strftime('%Y%m%d') != date_filter:
                    continue
                entries.append((entry.name, captured_at, entry.stat().st_size))

        # Filenames lead with the timestamp, so sorting by name sorts chronologically
        entries.sort(key=lambda entry: entry[0], reverse=(order == 'desc'))

        total = len(entries)
        start = (page - 1) * per_page
        page_entries = entries[start:start + per_page]

        return jsonify({
            "images": [
                {
                    "filename": name,
                    "url": f"/api/images/{name}",
                    "datetime": captured_at.isoformat(),
                    "timestamp": captured_at.timestamp(),
                    "size": size
                }
                for name, captured_at, size in page_entries
            ],
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
            "order": order,
            "date": date_filter
        })
    except FileNotFoundError:
        print(f"Image directory not found: {config.IMAGE_DIR}")
        return jsonify({"error": "Image directory not found"}), 500
    except Exception as e:
        print(f"Error listing images: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/images/<filename>', methods=['GET'])
def get_image(filename):
    """Serve one captured image"""
    # Only jpgs out of IMAGE_DIR, and no path separators, so a crafted
    # filename cannot walk out of the directory.
    if not filename.endswith('.jpg'):
        return jsonify({"error": "Invalid file type"}), 400
    if '/' in filename or '..' in filename:
        return jsonify({"error": "Invalid filename"}), 400

    filepath = os.path.join(config.IMAGE_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "Image not found"}), 404

    response = send_file(filepath, mimetype='image/jpeg')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@app.route('/api/capture-image', methods=['POST'])
def capture_image():
    """Capture one still through the matrix blank/flash sequence"""
    if camera is None or not camera.available:
        return jsonify({"error": "No camera attached"}), 503

    try:
        path = camera.capture()
    except Exception as exc:
        print(f"capture failed: {exc}")
        return jsonify({"error": str(exc)}), 500

    filename = os.path.basename(path)
    socketio.emit('image_captured', {"filename": filename, "timestamp": time.time()})
    return jsonify({
        "success": True,
        "filename": filename,
        "url": f"/api/images/{filename}"
    })


def generate_stream():
    """MJPEG frames from the CSI camera, at a deliberately modest rate."""
    fps = getattr(config, 'STREAM_FPS', 2)
    interval = 1.0 / max(fps, 0.1)
    while camera is not None and camera.available:
        started = time.monotonic()
        try:
            frame = camera.stream_frame()
        except Exception as exc:
            print(f"stream frame failed: {exc}")
            return
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(max(0.0, interval - (time.monotonic() - started)))


@app.route('/api/turns', methods=['GET'])
def get_turns():
    """The model's turn records, newest last, for the /logs page.

    **`sham` and `applied` are withheld unless the caller is an authenticated
    admin.** This is not tidiness, it is the experiment's integrity. The design
    depends on the model not knowing which turns are sham blocks, and this page
    is publicly reachable. A public list of which turns were shams is a channel
    straight back into the loop the moment anyone quotes it at the model, or it
    gets scraped into something the model later reads. The reasoning and the
    requested action are shown; whether it was applied is not.

    A caveat that page cannot fix: someone standing in front of the chamber can
    compare a shown action against whether the panel actually lit. Physical
    presence has always been able to see that.
    """
    try:
        limit = min(int(request.args.get('limit', 200)), 1000)
    except ValueError:
        limit = 200
    after = request.args.get('after', '')

    privileged = False
    try:
        import admin as admin_module

        privileged = admin_module.is_authenticated()
    except Exception:
        privileged = False

    paths = sorted(glob.glob(os.path.join(config.LOG_DIR, 'turns_*.jsonl')))
    # Newest files last; read backwards only far enough to satisfy the limit.
    lines = []
    for path in reversed(paths):
        try:
            with open(path) as handle:
                lines = handle.readlines() + lines
        except OSError:
            continue
        if len(lines) >= limit and not after:
            break

    turns = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if after and record.get('datetime', '') <= after:
            continue

        reply = record.get('reply') or {}
        turn = {
            'turn': record.get('turn'),
            'datetime': record.get('datetime'),
            'source': record.get('source'),
            'window_samples': record.get('window_samples'),
            'state': record.get('state'),
            'note': reply.get('note'),
            'resource': reply.get('resource'),
            'action': record.get('action'),
            'action_refused': record.get('action_refused'),
        }
        if privileged:
            turn['sham'] = record.get('sham')
            turn['applied'] = record.get('applied')
        turns.append(turn)

    return jsonify({
        'turns': turns[-limit:],
        'privileged': privileged,
        'loop_running': _loop_running(),
    })


def _loop_running():
    try:
        import admin as admin_module

        active, _ = admin_module.loop_state()
        return active
    except Exception:
        return None


@app.route('/api/stream')
def video_stream():
    """Live preview. A framing aid, not the science data."""
    if camera is None or not camera.available:
        return jsonify({"error": "No camera attached"}), 503
    return Response(generate_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


# --- stimulus ---------------------------------------------------------------

def _stimulus_active():
    return matrix is not None and matrix.stimulus_active()


def _clear_stimulus():
    global _stimulus_timer
    with _stimulus_lock:
        _stimulus_timer = None
        if matrix is not None:
            with gate.switching():
                matrix.clear_stimulus()
    socketio.emit('light_changed', {
        "exposure_light": False,
        "timestamp": time.time()
    })


@app.route('/api/trigger-light', methods=['POST'])
def trigger_light():
    """Drive the blue stimulus.

    Kept at this path because the frontend already calls it. What it switches
    is now a zone of the matrix rather than the old relay-driven exposure lamp,
    which is the hardware that actually exists.

    Body: {"state": "on"|"off"|"toggle", "zone": int, "intensity": float,
           "duration": seconds}
    """
    global _stimulus_timer

    if matrix is None:
        return jsonify({"error": "Matrix not available to this process"}), 503

    data = request.get_json(silent=True) or {}
    state = data.get('state', 'toggle')
    zone = data.get('zone', getattr(config, 'DEFAULT_STIMULUS_ZONE', 4))
    intensity = float(data.get('intensity', 1.0))

    max_duration = getattr(config, 'MAX_STIMULUS_DURATION', 300)
    duration = data.get('duration') or max_duration
    duration = min(float(duration), max_duration)

    if state == 'toggle':
        state = 'off' if _stimulus_active() else 'on'

    try:
        with _stimulus_lock:
            if _stimulus_timer is not None:
                _stimulus_timer.cancel()
                _stimulus_timer = None

            with gate.switching():
                if state == 'on':
                    matrix.clear_stimulus()
                    matrix.set_zone(zone, intensity)
                else:
                    matrix.clear_stimulus()

            if state == 'on':
                # Never leave a zone lit indefinitely on an organism that is
                # photophobic; the model's turns are bounded and so is this.
                _stimulus_timer = threading.Timer(duration, _clear_stimulus)
                _stimulus_timer.daemon = True
                _stimulus_timer.start()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    lit = state == 'on'
    socketio.emit('light_changed', {
        "exposure_light": lit,
        "zone": zone if lit else None,
        "timestamp": time.time()
    })
    return jsonify({
        "status": "success",
        "light_state": "on" if lit else "off",
        "zone": zone if lit else None,
        "auto_off_seconds": duration if lit else None
    })


# --- socket.io --------------------------------------------------------------

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    reading = electrodes.snapshot()
    if reading["timestamp"] > 0:
        emit('reading_update', reading)

    env = environment.snapshot()
    if env["available"]:
        emit('environment_update', env)

    emit('status_update', {
        "exposure_light": _stimulus_active(),
        "timestamp": time.time()
    })


@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")


def emit_realtime_data():
    """Push the latest readings to connected clients."""
    while True:
        try:
            reading = electrodes.snapshot()
            if reading["timestamp"] > 0:
                socketio.emit('reading_update', reading)

            env = environment.snapshot()
            if env["available"]:
                socketio.emit('environment_update', env)

            socketio.emit('status_update', {
                "exposure_light": _stimulus_active(),
                "timestamp": time.time()
            })
        except Exception as exc:
            print(f"Error emitting data: {exc}")

        time.sleep(config.SOCKET_EMIT_INTERVAL)


def main():
    global timelapse

    electrodes.start()
    environment.start()

    if camera is not None and getattr(config, 'TIMELAPSE_ENABLED', True):
        timelapse = Timelapse(camera, config.IMAGE_CAPTURE_INTERVAL).start()
        print(f"✓ timelapse every {config.IMAGE_CAPTURE_INTERVAL}s")

    if config.ENABLE_WEBSOCKETS:
        threading.Thread(target=emit_realtime_data, daemon=True).start()

    try:
        socketio.run(app, host=config.SERVER_HOST, port=config.SERVER_PORT,
                     debug=config.DEBUG_MODE, allow_unsafe_werkzeug=True)
    finally:
        electrodes.stop()
        environment.stop()
        if timelapse is not None:
            timelapse.stop()
        if camera is not None:
            camera.close()
        if matrix is not None:
            # Clear this service's stimulus, but do not blank the panel. The
            # API no longer owns it -- matrixd does, and llm/loop.py may be
            # driving zones through the same daemon. off() would also drop the
            # barrier zone, which must stay lit whenever the organism is in.
            try:
                matrix.clear_stimulus()
            except Exception as exc:  # noqa: BLE001 -- shutdown must not raise
                print(f"could not clear stimulus on shutdown: {exc}")


if __name__ == '__main__':
    main()
