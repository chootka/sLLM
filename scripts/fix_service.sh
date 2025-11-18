#!/bin/bash
# Quick fix script to update systemd service with PYTHONPATH
# Run on the Pi

VENV_PATH="/var/www/sllm/api/venv"
PYTHON_VERSION=$($VENV_PATH/bin/python -c "import sys; print(f'python{sys.version_info.major}.{sys.version_info.minor}')")
VENV_SITE_PACKAGES="$VENV_PATH/lib/$PYTHON_VERSION/site-packages"

echo "Updating systemd service with PYTHONPATH=$VENV_SITE_PACKAGES"

# Check if PYTHONPATH is already set
if grep -q "PYTHONPATH" /etc/systemd/system/sllm-api.service; then
    echo "PYTHONPATH already set, updating..."
    sudo sed -i "s|Environment=\"PYTHONPATH=.*\"|Environment=\"PYTHONPATH=$VENV_SITE_PACKAGES\"|" /etc/systemd/system/sllm-api.service
else
    echo "Adding PYTHONPATH..."
    sudo sed -i "/Environment=\"PYTHONNOUSERSITE=1\"/a Environment=\"PYTHONPATH=$VENV_SITE_PACKAGES\"" /etc/systemd/system/sllm-api.service
fi

sudo systemctl daemon-reload
sudo systemctl restart sllm-api
sleep 2
sudo systemctl status sllm-api --no-pager -l | head -20

