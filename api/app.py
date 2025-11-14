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
from datetime import datetime
from collections import deque
from flask import Flask, jsonify, send_file, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import RPi.GPIO as GPIO
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
import numpy as np

# Load configuration
try:
    import config
    print("Loaded configuration from config.py")
except ImportError:
    print("Warning: config.py not found. Using default configuration.")
    print("Copy config_template.py to config.py and customize as needed.")
    import config_template as config

# Temperature/Humidity sensor support (when available)
DHT_AVAILABLE = False
if config.ENABLE_DHT_SENSOR:
    try:
        import adafruit_dht
        DHT_AVAILABLE = True
    except ImportError:
        print("DHT sensor library not installed. Temperature/humidity monitoring disabled.")

app = Flask(__name__)
CORS(app)  # Enable CORS for web frontend
socketio = SocketIO(app, cors_allowed_origins="*")  # Enable Socket.IO with CORS

# Configuration from config.py
RING_LIGHT_PIN = config.RING_LIGHT_PIN
EXPOSURE_LIGHT_PIN = config.EXPOSURE_LIGHT_PIN
DHT_PIN = config.DHT_PIN
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
GPIO.setmode(GPIO.BCM)
GPIO.setup(RING_LIGHT_PIN, GPIO.OUT)
GPIO.setup(EXPOSURE_LIGHT_PIN, GPIO.OUT)
GPIO.output(RING_LIGHT_PIN, GPIO.LOW)
GPIO.output(EXPOSURE_LIGHT_PIN, GPIO.LOW)

# Initialize ADC (ADS1115)
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c, address=config.ADC_ADDRESS)
ads.gain = config.ADC_GAIN  # Set gain from config
# Create differential input between A0 and A1
chan = AnalogIn(ads, ADS.P0, ADS.P1)

# Initialize DHT sensor (if available)
dht_sensor = None
if DHT_AVAILABLE:
    try:
        # Map config pin number to board pin
        dht_board_pin = getattr(board, f'D{DHT_PIN}')
        dht_sensor = adafruit_dht.DHT22(dht_board_pin)
        print(f"DHT22 sensor initialized on GPIO {DHT_PIN}")
    except Exception as e:
        print(f"Failed to initialize DHT sensor: {e}")
        dht_sensor = None

# Initialize camera
picam2 = Picamera2()
camera_config = picam2.create_still_configuration(main={"size": config.CAMERA_RESOLUTION})
picam2.configure(camera_config)

def read_electrical_data():
    """Continuously read electrical data from the slime mold"""
    global current_reading
    
    while True:
        try:
            # Read voltage from ADC
            voltage = chan.voltage
            timestamp = time.time()
            
            reading = {
                "timestamp": timestamp,
                "value": voltage,
                "datetime": datetime.now().isoformat()
            }
            
            with readings_lock:
                readings_buffer.append(reading)
                current_reading = reading
            
            time.sleep(1.0 / config.ELECTRICAL_SAMPLE_RATE)  # Read at configured rate
            
        except Exception as e:
            print(f"Error reading ADC: {e}")
            time.sleep(1)

def read_environment_data():
    """Read temperature and humidity data"""
    global current_environment
    
    if not dht_sensor:
        return
    
    while True:
        try:
            temperature = dht_sensor.temperature
            humidity = dht_sensor.humidity
            
            if temperature is not None and humidity is not None:
                current_environment = {
                    "temperature": temperature,
                    "humidity": humidity,
                    "timestamp": time.time(),
                    "datetime": datetime.now().isoformat()
                }
        except RuntimeError as e:
            # DHT sensors can be flaky, this is normal
            pass
        except Exception as e:
            print(f"Error reading DHT sensor: {e}")
        
        time.sleep(config.DHT_READ_INTERVAL)  # DHT22 read interval from config

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

@app.route('/api/capture-image', methods=['POST'])
def capture_image():
    """Capture an image with the microscope camera"""
    try:
        # Turn on ring light
        GPIO.output(RING_LIGHT_PIN, GPIO.HIGH)
        time.sleep(config.RING_LIGHT_DELAY)  # Let light stabilize
        
        # Start camera if not already started
        if not picam2.started:
            picam2.start()
            time.sleep(config.CAMERA_WARMUP_TIME)  # Camera warmup
        
        # Capture image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(config.IMAGE_DIR, f"slime_{timestamp}.jpg")
        picam2.capture_file(filename)
        
        # Turn off ring light
        GPIO.output(RING_LIGHT_PIN, GPIO.LOW)
        
        # Emit image capture event
        socketio.emit('image_captured', {
            "filename": os.path.basename(filename),
            "timestamp": time.time()
        })
        
        # Return the image file
        return send_file(filename, mimetype='image/jpeg')
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
            "temperature_humidity": dht_sensor is not None,
            "camera": True
        },
        "environment": current_environment if current_environment["temperature"] is not None else None
    })

if __name__ == '__main__':
    # Start electrical reading thread
    reader_thread = threading.Thread(target=read_electrical_data, daemon=True)
    reader_thread.start()
    
    # Start environmental reading thread if sensor available
    if dht_sensor:
        env_thread = threading.Thread(target=read_environment_data, daemon=True)
        env_thread.start()
    
    # Start Socket.IO emitter thread if enabled
    if config.ENABLE_WEBSOCKETS:
        emitter_thread = threading.Thread(target=emit_realtime_data, daemon=True)
        emitter_thread.start()
    
    # Run Flask app with Socket.IO
    try:
        socketio.run(app, host=config.SERVER_HOST, port=config.SERVER_PORT, debug=config.DEBUG_MODE)
    finally:
        GPIO.cleanup()
        picam2.close()
        if dht_sensor:
            dht_sensor.exit()
