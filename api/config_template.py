# sLLM configuration template.
#
# Copy to config.py and edit for the machine you are on:
#
#     cp config_template.py config.py
#
# config.py is deliberately NOT tracked in git. Each checkout and each deployed
# copy keeps its own, so the two can never silently drift the way they did when
# config.py was committed (the repo said /home/pi, the deployed copy said
# /var/www, and only the deployed one was right).

import os

# --- data storage -----------------------------------------------------------
# Derived from wherever this file actually lives, so a checkout at ~/sllm and a
# deploy at /var/www/sllm each resolve to their own data directory with no edit.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
IMAGE_DIR = os.path.join(DATA_DIR, 'images')
LOG_DIR = os.path.join(DATA_DIR, 'logs')
CSV_DIR = os.path.join(DATA_DIR, 'readings')

# --- electrodes, ADS1115 ----------------------------------------------------
# Three recording electrodes read differentially against the reference in the
# corner under the barrier zone. Gain 16 is +/-0.256V full scale; plasmodium
# surface potentials are single-digit millivolts, so the coarse gains waste
# nearly all the range.
ADC_ADDRESS = 0x48
ADC_GAIN = 16
ADC_SAMPLE_RATE = 1.0          # Hz
ADC_CHANNELS = (0, 1, 2)       # differential pairs, each against channel 3
ADC_REFERENCE_CHANNEL = 3

# In-memory rolling buffer. Must exceed the reducer's 30 minute window or the
# model loop can never assemble a full one -- at 1 Hz, 1800 samples IS the
# window, so this carries 40 minutes for headroom. The durable record is the
# CSV in data/readings, not this.
MAX_READINGS_BUFFER = 2400

# Settling time after any switching event before the ADC is allowed to convert
# again. Nothing may convert while the matrix, fan or relay is being energised.
ADC_SWITCH_SETTLE = 0.25       # seconds

# --- temperature and humidity, SHT31 ----------------------------------------
SHT31_I2C_ADDRESS = 0x44       # 0x44 default, 0x45 if the ADDR pin is pulled high
SENSOR_READ_INTERVAL = 1.0     # seconds

# --- chamber fan ------------------------------------------------------------
# The fan keeps fresh air moving so mould does not establish. That is its only
# purpose. It will shift humidity and temperature as a side effect, which is
# accepted, but neither is a setpoint and neither decides when it runs -- the
# timed cycle below is the whole rule.
#
# Wiring, verified on the bench 2026-08-05 by listening to the contact and
# watching the blades:
#   relay IN  -> physical pin 16 = BCM 23, active-high (HIGH closes)
#   fan PWM   -> physical pin 32 = BCM 12
# The PWM line is held HIGH as a level whenever the relay closes, not driven
# as a waveform -- see the Relay docstring in gpio/sensor.py for why. Without
# it the relay clicks and the fan does not turn, because the pin idles as an
# input with the pull-down on and the fan reads that as 0% duty.
#
# A vaporizer, if one is added later, is the same shape: a relay on a pin with
# dwell times, driven from whatever rule suits it.
FAN_ENABLED = True
FAN_PIN = 23                   # BCM, relay controlling the Noctua NF-A6x25 5V
FAN_PWM_PIN = 12               # BCM, fan PWM line, held high while running

# Air exchange: run FAN_CYCLE_ON seconds in every FAN_CYCLE_PERIOD. 60 in 300
# is 20% duty -- short frequent bursts rather than long runs. This is a
# starting point, not a derived number; the empty-chamber run is what tunes it.
FAN_CYCLE_PERIOD = 300         # seconds, the air-exchange window
FAN_CYCLE_ON = 60              # seconds of run per window

# Dwell times, only to stop the contacts chattering. Keep FAN_MIN_ON below
# FAN_CYCLE_ON or the relay will refuse to release at the end of a burst and
# overrun the window.
FAN_MIN_ON = 30                # seconds, minimum run once started
FAN_MIN_OFF = 60               # seconds, minimum rest once stopped

# Optional extra ventilation at saturation. Off by default: it is not part of
# the mould logic. Set both to enable, RH_OFF below RH_ON. It can only ever add
# run time on top of the cycle, never take it away.
FAN_RH_ON = None               # e.g. 95.0
FAN_RH_OFF = None              # e.g. 91.0

# --- camera -----------------------------------------------------------------
# Pi Camera Module 3 NoIR (IMX708) on CSI. Capture runs through the matrix
# blank/flash sequence in gpio/leds.py, so no separate illuminator is
# configured here.
#
# Set CAMERA_RESOLUTION to None to use the largest mode the fitted sensor
# reports. 2304x1296 is the IMX708's binned full-field mode: the full 4608x2592
# is four times the pixels for no extra information about a plasmodium, and it
# makes a multi-day timelapse enormous.
CAMERA_RESOLUTION = (2304, 1296)
CAMERA_WARMUP_TIME = 2         # seconds
IMAGE_CAPTURE_INTERVAL = 300   # seconds

# Module 3 has an autofocus lens and the dish never moves, so focus is locked
# rather than left hunting between frames. None sweeps autofocus once at
# startup and holds it. A number fixes the lens in dioptres (1/metres): 0 is
# infinity, and for a dish roughly 20cm below the lens, 5.0 is the ballpark.
# Set this once the camera is mounted and the framing is final.
CAMERA_FOCUS_DIOPTRES = None

# --- stimulus ---------------------------------------------------------------
# The blue zone the API lights when the dashboard's light button is used.
# Zone 4 is the centre of the dish. Zone 2 is the barrier over the reference
# electrode and is never drivable -- gpio/leds.py refuses it.
DEFAULT_STIMULUS_ZONE = 4
MAX_STIMULUS_DURATION = 300    # seconds; a manual stimulus always self-cancels

# --- live preview -----------------------------------------------------------
# Frames per second for /api/stream. Kept low on purpose: the preview exists to
# frame and focus the camera, and every frame competes with the timelapse for
# the same capture lock.
STREAM_FPS = 2
TIMELAPSE_ENABLED = True

# --- the model loop ---------------------------------------------------------
# Ollama runs on the laptop, not here. This is chootka-pro's Tailscale address,
# so it works from anywhere rather than only on the studio LAN.
#
# Ollama binds 127.0.0.1 by default and will refuse the Pi until it is told
# otherwise. On the Mac:
#     launchctl setenv OLLAMA_HOST 0.0.0.0
# then restart Ollama. Check from here with: python3 llm/loop.py --check
OLLAMA_HOST = 'http://100.127.41.6:11434'
OLLAMA_MODEL = 'qwen2.5:14b'

LLM_PROMPT = 'blind'           # blind | informed | null, see llm/filters/prompts.md
LLM_WINDOW_S = 1800            # what the model sees, 30 min ~ 15-30 contractions
LLM_TURN_INTERVAL = 600        # how often it speaks
LLM_HISTORY_TURNS = 8          # how far back it remembers

# Fraction of turns where the action is logged and NOT applied. The model is
# never told which turn it is in; that is what makes it a control rather than
# a bug. Set to 0.0 only for a deliberately uncontrolled run.
LLM_SHAM_RATE = 0.25

# --- server -----------------------------------------------------------------
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
DEBUG_MODE = False
SOCKET_EMIT_INTERVAL = 0.5     # seconds between Socket.IO emissions
ENABLE_WEBSOCKETS = True

# --- frontend ---------------------------------------------------------------
CHART_UPDATE_RATE = 500        # milliseconds
STATUS_CHECK_INTERVAL = 5000   # milliseconds
