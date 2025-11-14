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

# Temperature/Humidity sensor support (when available)
try:
    import adafruit_dht
    DHT_AVAILABLE = True
except ImportError:
    DHT_AVAILABLE = False
    print("DHT sensor library not installed. Temperature/humidity monitoring disabled.")

app = Flask(__name__)
CORS(app)  # Enable CORS for web frontend
socketio = SocketIO(app, cors_allowed_origins="*")  # Enable Socket.IO with CORS

# Configuration
RING_LIGHT_PIN = 17  # GPIO pin for ring light
EXPOSURE_LIGHT_PIN = 27  # GPIO pin for exposure light
DHT_PIN = 4  # GPIO pin for DHT22 sensor (when available)
MAX_READINGS = 1000  # Keep last 1000 readings in memory
EMIT_INTERVAL = 0.5  # How often to emit data via Socket.IO (seconds)

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
ads = ADS.ADS1115(i2c)
# Create differential input between A0 and A1
chan = AnalogIn(ads, ADS.P0, ADS.P1)

# Initialize DHT sensor (if available)
dht_sensor = None
if DHT_AVAILABLE:
    try:
        dht_sensor = adafruit_dht.DHT22(board.D4)  # Using GPIO4
        print("DHT22 sensor initialized")
    except Exception as e:
        print(f"Failed to initialize DHT sensor: {e}")
        dht_sensor = None

# Initialize camera
picam2 = Picamera2()
camera_config = picam2.create_still_configuration(main={"size": (1920, 1080)})
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
            
            time.sleep(0.1)  # Read at 10Hz
            
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
        
        time.sleep(2)  # DHT22 has a 2-second minimum read interval

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
        time.sleep(0.5)  # Let light stabilize
        
        # Start camera if not already started
        if not picam2.started:
            picam2.start()
            time.sleep(2)  # Camera warmup
        
        # Capture image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/tmp/slime_{timestamp}.jpg"
        picam2.capture_file(filename)
        
        # Turn off ring light
        GPIO.output(RING_LIGHT_PIN, GPIO.LOW)
        
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
        
        if state == 'on':
            GPIO.output(EXPOSURE_LIGHT_PIN, GPIO.HIGH)
            if duration > 0:
                threading.Timer(duration, lambda: GPIO.output(EXPOSURE_LIGHT_PIN, GPIO.LOW)).start()
        elif state == 'off':
            GPIO.output(EXPOSURE_LIGHT_PIN, GPIO.LOW)
        elif state == 'toggle':
            current = GPIO.input(EXPOSURE_LIGHT_PIN)
            GPIO.output(EXPOSURE_LIGHT_PIN, not current)
        
        light_state = GPIO.input(EXPOSURE_LIGHT_PIN) == GPIO.HIGH
        
        # Emit light state change via Socket.IO
        socketio.emit('light_changed', {
            "exposure_light": light_state,
            "timestamp": time.time()
        })
        
        return jsonify({
            "status": "success",
            "light_state": "on" if light_state else "off"
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
    
    # Start Socket.IO emitter thread
    emitter_thread = threading.Thread(target=emit_realtime_data, daemon=True)
    emitter_thread.start()
    
    # Run Flask app with Socket.IO
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    finally:
        GPIO.cleanup()
        picam2.close()
        if dht_sensor:
            dht_sensor.exit()
