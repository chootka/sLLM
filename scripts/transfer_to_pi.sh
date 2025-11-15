#!/bin/bash
# Setup script - Clone/pull repository on Raspberry Pi and prepare for deployment

set -e

# Configuration
PI_USER="chootka"
PI_IP="100.85.144.126"
PI_DIR="/home/chootka/sllm"
REPO_URL="git@github.com:chootka/sLLM.git"

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
ssh ${PI_USER}@${PI_IP} "chmod +x ${PI_DIR}/scripts/deploy.sh"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. SSH into your Pi:"
echo "   ssh ${PI_USER}@${PI_IP}"
echo ""
echo "2. Run the deploy script:"
echo "   cd ${PI_DIR}"
echo "   sudo ./scripts/deploy.sh"
echo ""
echo "For future updates, just run on Pi:"
echo "   cd ${PI_DIR} && git pull && sudo ./scripts/deploy.sh"
echo ""

