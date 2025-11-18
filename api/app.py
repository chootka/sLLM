#!/usr/bin/env python3
"""
Slime Mold API Server
Provides endpoints for electrical readings, camera capture, and light control
with real-time Socket.IO support
"""

import time
import json
import threading
import base64
import os
import sys
import random
# Add system site-packages for libgpiod (required for Raspberry Pi 5)
sys.path.insert(0, '/usr/lib/python3/dist-packages')
from datetime import datetime
from collections import deque
from flask import Flask, jsonify, send_file, request, Response
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import RPi.GPIO as GPIO
import board
import busio
import serial
import serial.tools.list_ports
import cv2
import numpy as np

# USB HID support for HID-based relay modules
try:
    import usb.core
    import usb.util
    HID_AVAILABLE = True
except ImportError:
    HID_AVAILABLE = False
    print("⚠️  pyusb not installed - HID relay support disabled")
    print("  Install with: pip install pyusb")

# Load configuration
try:
    import config
    print("Loaded configuration from config.py")
except ImportError:
    print("Warning: config.py not found. Using default configuration.")
    print("Copy config_template.py to config.py and customize as needed.")
    import config_template as config

# Temperature/Humidity sensor support (when available)
SENSOR_AVAILABLE = False
SENSOR_TYPE = getattr(config, 'SENSOR_TYPE', 'SHT31').upper()  # Default to SHT31, fallback to DHT22
if config.ENABLE_DHT_SENSOR:
    if SENSOR_TYPE == 'SHT31':
        try:
            import adafruit_sht31d
            SENSOR_AVAILABLE = True
        except ImportError:
            print("SHT31 sensor library not installed. Trying DHT22...")
            try:
                import adafruit_dht
                SENSOR_AVAILABLE = True
                SENSOR_TYPE = 'DHT22'
            except ImportError:
                print("DHT sensor library not installed. Temperature/humidity monitoring disabled.")
    else:  # DHT22 or DHT11
        try:
            import adafruit_dht
            SENSOR_AVAILABLE = True
        except ImportError:
            print("DHT sensor library not installed. Temperature/humidity monitoring disabled.")

app = Flask(__name__)
CORS(app)  # Enable CORS for web frontend
socketio = SocketIO(app, cors_allowed_origins="*")  # Enable Socket.IO with CORS

# Configuration from config.py
EXPOSURE_LIGHT_PIN = config.EXPOSURE_LIGHT_PIN
RING_LIGHT_PIN = getattr(config, 'RING_LIGHT_PIN', 17)  # GPIO pin for ring light relay control
DHT_PIN = getattr(config, 'DHT_PIN', 4)  # GPIO pin for DHT sensors
SHT31_I2C_ADDRESS = getattr(config, 'SHT31_I2C_ADDRESS', 0x44)  # Default I2C address for SHT31
MAX_READINGS = config.MAX_READINGS_BUFFER
EMIT_INTERVAL = config.SOCKET_EMIT_INTERVAL

# Create data directories if they don't exist
os.makedirs(config.IMAGE_DIR, exist_ok=True)
os.makedirs(config.LOG_DIR, exist_ok=True)
os.makedirs(config.CSV_DIR, exist_ok=True)

# Global data storage
readings_buffer = deque(maxlen=MAX_READINGS)
readings_lock = threading.Lock()
current_reading = {"timestamp": 0, "value": 0}
current_environment = {"temperature": None, "humidity": None, "timestamp": 0}

# Initialize hardware
try:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(EXPOSURE_LIGHT_PIN, GPIO.OUT)
    GPIO.setup(RING_LIGHT_PIN, GPIO.OUT)
    GPIO.output(EXPOSURE_LIGHT_PIN, GPIO.LOW)
    GPIO.output(RING_LIGHT_PIN, GPIO.LOW)  # Ring light off by default
    print(f"✓ GPIO initialized (exposure light: GPIO {EXPOSURE_LIGHT_PIN}, ring light: GPIO {RING_LIGHT_PIN})")
except Exception as e:
    print(f"⚠ WARNING: GPIO initialization failed: {e}")
    print("  Ring light control will be disabled, but image capture will still work")

# Initialize Serial connection to Arduino
SERIAL_BAUD = 1200  # Match Arduino's Serial.begin(1200)

def find_arduino_port():
    """Find the Arduino serial port automatically"""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        # Common Arduino identifiers
        if any(keyword in port.description.upper() for keyword in ['USB', 'ARDUINO', 'CH340', 'FTDI', 'SERIAL']):
            return port.device
    # Fallback: try common port names
    for port_name in ['/dev/ttyUSB0', '/dev/ttyACM0', '/dev/ttyUSB1', '/dev/ttyACM1']:
        try:
            test_serial = serial.Serial(port_name, SERIAL_BAUD, timeout=1)
            test_serial.close()
            return port_name
        except:
            continue
    return None

SERIAL_PORT = find_arduino_port()
arduino_serial = None
if SERIAL_PORT:
    try:
        arduino_serial = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
        print(f"✓ Arduino connected on {SERIAL_PORT} at {SERIAL_BAUD} baud")
    except Exception as e:
        print(f"✗ Failed to open serial port {SERIAL_PORT}: {e}")
        arduino_serial = None
else:
    print("✗ WARNING: Could not find Arduino serial port")
    print("  Trying default /dev/ttyUSB0...")
    try:
        arduino_serial = serial.Serial('/dev/ttyUSB0', SERIAL_BAUD, timeout=1)
        print("✓ Connected to /dev/ttyUSB0")
    except Exception as e:
        print(f"✗ Failed to open /dev/ttyUSB0: {e}")
        arduino_serial = None

# Ring light control via GPIO relay module
# The Neewer BR60 is USB-powered but doesn't have software control.
# Use a GPIO relay module to switch the USB power lines:
# - Connect relay module to Pi: GND→GND, 5V→5V, Signal→GPIO 17
# - Use USB breakout board: plug ring light USB cable into breakout
# - Wire breakout VBUS (+5V) through relay terminals: USB power→COM, NO→Breakout VBUS
# - Wire breakout GND directly (not through relay)
# - When GPIO 17 goes HIGH, relay closes and ring light turns on

def turn_ring_light_on():
    """Turn on the ring light via GPIO-controlled relay"""
    try:
        GPIO.output(RING_LIGHT_PIN, GPIO.HIGH)
        return True
    except Exception as e:
        print(f"Error turning on ring light: {e}")
        return False

def turn_ring_light_off():
    """Turn off the ring light via GPIO-controlled relay"""
    try:
        GPIO.output(RING_LIGHT_PIN, GPIO.LOW)
        return True
    except Exception as e:
        print(f"Error turning off ring light: {e}")
        return False

# Initialize temperature/humidity sensor (if available)
env_sensor = None
if SENSOR_AVAILABLE:
    try:
        if SENSOR_TYPE == 'SHT31':
            # SHT31 uses I2C
            i2c = busio.I2C(board.SCL, board.SDA)
            env_sensor = adafruit_sht31d.SHT31D(i2c, address=SHT31_I2C_ADDRESS)
            print(f"✓ SHT31 sensor initialized on I2C (address 0x{SHT31_I2C_ADDRESS:02X})")
        else:
            # DHT22 or DHT11 uses GPIO
            dht_board_pin = getattr(board, f'D{DHT_PIN}')
            if SENSOR_TYPE == 'DHT11':
                env_sensor = adafruit_dht.DHT11(dht_board_pin)
                print(f"✓ DHT11 sensor initialized on GPIO {DHT_PIN}")
            else:  # DHT22
                env_sensor = adafruit_dht.DHT22(dht_board_pin)
                print(f"✓ DHT22 sensor initialized on GPIO {DHT_PIN}")
    except Exception as e:
        print(f"✗ Failed to initialize {SENSOR_TYPE} sensor: {e}")
        env_sensor = None

# Initialize USB camera
usb_camera = None
try:
    usb_camera = cv2.VideoCapture(0)  # Use first available USB camera
    if usb_camera.isOpened():
        # Set camera resolution if specified in config
        if hasattr(config, 'CAMERA_RESOLUTION') and config.CAMERA_RESOLUTION:
            width, height = config.CAMERA_RESOLUTION
            usb_camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            usb_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        print("✓ USB camera initialized")
    else:
        print("✗ WARNING: Could not open USB camera")
        usb_camera = None
except Exception as e:
    print(f"✗ Failed to initialize USB camera: {e}")
    usb_camera = None

def read_electrical_data():
    """Continuously read electrical data from Arduino via serial port"""
    global current_reading, arduino_serial, SERIAL_PORT
    
    reconnect_attempts = 0
    last_reconnect_attempt = 0
    
    while True:
        # If no serial connection, try to find and connect to Arduino
        if arduino_serial is None or not arduino_serial.is_open:
            current_time = time.time()
            # Try to reconnect every 5 seconds
            if current_time - last_reconnect_attempt > 5:
                last_reconnect_attempt = current_time
                reconnect_attempts += 1
                
                # Close existing connection if any
                try:
                    if arduino_serial and arduino_serial.is_open:
                        arduino_serial.close()
                except:
                    pass
                
                # Try to find Arduino port (in case it was just plugged in)
                if not SERIAL_PORT or reconnect_attempts % 10 == 0:  # Re-scan every 10 attempts (50 seconds)
                    SERIAL_PORT = find_arduino_port()
                    if SERIAL_PORT:
                        print(f"Found Arduino on {SERIAL_PORT}")
                
                # Try to connect
                if SERIAL_PORT:
                    try:
                        arduino_serial = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
                        print(f"✓ Connected to Arduino on {SERIAL_PORT}")
                        reconnect_attempts = 0  # Reset counter on success
                    except Exception as e:
                        print(f"✗ Failed to connect to {SERIAL_PORT}: {e}")
                        arduino_serial = None
                else:
                    if reconnect_attempts == 1 or reconnect_attempts % 20 == 0:  # Print every 20 attempts (100 seconds)
                        print("⚠ Waiting for Arduino to be connected...")
            
            time.sleep(1)
            continue
        
        # Read data from serial port
        try:
            if arduino_serial.in_waiting > 0:
                line = arduino_serial.readline().decode('utf-8', errors='ignore').strip()
                
                if line:
                    # Parse the voltage value (Arduino sends in mV, keep as mV)
                    try:
                        voltage_mv = float(line)
                        
                        timestamp = time.time()
                        reading = {
                            "timestamp": timestamp,
                            "value": voltage_mv,  # Keep in millivolts
                            "datetime": datetime.now().isoformat()
                        }
                        
                        with readings_lock:
                            readings_buffer.append(reading)
                            current_reading = reading
                            
                    except ValueError:
                        # Skip invalid lines (non-numeric data)
                        continue
            
            # Small delay to prevent CPU spinning
            time.sleep(0.01)
            
        except serial.SerialException as e:
            print(f"Serial port error: {e}")
            # Close the connection so we can reconnect
            try:
                if arduino_serial and arduino_serial.is_open:
                    arduino_serial.close()
            except:
                pass
            arduino_serial = None
            time.sleep(1)
        except Exception as e:
            print(f"Error reading serial: {e}")
            time.sleep(1)

def read_environment_data():
    """Read temperature and humidity data"""
    global current_environment
    
    # Mock data variables for when sensor is not available
    mock_temp_base = 22.0  # Base temperature in Celsius
    mock_humidity_base = 55.0  # Base humidity in %
    mock_temp_variation = 0.0
    mock_humidity_variation = 0.0
    
    while True:
        if env_sensor:
            # Real sensor reading
            try:
                temperature = env_sensor.temperature
                humidity = env_sensor.humidity
                
                if temperature is not None and humidity is not None:
                    current_environment = {
                        "temperature": temperature,
                        "humidity": humidity,
                        "timestamp": time.time(),
                        "datetime": datetime.now().isoformat()
                    }
            except RuntimeError as e:
                # DHT sensors can be flaky, this is normal
                if SENSOR_TYPE != 'SHT31':  # SHT31 is more reliable, log errors
                    pass
                else:
                    print(f"Error reading SHT31 sensor: {e}")
            except Exception as e:
                print(f"Error reading {SENSOR_TYPE} sensor: {e}")
        else:
            # Generate mock data
            # Simulate natural variation
            mock_temp_variation += random.uniform(-0.1, 0.1)
            mock_temp_variation = max(-2.0, min(2.0, mock_temp_variation))  # Clamp variation
            
            mock_humidity_variation += random.uniform(-0.5, 0.5)
            mock_humidity_variation = max(-5.0, min(5.0, mock_humidity_variation))  # Clamp variation
            
            # Generate realistic readings with some noise
            temperature = mock_temp_base + mock_temp_variation + random.uniform(-0.2, 0.2)
            humidity = mock_humidity_base + mock_humidity_variation + random.uniform(-1.0, 1.0)
            
            # Clamp to realistic ranges
            temperature = max(18.0, min(26.0, temperature))
            humidity = max(40.0, min(70.0, humidity))
            
            current_environment = {
                "temperature": round(temperature, 1),
                "humidity": round(humidity, 1),
                "timestamp": time.time(),
                "datetime": datetime.now().isoformat()
            }
        
        # SHT31 can read faster, DHT sensors need 2+ seconds, mock data every second
        read_interval = 1.0 if (SENSOR_TYPE == 'SHT31' or not env_sensor) else config.DHT_READ_INTERVAL
        time.sleep(read_interval)

def emit_realtime_data():
    """Emit real-time data via Socket.IO"""
    while True:
        try:
            # Emit electrical reading
            with readings_lock:
                if current_reading["timestamp"] > 0:
                    socketio.emit('reading_update', current_reading)
            
            # Emit environmental data if available
            if current_environment["temperature"] is not None:
                socketio.emit('environment_update', current_environment)
            
            # Get system status
            status = {
                "exposure_light": GPIO.input(EXPOSURE_LIGHT_PIN) == GPIO.HIGH,
                "timestamp": time.time()
            }
            socketio.emit('status_update', status)
            
        except Exception as e:
            print(f"Error emitting data: {e}")
        
        time.sleep(EMIT_INTERVAL)

@app.route('/')
def serve_frontend():
    return send_file('../frontend/index.html')

@app.route('/api/readings', methods=['GET'])
def get_readings():
    """Get current electrical reading"""
    with readings_lock:
        return jsonify(current_reading)

@app.route('/api/readings/history', methods=['GET'])
def get_readings_history():
    """Get historical electrical readings"""
    limit = request.args.get('limit', 100, type=int)
    with readings_lock:
        recent_readings = list(readings_buffer)[-limit:]
    return jsonify(recent_readings)

@app.route('/api/environment', methods=['GET'])
def get_environment():
    """Get current temperature and humidity"""
    return jsonify(current_environment)

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get relevant configuration for frontend"""
    return jsonify({
        "image_capture_interval": config.IMAGE_CAPTURE_INTERVAL,
        "max_exposure_duration": config.MAX_EXPOSURE_DURATION,
        "chart_update_rate": config.CHART_UPDATE_RATE,
        "status_check_interval": config.STATUS_CHECK_INTERVAL,
        "websockets_enabled": config.ENABLE_WEBSOCKETS,
        "server_port": config.SERVER_PORT
    })

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print(f"Client connected: {request.sid}")
    # Send current state to new client
    with readings_lock:
        if current_reading["timestamp"] > 0:
            emit('reading_update', current_reading)
    
    if current_environment["temperature"] is not None:
        emit('environment_update', current_environment)
    
    status = {
        "exposure_light": GPIO.input(EXPOSURE_LIGHT_PIN) == GPIO.HIGH,
        "timestamp": time.time()
    }
    emit('status_update', status)

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print(f"Client disconnected: {request.sid}")

@app.route('/api/images/<filename>', methods=['GET'])
def get_image(filename):
    """Serve an image file by filename"""
    try:
        # Security: only allow jpg files from IMAGE_DIR
        if not filename.endswith('.jpg'):
            return jsonify({"error": "Invalid file type"}), 400
        
        # Prevent directory traversal
        if '/' in filename or '..' in filename:
            return jsonify({"error": "Invalid filename"}), 400
        
        filepath = os.path.join(config.IMAGE_DIR, filename)
        if not os.path.exists(filepath):
            return jsonify({"error": "Image not found"}), 404
        
        response = send_file(filepath, mimetype='image/jpeg')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        print(f"Error serving image {filename}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/capture-image', methods=['POST'])
def capture_image():
    """Capture an image with the USB camera"""
    try:
        print("📸 Capture image request received")
        
        if usb_camera is None or not usb_camera.isOpened():
            error_msg = "USB camera not available"
            print(f"❌ {error_msg}")
            return jsonify({"error": error_msg}), 500
        
        print("✓ USB camera is available")
        
        # Turn on USB ring light
        print("💡 Turning on ring light...")
        turn_ring_light_on()
        time.sleep(config.RING_LIGHT_DELAY)  # Let light stabilize
        
        # Capture image from USB camera
        print("📷 Capturing image from camera...")
        ret, frame = usb_camera.read()
        if not ret:
            print("❌ Failed to read frame from camera")
            turn_ring_light_off()
            return jsonify({"error": "Failed to capture image from USB camera"}), 500
        
        print(f"✓ Frame captured: {frame.shape if frame is not None else 'None'}")
        
        # Save image with millisecond precision to ensure unique filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds (last 3 digits of microseconds)
        filename = os.path.join(config.IMAGE_DIR, f"slime_{timestamp}.jpg")
        print(f"💾 Saving image to: {filename}")
        
        success = cv2.imwrite(filename, frame)
        if not success:
            print("❌ Failed to save image file")
            turn_ring_light_off()
            return jsonify({"error": "Failed to save image file"}), 500
        
        file_size = os.path.getsize(filename)
        print(f"✓ Image saved: {file_size} bytes")
        
        # Turn off USB ring light
        print("💡 Turning off ring light...")
        turn_ring_light_off()
        
        image_filename = os.path.basename(filename)
        
        # Emit image capture event with filename
        socketio.emit('image_captured', {
            "filename": image_filename,
            "timestamp": time.time()
        })
        
        # Return JSON with filename instead of the image file directly
        # Frontend will fetch the image using the filename to avoid blob URL caching issues
        print(f"✅ Image captured: {image_filename}")
        return jsonify({
            "success": True,
            "filename": image_filename,
            "url": f"/api/images/{image_filename}"
        })
        
    except Exception as e:
        error_msg = f"Error capturing image: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def generate_stream():
    """Generate MJPEG stream from USB camera"""
    while True:
        if usb_camera is None or not usb_camera.isOpened():
            break
        
        ret, frame = usb_camera.read()
        if not ret:
            break
        
        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            continue
        
        # Yield frame in MJPEG format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        
        # Small delay to control frame rate (adjust as needed)
        time.sleep(0.033)  # ~30 FPS

@app.route('/api/stream')
def video_stream():
    """Live video stream endpoint"""
    if usb_camera is None or not usb_camera.isOpened():
        return jsonify({"error": "USB camera not available"}), 500
    
    return Response(generate_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/trigger-light', methods=['POST'])
def trigger_light():
    """Control the exposure light"""
    try:
        data = request.get_json()
        state = data.get('state', 'toggle')
        duration = data.get('duration', 0)  # Duration in seconds, 0 = permanent
        
        # Apply safety limits from config
        if config.AUTO_LIGHT_OFF and duration == 0:
            duration = config.MAX_EXPOSURE_DURATION
        elif duration > config.MAX_EXPOSURE_DURATION:
            duration = config.MAX_EXPOSURE_DURATION
        
        if state == 'on':
            GPIO.output(EXPOSURE_LIGHT_PIN, GPIO.HIGH)
            if duration > 0:
                threading.Timer(duration, lambda: GPIO.output(EXPOSURE_LIGHT_PIN, GPIO.LOW)).start()
        elif state == 'off':
            GPIO.output(EXPOSURE_LIGHT_PIN, GPIO.LOW)
        elif state == 'toggle':
            current = GPIO.input(EXPOSURE_LIGHT_PIN)
            GPIO.output(EXPOSURE_LIGHT_PIN, not current)
            if not current and config.AUTO_LIGHT_OFF:  # Turning on
                threading.Timer(config.MAX_EXPOSURE_DURATION, lambda: GPIO.output(EXPOSURE_LIGHT_PIN, GPIO.LOW)).start()
        
        light_state = GPIO.input(EXPOSURE_LIGHT_PIN) == GPIO.HIGH
        
        # Emit light state change via Socket.IO
        socketio.emit('light_changed', {
            "exposure_light": light_state,
            "timestamp": time.time()
        })
        
        return jsonify({
            "status": "success",
            "light_state": "on" if light_state else "off",
            "auto_off_seconds": config.MAX_EXPOSURE_DURATION if light_state and config.AUTO_LIGHT_OFF else None
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get system status"""
    return jsonify({
        "status": "online",
        "exposure_light": "on" if GPIO.input(EXPOSURE_LIGHT_PIN) else "off",
        "readings_count": len(readings_buffer),
        "timestamp": datetime.now().isoformat(),
        "sensors": {
            "electrical": True,
            "temperature_humidity": env_sensor is not None,
            "camera": True
        },
        "environment": current_environment if current_environment["temperature"] is not None else None
    })

if __name__ == '__main__':
    # Start electrical reading thread
    reader_thread = threading.Thread(target=read_electrical_data, daemon=True)
    reader_thread.start()
    
    # Start environmental reading thread (generates mock data if no sensor)
    if config.ENABLE_DHT_SENSOR:
        env_thread = threading.Thread(target=read_environment_data, daemon=True)
        env_thread.start()
    
    # Start Socket.IO emitter thread if enabled
    if config.ENABLE_WEBSOCKETS:
        emitter_thread = threading.Thread(target=emit_realtime_data, daemon=True)
        emitter_thread.start()
    
    # Run Flask app with Socket.IO
    try:
        socketio.run(app, host=config.SERVER_HOST, port=config.SERVER_PORT, debug=config.DEBUG_MODE, allow_unsafe_werkzeug=True)
    finally:
        GPIO.cleanup()
        if usb_camera:
            usb_camera.release()
            print("USB camera released")
        # Only DHT sensors have exit() method, SHT31 doesn't need cleanup
        if env_sensor and SENSOR_TYPE != 'SHT31':
            try:
                env_sensor.exit()
            except:
                pass
        if arduino_serial and arduino_serial.is_open:
            arduino_serial.close()
            print("Serial port closed")
        # Turn off ring light on shutdown
        turn_ring_light_off()
