# sLLM API

Flask API server for the Slime Mould Monitor.

## Development Setup

### Local Development (macOS/Windows)

For local development, use the development requirements file which excludes Raspberry Pi-specific packages:

```bash
cd api
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
```

This installs all the core dependencies except:
- `RPi.GPIO` (GPIO control - Pi only)
- `picamera2` (Raspberry Pi camera - Pi only)
- `adafruit-circuitpython-*` packages (CircuitPython - Pi only)

The code should handle missing Pi-specific imports gracefully.

### Raspberry Pi Setup

On the Raspberry Pi, install the full requirements:

```bash
cd api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

This installs all packages including Pi-specific hardware libraries.

## Running the API

```bash
# Activate virtual environment
source venv/bin/activate

# Run the API
python app.py
# or
python app_minimal.py
```

## Configuration

Copy `config_template.py` to `config.py` and customize:

```bash
cp config_template.py config.py
nano config.py
```

## Deployment

The deployment script (`scripts/deploy.sh`) automatically:
1. Creates a virtual environment at `/var/www/sllm/api/venv`
2. Installs all dependencies from `requirements.txt`
3. Sets up the systemd service

