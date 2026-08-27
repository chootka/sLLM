#!/usr/bin/env python3
"""sLLM API: electrode readings, chamber environment, camera, matrix stimulus.

This is the web layer only. Every piece of hardware lives in gpio/ and is
driven through a module there:

    gpio/bus.py      shared I2C bus, and the gate that keeps ADC conversions
                     away from switching events
    gpio/adc.py      ADS1115, three electrodes differential against reference
    gpio/sensor.py   SHT31 temperature and humidity, and the fan relay
    gpio/camera.py   stills through the matrix blank/flash sequence, from
                     either a CSI camera or a USB one
    gpio/leds.py     WS2812B matrix, blue stimulus by zone and red imaging light

Nothing here fabricates data. If a device is absent its readings are null and
`available` is false, and the frontend shows dashes. The previous version
generated plausible temperature and humidity whenever the sensor was missing,
which put invented numbers on the dashboard for a chamber nobody was measuring.

Removed, for the record, because none of it corresponded to hardware that is
on this machine: the Arduino serial reader (electrodes are on the ADS1115 now),
the DHT22/DHT11 fallback (the sensor is an SHT31), and the mock environment
generator.
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

# board, picamera2 and RPi.GPIO are apt packages pip cannot provide. Both system
# paths are needed: apt uses /usr/lib/python3/dist-packages, root-level pip uses
# /usr/local/lib/pythonX.Y/dist-packages, where rpi_ws281x lives.
#
# Appended, not prepended -- prepending lets a system numpy shadow the venv's.
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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adc import ElectrodeMonitor
from bus import SwitchGate
from camera import CameraUnavailable, Timelapse, open_camera
from sensor import EnvironmentMonitor
from store import electrode_log, environment_log

app = Flask(__name__)

# The public read-only surface stays open to any origin -- the dashboard is
# embeddable and none of it is secret. Admin routes are pinned to the site's
# own origin. Bearer tokens already rule out CSRF; this is defence in depth.
_admin_origin = getattr(config, 'ADMIN_ORIGIN', 'https://sllm.visceral.systems')
CORS(app, resources={
    r"/api/admin/*": {"origins": [_admin_origin]},
    # Choosing the camera is an admin action that happens to live with the
    # rest of the camera code rather than in admin.py, so it is pinned here by
    # path instead of by prefix. Capture and preview stay public, as before.
    r"/api/camera/*": {"origins": [_admin_origin]},
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

# Consecutive frames a preview will wait through while no camera is available
# before giving up. At the default 2fps this is a five second tolerance, which
# covers a source switch and not much else.
STREAM_MISS_LIMIT = 10


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


def _reading_modes(asked=None):
    """Which mode directories to read for a read-back window.

    Readings are partitioned by mode -- 'live' at the top level, everything
    else in a subdirectory of it -- but the record they hold is one continuous
    stream: the sensors log whenever the API is up, and a mode switch only
    changes which folder the next row lands in. Reading a single mode makes the
    other side of a switch look like an outage, which is exactly how it read on
    the dashboard: two days of live-mode data drawn as a hole.
    """
    if asked:
        return [asked]
    modes = ['live']
    try:
        with os.scandir(config.CSV_DIR) as scan:
            modes += sorted(e.name for e in scan if e.is_dir())
    except OSError:
        pass
    return modes


@app.route('/api/readings/range', methods=['GET'])
def get_readings_range():
    """Downsampled electrode history over an arbitrary window.

    The rolling buffer only reaches back MAX_READINGS_BUFFER samples and dies
    with the process. This reads the daily CSVs instead, so the dashboard can
    scroll back through a run that has been going for days.

    A day at 1 Hz is 86400 samples and no browser wants them, so the window is
    bucketed. Each bucket carries min and max as well as mean: a contraction
    spike narrower than one bucket would be averaged out of existence
    otherwise, and the spikes are the signal.
    """
    log = getattr(electrodes, 'log', None)
    if log is None:
        return jsonify({"error": "disk logging is disabled"}), 503

    start = request.args.get('start', type=float)
    end = request.args.get('end', type=float)
    if start is None or end is None:
        return jsonify({"error": "start and end are required, unix seconds"}), 400
    if end <= start:
        return jsonify({"error": "end must be after start"}), 400

    # Capped so a wide window cannot ask the Pi for a point per sample.
    buckets = max(1, min(request.args.get('buckets', 800, type=int), 5000))
    mode = request.args.get('mode') or None
    channels = tuple(getattr(config, 'ADC_CHANNELS', (0, 1, 2)))

    width = (end - start) / buckets
    columns = [f'ch{channel}_mv' for channel in channels]
    # Streamed, not materialised: a month view covers the whole record and
    # building a dict per sample first would cost hundreds of megabytes for a
    # few hundred points of output.
    table = {}
    seen = 0
    for name in _reading_modes(mode):
        part, count = log.aggregate(start, end, buckets, columns, mode=name)
        seen += count
        # Only one mode records at a time, so buckets do not overlap; first
        # writer wins if they ever do.
        for index, stats in part.items():
            table.setdefault(index, stats)

    points = []
    for index in sorted(table):
        entry = {"t": start + (index + 0.5) * width, "channels": {}}
        for channel, column in zip(channels, columns):
            stats = table[index].get(column)
            if stats is None:
                continue
            low, high, total, count = stats
            entry["channels"][str(channel)] = {
                "min": round(low, 4),
                "max": round(high, 4),
                "mean": round(total / count, 4),
            }
        points.append(entry)

    return jsonify({
        "start": start,
        "end": end,
        "buckets": buckets,
        "samples": seen,
        "channels": [str(c) for c in channels],
        "points": points,
    })


# Bounded: the chain is seconds of CPU on a wide window and the dashboard
# re-requests the same span on every theme toggle and tab focus.
_PROCESSED_CACHE = {}
_PROCESSED_CACHE_MAX = 8


@app.route('/api/readings/processed', methods=['GET'])
def get_readings_processed():
    """Slime-attributable signal over a window.

    `signal` is the band-limited trace zeroed wherever the gate is shut, so a
    flat line reads as "no organism" rather than "dead feed" -- pair it with
    `ghost`, the high-passed raw, which is never flat while data is arriving.

    Reads WARMUP seconds before `start`. The high-pass needs run-in and the
    periodogram needs a full window; without the lead-in the first hour of
    every view would show a false gate=0.

    Method, thresholds and validation: documentation/signal_processing.md
    """
    import numpy as np
    from processing.slime import chain, step_for, WARMUP

    log = getattr(electrodes, 'log', None)
    if log is None:
        return jsonify({"error": "disk logging is disabled"}), 503

    start = request.args.get('start', type=float)
    end = request.args.get('end', type=float)
    if start is None or end is None:
        return jsonify({"error": "start and end are required, unix seconds"}), 400
    if end <= start:
        return jsonify({"error": "end must be after start"}), 400

    buckets = max(1, min(request.args.get('buckets', 800, type=int), 5000))
    mode = request.args.get('mode') or None
    channels = tuple(getattr(config, 'ADC_CHANNELS', (0, 1, 2)))

    key = (round(start), round(end), buckets, mode)
    if key in _PROCESSED_CACHE:
        return jsonify(_PROCESSED_CACHE[key])

    rows = []
    for name in _reading_modes(mode):
        rows.extend(log.between(start - WARMUP, end, mode=name))
    if len(rows) < 2:
        return jsonify({"start": start, "end": end, "buckets": buckets,
                        "samples": 0, "channels": [str(c) for c in channels],
                        "warmup": WARMUP, "points": []})
    rows.sort(key=lambda r: float(r["timestamp"]))

    stamps, series = [], {c: [] for c in channels}
    for row in rows:
        try:
            t = float(row["timestamp"])
            values = {c: float(row[f"ch{c}_mv"]) for c in channels}
        except (KeyError, ValueError, TypeError):
            continue
        stamps.append(t)
        for c in channels:
            series[c].append(values[c])
    if len(stamps) < 2:
        return jsonify({"error": "no parseable rows in window"}), 503

    stamps = np.asarray(stamps)
    grid = np.arange(stamps[0], stamps[-1], 1.0)
    step = step_for(end - start, buckets)

    out = {}
    for c in channels:
        x = np.interp(grid, stamps, np.asarray(series[c]))
        out[c] = chain(x, step=step)

    # Drop the lead-in: it exists to make the gate honest at the left edge, not
    # to be drawn.
    keep = (grid >= start) & (grid <= end)
    kept = grid[keep]
    if kept.size == 0:
        return jsonify({"error": "window has no samples"}), 503

    width = (end - start) / buckets
    index = np.clip(((kept - start) / width).astype(int), 0, buckets - 1)

    points = []
    for b in np.unique(index):
        m = index == b
        entry = {"t": float(start + (b + 0.5) * width), "channels": {}}
        for c in channels:
            r = out[c]
            sig = r["signal"][keep][m]
            gho = r["ghost"][keep][m]
            entry["channels"][str(c)] = {
                "signal_min": round(float(sig.min()), 4),
                "signal_max": round(float(sig.max()), 4),
                "signal": round(float(sig.mean()), 4),
                "ghost_min": round(float(gho.min()), 4),
                "ghost_max": round(float(gho.max()), 4),
                "gate": round(float(r["gate"][keep][m].mean()), 3),
                "provisional": round(float(r["provisional"][keep][m].mean()), 3),
                "presence": round(float(r["presence"][keep][m].mean()), 3),
                "activity": round(float(r["activity"][keep][m].mean()), 3),
                "period": round(float(r["period"][keep][m].mean()), 1),
            }
        points.append(entry)

    payload = {
        "start": start,
        "end": end,
        "buckets": buckets,
        "samples": int(keep.sum()),
        "channels": [str(c) for c in channels],
        "warmup": WARMUP,
        "step": step,
        "points": points,
    }
    if len(_PROCESSED_CACHE) >= _PROCESSED_CACHE_MAX:
        _PROCESSED_CACHE.pop(next(iter(_PROCESSED_CACHE)))
    _PROCESSED_CACHE[key] = payload
    return jsonify(payload)

@app.route('/api/phase-lock', methods=['GET'])
def get_phase_lock():
    """Is the applied light arriving at a preferred phase of the rhythm?

    Two systems entrain each other without either knowing anything about the
    other. What that needs is for the phase relationship between them to settle
    rather than stay arbitrary, which is what this measures and all it claims.

    **Event counts are withheld unless the caller is an authenticated admin.**
    Only applied actions put light in the dish, so the number of onsets in a
    window, set against the actions the public turn log shows were requested,
    gives away how many of them were shams. The shape does not: a phase
    distribution says when light landed relative to the rhythm and nothing
    about which turn produced it. So the histogram goes out normalised, and the
    counts stay behind the same door `applied` does.
    """
    try:
        import admin as admin_module

        privileged = admin_module.is_authenticated()
    except Exception:
        privileged = False

    log = getattr(electrodes, 'log', None)
    if log is None:
        return jsonify({"error": "disk logging is disabled"}), 503

    end = request.args.get('end', type=float) or time.time()
    hours = min(max(request.args.get('hours', 24, type=float), 0.5), 24 * 14)
    start = end - hours * 3600
    channels = tuple(getattr(config, 'ADC_CHANNELS', (0, 1, 2)))
    channel = request.args.get('channel') or f'ch{channels[0]}_mv'
    mode = request.args.get('mode') or None

    stamps, values = [], []
    for name in _reading_modes(mode):
        for row in log.between(start, end, mode=name):
            try:
                stamps.append(float(row['timestamp']))
                values.append(float(row[channel]))
            except (KeyError, TypeError, ValueError):
                continue
    order = sorted(range(len(stamps)), key=lambda i: stamps[i])
    stamps = [stamps[i] for i in order]
    values = [values[i] for i in order]

    onsets = []
    for path in sorted(glob.glob(os.path.join(config.LOG_DIR,
                                              'switches_*.jsonl'))):
        with open(path, encoding='utf-8') as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                stamp = row.get('timestamp')
                if row.get('event') == 'on' and stamp and start <= stamp <= end:
                    onsets.append(float(stamp))

    try:
        sys.path.insert(0, os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'llm', 'filters'))
        from phaselock import analyse
    except ImportError as exc:
        return jsonify({"error": f"phaselock unavailable: {exc}"}), 503

    # Fewer shuffles than the CLI uses: this runs on the Pi while a session is
    # recording, and the verdict is stable well before 1000.
    out = analyse(stamps, values, sorted(onsets),
                  bins=request.args.get('bins', 12, type=int),
                  shuffles=300)
    out.update({"start": start, "end": end, "channel": channel})
    if privileged:
        out["samples"] = len(stamps)
    else:
        total = sum(out.get("bins") or []) or 1
        out["bins"] = [round(c / total, 4) for c in (out.get("bins") or [])]
        out["n_onsets"] = None
        # A thin window must still read as "not enough yet" rather than as a
        # negative result, so the verdict and its reason survive; the number
        # behind it does not.
        out["detail"] = re.sub(r'\d+', 'too few', out.get("detail", ""), count=1)
    return jsonify(out)


@app.route('/api/slime/skeleton', methods=['GET'])
def get_slime_skeleton():
    """The plasmodium's tube network, for the WebGL view.

    Geometry is in dish coordinates -- -1..1 across the diameter, y down, origin
    at the dish centre -- so the renderer never needs to know the capture
    resolution or where the dish happened to sit in frame. Regenerating it after
    the camera moves changes nothing downstream.

    Written by scripts/extract_skeleton.py, or by placeholder_skeleton.py while
    the lighting rebuild is outstanding; `placeholder` in the payload says
    which, so the view can label itself honestly rather than presenting invented
    geometry as a measurement.
    """
    path = os.path.join(config.DATA_DIR, 'skeleton.json')
    if not os.path.exists(path):
        return jsonify({"error": "no skeleton has been extracted yet"}), 404
    try:
        with open(path, encoding='utf-8') as handle:
            return jsonify(json.load(handle))
    except (OSError, ValueError) as exc:
        return jsonify({"error": f"skeleton unreadable: {exc}"}), 500


@app.route('/api/readings/extent', methods=['GET'])
def get_readings_extent():
    """Earliest and latest sample on disk, so the UI knows its scroll limits."""
    log = getattr(electrodes, 'log', None)
    if log is None:
        return jsonify({"error": "disk logging is disabled"}), 503
    earliest = latest = None
    for name in _reading_modes(request.args.get('mode')):
        low, high = log.extent(mode=name)
        if low is not None:
            earliest = low if earliest is None else min(earliest, low)
        if high is not None:
            latest = high if latest is None else max(latest, high)
    return jsonify({"earliest": earliest, "latest": latest})


@app.route('/api/environment/range', methods=['GET'])
def get_environment_range():
    """Bucketed chamber conditions over a window, for the timelapse overlay.

    Reads every mode's directory, not just the one currently running. The
    sensor logs continuously whenever the API is up; what the mode changes is
    only which directory the rows land in, so a window that straddles a mode
    switch is one continuous record split across two folders. Aggregating a
    single mode would blank out everything either side of the switch.
    """
    log = getattr(environment, 'log', None)
    if log is None:
        return jsonify({"error": "disk logging is disabled"}), 503

    start = request.args.get('start', type=float)
    end = request.args.get('end', type=float)
    if start is None or end is None:
        return jsonify({"error": "start and end are required, unix seconds"}), 400
    if end <= start:
        return jsonify({"error": "end must be after start"}), 400

    buckets = max(1, min(request.args.get('buckets', 600, type=int), 5000))
    columns = ['temperature_c', 'temperature_f', 'humidity_pct']

    modes = _reading_modes(request.args.get('mode'))

    width = (end - start) / buckets
    merged = {}
    seen = 0
    for mode in modes:
        table, count = log.aggregate(start, end, buckets, columns, mode=mode)
        seen += count
        # Only one mode records at a time, so buckets do not overlap in
        # practice; first writer wins if they ever do.
        for index, stats in table.items():
            merged.setdefault(index, stats)

    points = []
    for index in sorted(merged):
        entry = {"t": start + (index + 0.5) * width}
        for column in columns:
            stats = merged[index].get(column)
            if stats is None:
                continue
            low, high, total, count = stats
            entry[column] = round(total / count, 2)
        points.append(entry)

    return jsonify({
        "start": start,
        "end": end,
        "buckets": buckets,
        "modes": modes,
        "samples": seen,
        "points": points,
    })


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
        # The dashboard labels each trace with the pair it came from, so it
        # needs to know which electrode is the reference rather than assuming
        # A3 -- true today, but it is config, not a constant.
        "adc_channels": list(getattr(config, 'ADC_CHANNELS', (0, 1, 2))),
        "adc_reference_channel": getattr(config, 'ADC_REFERENCE_CHANNEL', 3),
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

    # Cached hard: the filename carries the capture timestamp and the bytes are
    # written once. Under `no-store` timelapse playback never worked -- every
    # frame was a fresh ~145KB download at 5/s, each cancelling the last.
    # New frames are requested with a cache-busting query string.
    response = send_file(filepath, mimetype='image/jpeg', max_age=31536000)
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    # Werkzeug adds its own Expires alongside Cache-Control; a stale absolute
    # date next to max-age is just a second opinion for a proxy to misread.
    response.headers.pop('Expires', None)
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
    """MJPEG frames from whichever camera is live, at a modest rate."""
    fps = getattr(config, 'STREAM_FPS', 2)
    interval = 1.0 / max(fps, 0.1)
    misses = 0
    while camera is not None:
        started = time.monotonic()
        try:
            frame = camera.stream_frame()
            misses = 0
        except CameraUnavailable:
            # Switching source closes one camera before opening the next, so a
            # gap here is expected and brief. Ending the stream on the first
            # one would leave the dashboard on a broken image until somebody
            # reloaded the page, which is a worse answer than a short freeze.
            misses += 1
            if misses > STREAM_MISS_LIMIT:
                return
            time.sleep(interval)
            continue
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


# --- choosing a camera ------------------------------------------------------

def _admin_request():
    """Whether this request carries a valid admin session.

    Imported here rather than at the top because admin.py is optional -- see
    register_admin -- and a camera route must not be what turns a missing
    webauthn install into a dead dashboard.
    """
    try:
        import admin as admin_module

        return admin_module.is_authenticated()
    except Exception:  # noqa: BLE001 -- no admin module, no admin session
        return False


@app.route('/api/camera/sources', methods=['GET'])
def camera_sources():
    """Attached cameras, and which one is live.

    Behind the admin session not because a camera list is secret, but because
    it is an inventory of what is plugged into the machine and the public
    dashboard has no use for it.
    """
    if not _admin_request():
        return jsonify({"error": "not authenticated"}), 401
    return jsonify({"sources": camera.sources(), **camera.status()})


@app.route('/api/camera/source', methods=['POST'])
def camera_select():
    """Switch to another camera, without restarting the service."""
    if not _admin_request():
        return jsonify({"error": "not authenticated"}), 401

    body = request.get_json(silent=True) or {}
    source = body.get('source', '')
    if not source:
        return jsonify({"error": "source required"}), 400

    if source not in [entry['id'] for entry in camera.sources()]:
        return jsonify({"error": f"no camera with id {source}"}), 404

    try:
        status = camera.select(source)
    except CameraUnavailable as exc:
        # The manager reopens the previous camera before this raises, so a
        # failed switch costs a moment of preview and nothing else.
        return jsonify({"error": str(exc), **camera.status()}), 503

    print(f"admin: camera -> {source} by {request.remote_addr}", flush=True)
    socketio.emit('camera_source', status)
    return jsonify({"ok": True, "sources": camera.sources(), **status})


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

    # Started whether or not a camera is attached right now. It holds the
    # manager rather than a camera, so it starts capturing on its own once one
    # is plugged in and selected, and keeps going across a source change.
    if getattr(config, 'TIMELAPSE_ENABLED', True):
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
