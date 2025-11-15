#!/usr/bin/env python3
"""
Slime Mold Monitor - Minimal version for testing
Works with just gpiozero or falls back to mock mode
"""

import time
import json
import threading
import random
from datetime import datetime
from collections import deque
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# Try to set up GPIO
GPIO_AVAILABLE = False
led = None

try:
    from gpiozero import LED
    # Try to create an LED - this will fail if GPIO not available
    led = LED(18)
    GPIO_AVAILABLE = True
    print("✓ GPIO initialized successfully with gpiozero")
except Exception as e:
    print(f"GPIO not available: {e}")
    print("Running in MOCK mode - no hardware required")

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
MAX_READINGS = 1000
SAMPLE_RATE = 10  # Hz

# Global data storage
readings_buffer = deque(maxlen=MAX_READINGS)
readings_lock = threading.Lock()
current_reading = {"timestamp": 0, "value": 0}
led_state = False

# Simulation variables
mock_base_voltage = 2.5
mock_voltage_variation = 0

def get_simulated_reading():
    """Generate realistic-looking electrical readings"""
    global mock_voltage_variation
    
    # Natural drift
    mock_voltage_variation += random.uniform(-0.02, 0.02)
    mock_voltage_variation = max(-0.5, min(0.5, mock_voltage_variation))  # Clamp
    
    # Base reading with noise
    reading = mock_base_voltage + mock_voltage_variation
    reading += random.uniform(-0.05, 0.05)  # Noise
    
    # LED effect
    if led_state:
        reading += 0.3 + random.uniform(-0.1, 0.1)
    
    return max(0, min(5, reading))  # Clamp to 0-5V

def read_electrical_data():
    """Continuously generate electrical readings"""
    global current_reading
    
    while True:
        try:
            voltage = get_simulated_reading()
            
            timestamp = time.time()
            reading = {
                "timestamp": timestamp,
                "value": voltage,
                "datetime": datetime.now().isoformat()
            }
            
            with readings_lock:
                readings_buffer.append(reading)
                current_reading = reading
            
            # Emit via Socket.IO
            socketio.emit('reading_update', reading)
            
            time.sleep(1.0 / SAMPLE_RATE)
            
        except Exception as e:
            print(f"Error in reading loop: {e}")
            time.sleep(1)

@app.route('/')
def serve_frontend():
    return send_file('../frontend/index.html')

#@app.route('/')
#def index():
#    """Serve a simple test page"""
#    return """
#    <!DOCTYPE html>
#    <html>
#    <head>
#        <title>Slime Monitor Test</title>
#    </head>
#    <body>
#        <h1>Slime Monitor API Running</h1>
#        <p>GPIO Available: """ + str(GPIO_AVAILABLE) + """</p>
#        <p>Access the frontend at index.html</p>
#        <p>API Endpoints:</p>
#        <ul>
#            <li>GET /api/status</li>
#            <li>GET /api/readings</li>
#            <li>POST /api/led</li>
#        </ul>
#    </body>
#    </html>
#    """

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

@app.route('/api/led', methods=['POST'])
def control_led():
    """Control the LED"""
    global led_state
    
    try:
        data = request.get_json()
        state = data.get('state', 'toggle')
        
        if state == 'on':
            led_state = True
            if GPIO_AVAILABLE and led:
                led.on()
        elif state == 'off':
            led_state = False
            if GPIO_AVAILABLE and led:
                led.off()
        elif state == 'toggle':
            led_state = not led_state
            if GPIO_AVAILABLE and led:
                if led_state:
                    led.on()
                else:
                    led.off()
        
        # Emit state change
        socketio.emit('led_changed', {
            "led_state": led_state,
            "timestamp": time.time()
        })
        
        return jsonify({
            "status": "success",
            "led_state": "on" if led_state else "off",
            "gpio_available": GPIO_AVAILABLE
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get system status"""
    return jsonify({
        "status": "online",
        "led_state": "on" if led_state else "off",
        "readings_count": len(readings_buffer),
        "timestamp": datetime.now().isoformat(),
        "gpio_available": GPIO_AVAILABLE,
        "mock_mode": not GPIO_AVAILABLE,
        "current_reading": current_reading["value"] if current_reading["timestamp"] > 0 else 0
    })

@app.route('/api/trigger-light', methods=['POST'])
def trigger_light():
    """Alias for LED control to match frontend"""
    return control_led()

@app.route('/api/capture-image', methods=['POST'])
def capture_image():
    """Stub for image capture - not implemented in minimal version"""
    return jsonify({
        "status": "success",
        "message": "Image capture not available in minimal version"
    })

@app.route('/api/config', methods=['GET'])
def get_config():
    """Stub for config endpoint"""
    return jsonify({
        "image_capture_interval": 300,
        "max_exposure_duration": 30,
        "mock_mode": not GPIO_AVAILABLE
    })

@app.route('/api/environment', methods=['GET'])
def get_environment():
    """Stub for environmental data"""
    return jsonify({
        "temperature": None,
        "humidity": None,
        "timestamp": 0
    })

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print(f"Client connected: {request.sid}")
    emit('status_update', {
        "led_state": led_state,
        "timestamp": time.time(),
        "gpio_available": GPIO_AVAILABLE
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print(f"Client disconnected: {request.sid}")

if __name__ == '__main__':
    print("\n" + "="*50)
    print("SLIME MOLD MONITOR - Starting Up")
    print("="*50)
    
    if GPIO_AVAILABLE:
        print("✓ Running with REAL GPIO")
        print(f"✓ LED connected to GPIO 18")
    else:
        print("✓ Running in MOCK mode")
        print("✓ Simulating electrical readings")
        print("✓ LED control will be simulated")
    
    print("\nStarting data collection thread...")
    reader_thread = threading.Thread(target=read_electrical_data, daemon=True)
    reader_thread.start()
    
    print("Starting web server on http://0.0.0.0:5000")
    print("\nAccess the API at:")
    print("  http://YOUR_PI_IP:5000/api/status")
    print("\nReady to go! 🦠")
    print("-"*50 + "\n")
    
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    finally:
        if GPIO_AVAILABLE and led:
            led.close()
