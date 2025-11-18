#!/bin/bash
# Script to checkout and pull livestream branch on Raspberry Pi
# Run this script on the Pi

set -e

echo "🦠 Checking out livestream branch..."

# Default deploy directory (can be overridden)
DEPLOY_DIR="${DEPLOY_DIR:-/var/www/sllm}"

# Navigate to project directory
if [ ! -d "$DEPLOY_DIR" ]; then
    echo "❌ Error: Project directory not found at $DEPLOY_DIR"
    echo "   Please set DEPLOY_DIR environment variable or ensure project is deployed"
    exit 1
fi

cd "$DEPLOY_DIR"

echo "📂 Current directory: $(pwd)"
echo "🌿 Current branch: $(git branch --show-current)"

# Fetch latest branches from remote
echo "⬇️  Fetching latest branches..."
git fetch origin

# Checkout livestream branch (create if it doesn't exist locally)
echo "🔀 Checking out livestream branch..."
git checkout livestream 2>/dev/null || git checkout -b livestream origin/livestream

# Pull latest changes
echo "⬇️  Pulling latest changes..."
git pull origin livestream

echo "✅ Successfully checked out livestream branch!"
echo "🌿 Current branch: $(git branch --show-current)"
echo "📝 Latest commit: $(git log -1 --oneline)"

