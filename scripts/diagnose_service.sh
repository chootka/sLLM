#!/bin/bash
# Diagnostic script for sLLM API service
# Run from your local machine - it will SSH into the Pi and run diagnostics

set -e

# Load configuration from config.sh
CONFIG_FILE="$(dirname "$0")/config.sh"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: config.sh not found!"
    exit 1
fi

source "$CONFIG_FILE"

echo "🔍 Diagnosing sLLM API service on ${PI_USER}@${PI_IP}..."
echo ""

# Check service status
echo "=== Service Status ==="
ssh -A ${PI_USER}@${PI_IP} "sudo systemctl status sllm-api --no-pager -l | head -20"
echo ""

# Check recent logs
echo "=== Recent Service Logs (last 50 lines) ==="
ssh -A ${PI_USER}@${PI_IP} "sudo journalctl -u sllm-api -n 50 --no-pager"
echo ""

# Check systemd service file
echo "=== Systemd Service Configuration ==="
ssh -A ${PI_USER}@${PI_IP} "sudo cat /etc/systemd/system/sllm-api.service | grep -A 5 Environment"
echo ""

# Test manual startup
echo "=== Testing Manual Startup (will timeout after 5 seconds) ==="
ssh -A ${PI_USER}@${PI_IP} "timeout 5 sudo -u chootka env PYTHONNOUSERSITE=1 /var/www/sllm/api/venv/bin/python /var/www/sllm/api/app.py 2>&1 | head -30 || echo 'Process started (timeout expected)'"
echo ""

# Check NumPy versions
echo "=== NumPy Version Check ==="
ssh -A ${PI_USER}@${PI_IP} "source /var/www/sllm/api/venv/bin/activate && python -c 'import numpy; print(\"Venv NumPy:\", numpy.__version__, numpy.__file__)' && deactivate"
echo ""

echo "✅ Diagnostics complete!"

