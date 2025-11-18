#!/bin/bash
# Setup script - Clone/pull repository on Raspberry Pi and prepare for deployment

set -e

# Load configuration from config.sh
CONFIG_FILE="$(dirname "$0")/config.sh"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: config.sh not found!"
    echo ""
    echo "Please create scripts/config.sh with your configuration:"
    echo "   cp scripts/config.example.sh scripts/config.sh"
    echo "   # Then edit scripts/config.sh with your values"
    echo ""
    exit 1
fi

source "$CONFIG_FILE"

# Validate required variables
if [ -z "$PI_USER" ] || [ -z "$PI_IP" ] || [ -z "$PI_DIR" ] || [ -z "$REPO_URL" ]; then
    echo "❌ Error: Required configuration variables not set in config.sh"
    echo "   Required: PI_USER, PI_IP, PI_DIR, REPO_URL"
    exit 1
fi

echo "🚀 Setting up sLLM on Raspberry Pi..."
echo "   Pi: ${PI_USER}@${PI_IP}"
echo "   Repo: ${REPO_URL} (SSH)"
echo "   Destination: ${PI_DIR}"
echo ""

# Check if repo exists on Pi
echo "Checking if repository exists on Pi..."
if ssh -o ConnectTimeout=5 ${PI_USER}@${PI_IP} "[ -d ${PI_DIR}/.git ]" 2>/dev/null; then
    echo "📦 Repository exists, pulling latest changes..."
    ssh ${PI_USER}@${PI_IP} "cd ${PI_DIR} && git pull"
else
    echo "📦 Cloning repository using SSH..."
    ssh ${PI_USER}@${PI_IP} "git clone ${REPO_URL} ${PI_DIR}"
fi

# Make deploy script executable on Pi
echo "🔧 Making deploy script executable..."
ssh ${PI_USER}@${PI_IP} "chmod +x ${PI_DIR}/scripts/deploy_on_pi.sh"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. SSH into your Pi:"
echo "   ssh ${PI_USER}@${PI_IP}"
echo ""
echo "2. Run the deploy script:"
echo "   cd ${PI_DIR}"
echo "   sudo ./scripts/deploy_on_pi.sh"
echo ""
echo "For future updates, just run on Pi:"
echo "   cd ${PI_DIR} && git pull && sudo ./scripts/deploy_on_pi.sh"
echo ""

