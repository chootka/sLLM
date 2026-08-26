# Copy to config.py and edit for this machine. config.py is NOT tracked, so a
# checkout and a deploy each keep their own and cannot drift.

import os

# --- data storage -----------------------------------------------------------
# Derived from this file's location, so a checkout and a deploy each resolve
# to their own data directory with no edit.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
IMAGE_DIR = os.path.join(DATA_DIR, 'images')
LOG_DIR = os.path.join(DATA_DIR, 'logs')
CSV_DIR = os.path.join(DATA_DIR, 'readings')

# --- electrodes, ADS1115 ----------------------------------------------------
# Three electrodes read differentially against the reference under the barrier
# zone. Gain 16 is +/-0.256V full scale; surface potentials are single-digit mV.
ADC_ADDRESS = 0x48
ADC_GAIN = 16
ADC_DATA_RATE = 8              # SPS, 125ms integration per conversion
ADC_SAMPLE_RATE = 1.0          # Hz
ADC_CHANNELS = (0, 1, 2)       # differential pairs, each against channel 3
ADC_REFERENCE_CHANNEL = 3

# Rolling buffer. Must exceed the reducer's 1800-sample window; 40 min of
# headroom. The durable record is the CSV in data/readings.
MAX_READINGS_BUFFER = 2400

# Settle after any switching event. Nothing converts while the matrix, fan or
# relay is being energised.
ADC_SWITCH_SETTLE = 0.25       # seconds

# --- temperature and humidity, SHT31 ----------------------------------------
SHT31_I2C_ADDRESS = 0x44       # 0x44 default, 0x45 if the ADDR pin is pulled high
SENSOR_READ_INTERVAL = 1.0     # seconds

# --- chamber fan ------------------------------------------------------------
# Airflow to stop mould. RH and temperature move as a side effect; neither is a
# setpoint. The timed cycle below is the whole rule.
#
# Wiring, verified on the bench 2026-08-05:
#   relay IN  -> physical pin 16 = BCM 23, active-high (HIGH closes)
#   fan PWM   -> physical pin 32 = BCM 12
# PWM is held HIGH as a level, not a waveform. Without it the relay clicks and
# the fan sits still: the pin idles as an input with the pull-down on, which a
# 4-pin fan reads as 0% duty.
FAN_ENABLED = True
FAN_PIN = 23                   # BCM, relay controlling the Noctua NF-A6x25 5V
FAN_PWM_PIN = 12               # BCM, fan PWM line, held high while running

# Run FAN_CYCLE_ON seconds in every FAN_CYCLE_PERIOD. 20% duty, a starting
# point; the empty-chamber run tunes it.
FAN_CYCLE_PERIOD = 300         # seconds, the air-exchange window
FAN_CYCLE_ON = 60              # seconds of run per window

# Dwell times, to stop the contacts chattering. Keep FAN_MIN_ON below
# FAN_CYCLE_ON or the relay overruns the window.
FAN_MIN_ON = 30                # seconds, minimum run once started
FAN_MIN_OFF = 60               # seconds, minimum rest once stopped

# Optional extra ventilation at saturation, off by default. Set both, RH_OFF
# below RH_ON. Only ever adds run time on top of the cycle.
FAN_RH_ON = None               # e.g. 95.0
FAN_RH_OFF = None              # e.g. 91.0

# --- camera -----------------------------------------------------------------
# CSI or USB. Capture runs through the blank/flash sequence in gpio/leds.py
# either way, so there is no separate illuminator here.
#
# CAMERA_SOURCE picks the one to open at startup:
#   'auto'                        first camera found, CSI before USB
#   'csi'                         the ribbon
#   '/dev/v4l/by-id/usb-...'      a specific USB camera
# The admin page's last selection outranks this.
# `./scripts/py gpio/camera.py info` lists the ids.
CAMERA_SOURCE = 'auto'

# None uses the sensor's largest mode. 2304x1296 is the IMX708 binned
# full-field; the full 4608x2592 adds nothing and bloats the timelapse.
CAMERA_RESOLUTION = (2304, 1296)
CAMERA_WARMUP_TIME = 2         # seconds
IMAGE_CAPTURE_INTERVAL = 300   # seconds

# USB only. Separate because a UVC camera silently substitutes its nearest
# mode when asked for one it does not have.
USB_CAMERA_RESOLUTION = (1920, 1080)
USB_CAMERA_JPEG_QUALITY = 92

# Frames to discard first: V4L2 queues stale frames, so without this the still
# taken during the flash can predate it. ~200ms at 30fps.
USB_CAMERA_FLUSH_FRAMES = 6

# Focus is locked, not left hunting. None sweeps autofocus once at startup and
# holds it; a number fixes the lens in dioptres (1/m). ~5.0 for a dish 20cm
# below. Set once the framing is final.
CAMERA_FOCUS_DIOPTRES = None

# --- stimulus ---------------------------------------------------------------
# Zone the dashboard light button drives. 4 is the centre. Zone 2 is the
# barrier and gpio/leds.py refuses it.
DEFAULT_STIMULUS_ZONE = 4
MAX_STIMULUS_DURATION = 300    # seconds; a manual stimulus always self-cancels

# --- live preview -----------------------------------------------------------
# /api/stream fps. Low on purpose: every frame competes with the timelapse for
# the capture lock.
STREAM_FPS = 2
TIMELAPSE_ENABLED = True

# --- the model loop ---------------------------------------------------------
# Ollama runs on the laptop. Tailscale address, so it works off the studio LAN.
# Ollama binds 127.0.0.1 by default; on the Mac:
#     launchctl setenv OLLAMA_HOST 0.0.0.0
# then restart it. Check with: python3 llm/loop.py --check
OLLAMA_HOST = 'http://100.127.41.6:11434'
OLLAMA_MODEL = 'qwen2.5:14b'

LLM_PROMPT = 'blind'           # blind | informed | adversarial | mimic | null
LLM_WINDOW_S = 1800            # what the model sees, 30 min ~ 15-30 contractions
LLM_TURN_INTERVAL = 600        # how often it speaks
LLM_HISTORY_TURNS = 8          # how far back it remembers; 0 = everything

# Context window. None leaves it to the model's Modelfile, fine for blind and
# informed since they truncate history and never fill it. Adversarial forces
# 32768 if unset, because it reports remaining tokens to the model.
# ~1400 tokens per turn pair active, so ~23 turns. State is 364 tokens active
# against 69 quiet: a suppressed organism costs a fifth as much.
LLM_NUM_CTX = None

# Fraction of turns logged and NOT applied. The model is never told which. Set
# 0.0 only for a deliberately uncontrolled run.
LLM_SHAM_RATE = 0.25

# --- server -----------------------------------------------------------------
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 5000
DEBUG_MODE = False
SOCKET_EMIT_INTERVAL = 0.5     # seconds between Socket.IO emissions
ENABLE_WEBSOCKETS = True

# --- frontend ---------------------------------------------------------------
CHART_UPDATE_RATE = 500        # milliseconds
STATUS_CHECK_INTERVAL = 5000   # milliseconds

# --- admin controls ---------------------------------------------------------
# Passkey (WebAuthn) auth: no password anywhere, the server holds only public
# keys. Enrol with scripts/enrol_passkey.py, which must run on the Pi -- SSH
# access is the authority to enrol and the recovery path if every device is
# lost, so register at least two.
#
# ADMIN_ORIGIN must match what the browser shows byte for byte, scheme
# included; a mismatch fails with an unhelpful error.
ADMIN_RP_ID = 'sllm.visceral.systems'
ADMIN_RP_NAME = 'sLLM'
ADMIN_ORIGIN = 'https://sllm.visceral.systems'

# Enrolled public keys and unspent enrolment tokens. Created mode 0600.
ADMIN_CREDENTIALS_FILE = os.path.join(DATA_DIR, 'admin_credentials.json')

# --- chamber occupancy ------------------------------------------------------
# The recording mode is the occupancy flag: `live` means something is in the
# chamber, `test` means there is not. Set it wrong and a real session lands in
# the test subdirectory, so it gets corrected fast.
#
# Its one job today is to refuse `loop.py --demo`, which invents data and puts
# real light on the panel.
