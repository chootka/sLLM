# Slime Mold Monitor Configuration File
# Copy this to config.py and modify as needed

# GPIO Pin Configuration
RING_LIGHT_PIN = 17        # GPIO pin for ring light control
EXPOSURE_LIGHT_PIN = 27    # GPIO pin for exposure light
DHT_PIN = 4                # GPIO pin for DHT22 sensor

# Camera Settings
CAMERA_RESOLUTION = (1920, 1080)
CAMERA_WARMUP_TIME = 2     # seconds
RING_LIGHT_DELAY = 0.5     # seconds to wait after turning on ring light

# Data Collection Settings
ELECTRICAL_SAMPLE_RATE = 10    # Hz (samples per second)
MAX_READINGS_BUFFER = 1000     # Maximum readings to keep in memory
IMAGE_CAPTURE_INTERVAL = 300   # seconds (5 minutes)

# Environmental Monitoring
DHT_READ_INTERVAL = 2          # seconds (DHT22 minimum is 2 seconds)
ENABLE_DHT_SENSOR = True       # Set to False to disable DHT sensor

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
DATA_DIR = '/home/pi/sllm/data'
IMAGE_DIR = f'{DATA_DIR}/images'
LOG_DIR = f'{DATA_DIR}/logs'
CSV_DIR = f'{DATA_DIR}/readings'

# Safety Features
MAX_EXPOSURE_DURATION = 30     # Maximum seconds exposure light can be on
AUTO_LIGHT_OFF = True         # Automatically turn off exposure light after max duration

# Frontend Update Rates
CHART_UPDATE_RATE = 500       # milliseconds
STATUS_CHECK_INTERVAL = 5000  # milliseconds
