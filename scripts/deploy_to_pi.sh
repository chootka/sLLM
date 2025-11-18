#!/bin/bash
# Remote deployment script - SSHs into Pi, pulls code, and deploys
# Run from your local machine

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
if [ -z "$PI_USER" ] || [ -z "$PI_IP" ] || [ -z "$PI_DIR" ]; then
    echo "❌ Error: Required configuration variables not set in config.sh"
    echo "   Required: PI_USER, PI_IP, PI_DIR"
    exit 1
fi

echo "🚀 Deploying sLLM to Raspberry Pi..."
echo "   Pi: ${PI_USER}@${PI_IP}"
echo "   Project: ${PI_DIR}"
echo ""

# Check if repo exists on Pi and pull/clone
echo "📦 Updating repository on Pi..."
if ssh -o ConnectTimeout=5 -A ${PI_USER}@${PI_IP} "[ -d ${PI_DIR}/.git ]" 2>/dev/null; then
    echo "   Pulling latest changes..."
    ssh -A ${PI_USER}@${PI_IP} "cd ${PI_DIR} && git pull"
else
    echo "❌ Repository not found on Pi!"
    echo "   Checking if directory exists..."
    ssh -A ${PI_USER}@${PI_IP} "ls -la ${PI_DIR} 2>&1 || echo 'Directory does not exist'"
    echo ""
    echo "   Debug: Testing SSH connection..."
    ssh -A ${PI_USER}@${PI_IP} "echo 'SSH connection successful' && pwd && ls -la ${PI_DIR}/.git 2>&1 || echo '.git directory not found'"
    echo ""
    echo "   Please run scripts/transfer_to_pi.sh first to clone the repository"
    exit 1
fi

# Run deploy script on Pi
echo ""
echo "🔧 Running deployment on Pi..."
ssh -t -A ${PI_USER}@${PI_IP} "cd ${PI_DIR} && sudo ./scripts/deploy_on_pi.sh"

echo ""
echo "✅ Deployment complete!"

