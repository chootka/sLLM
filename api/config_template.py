# Slime Mold Monitor Configuration File
# Copy this to config.py and modify as needed

# GPIO Pin Configuration
RING_LIGHT_PIN = 17        # GPIO pin for ring light control
EXPOSURE_LIGHT_PIN = 27    # GPIO pin for exposure light

# Camera Settings
CAMERA_RESOLUTION = (1920, 1080)
CAMERA_WARMUP_TIME = 2     # seconds
RING_LIGHT_DELAY = 0.5     # seconds to wait after turning on ring light

# Data Collection Settings
ELECTRICAL_SAMPLE_RATE = 10    # Hz (samples per second)
MAX_READINGS_BUFFER = 1000     # Maximum readings to keep in memory
IMAGE_CAPTURE_INTERVAL = 300   # seconds (5 minutes)

# Environmental Monitoring
SENSOR_TYPE = 'SHT31'          # Options: 'SHT31' (recommended), 'DHT22', 'DHT11'
SHT31_I2C_ADDRESS = 0x44       # I2C address for SHT31 (default 0x44, alternative 0x45)
DHT_PIN = 4                    # GPIO pin for DHT22/DHT11 sensors (only used if SENSOR_TYPE is DHT22/DHT11)
DHT_READ_INTERVAL = 2          # seconds (DHT22 minimum is 2 seconds, SHT31 can read faster)
ENABLE_DHT_SENSOR = True       # Set to False to disable temperature/humidity sensor

# Socket.IO Settings
SOCKET_EMIT_INTERVAL = 0.5     # seconds between Socket.IO emissions
ENABLE_WEBSOCKETS = True       # Set to False to disable Socket.IO

# ADC Settings
ADC_GAIN = 1                   # Gain setting for ADS1115 (1 = ±4.096V)
ADC_ADDRESS = 0x48            # I2C address of ADS1115

# Server Settings
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
DEBUG_MODE = False

# Data Storage
# Use relative path from project root, or absolute path on Pi
# For local development: '../data' (relative to api/ directory)
# For Pi deployment: '/var/www/sllm/data' or project root 'data'
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
IMAGE_DIR = os.path.join(DATA_DIR, 'images')
LOG_DIR = os.path.join(DATA_DIR, 'logs')
CSV_DIR = os.path.join(DATA_DIR, 'readings')

# Safety Features
MAX_EXPOSURE_DURATION = 30     # Maximum seconds exposure light can be on
AUTO_LIGHT_OFF = True         # Automatically turn off exposure light after max duration

# Frontend Update Rates
CHART_UPDATE_RATE = 500       # milliseconds
STATUS_CHECK_INTERVAL = 5000  # milliseconds
