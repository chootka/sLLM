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

# Get script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
API_DIR="$PROJECT_ROOT/api"

# Create virtual environment in project directory
cd "$API_DIR"
python3 -m venv venv
source venv/bin/activate

# Install Python packages from requirements.txt
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "⚠️  requirements.txt not found, installing packages manually..."
    pip install flask flask-cors flask-socketio
    pip install python-socketio
    pip install RPi.GPIO
    pip install adafruit-circuitpython-ads1x15
    pip install picamera2
    pip install numpy
    pip install adafruit-circuitpython-dht
fi

deactivate

# Create data directories in project root
DATA_DIR="$PROJECT_ROOT/data"
mkdir -p "$DATA_DIR/images"
mkdir -p "$DATA_DIR/logs"
mkdir -p "$DATA_DIR/readings"
echo "Created data directories at $DATA_DIR"

echo "Setup complete! To run the server:"
echo "1. cd $API_DIR"
echo "2. source venv/bin/activate"
echo "3. python app.py"
echo ""
echo "Note: DHT sensor support is installed but optional."
echo "The system will run without it if not connected."
