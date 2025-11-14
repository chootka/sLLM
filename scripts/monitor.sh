#!/bin/bash
# Setup script for Slime Mold Monitor on Raspberry Pi

echo "Setting up Slime Mold Monitor..."

# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install system dependencies
sudo apt-get install -y python3-pip python3-dev python3-venv
sudo apt-get install -y python3-picamera2
sudo apt-get install -y libatlas-base-dev
# For DHT sensor
sudo apt-get install -y libgpiod2

# Create virtual environment
python3 -m venv ~/slime_env
source ~/slime_env/bin/activate

# Install Python packages
pip install --upgrade pip
pip install flask flask-cors flask-socketio
pip install python-socketio
pip install RPi.GPIO
pip install adafruit-circuitpython-ads1x15
pip install picamera2
pip install numpy

# Install DHT sensor library (optional - for when you have the sensor)
pip install adafruit-circuitpython-dht
# Note: DHT library requires libgpiod2

# Create directories
mkdir -p ~/slime_data/images
mkdir -p ~/slime_data/logs
mkdir -p ~/slime_data/readings

echo "Setup complete! To run the server:"
echo "1. source ~/slime_env/bin/activate"
echo "2. python ~/slime_api.py"
echo ""
echo "Note: DHT sensor support is installed but optional."
echo "The system will run without it if not connected."
