#!/bin/bash
# Deployment script for sLLM on Raspberry Pi 5
# Run from the git repository root directory

set -e

echo "🦠 Deploying sLLM to Raspberry Pi 5..."

# Get the script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Change to project root
cd "$PROJECT_ROOT"

# Configuration
DEPLOY_DIR="/var/www/sllm"
FRONTEND_DIR="$DEPLOY_DIR/frontend"
API_DIR="$DEPLOY_DIR/api"
NGINX_CONF="/etc/nginx/sites-available/sllm.visceral.systems"

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "Please run with sudo"
    exit 1
fi

# Check if we're in the right directory
if [ ! -d "frontend" ] || [ ! -d "api" ]; then
    echo "❌ Error: frontend/ or api/ directory not found"
    echo "   Current directory: $(pwd)"
    echo "   Please run this script from the project root"
    exit 1
fi

# Create deployment directories
echo "Creating deployment directories..."
mkdir -p $FRONTEND_DIR
mkdir -p $API_DIR

# Copy frontend files
echo "Copying frontend files..."
cp -r frontend/* $FRONTEND_DIR/
chown -R www-data:www-data $FRONTEND_DIR
chmod -R 755 $FRONTEND_DIR

# Copy API files
echo "Copying API files..."
cp -r api/* $API_DIR/
chown -R www-data:www-data $API_DIR
chmod -R 755 $API_DIR

# Install Python dependencies in virtual environment
echo "Installing Python dependencies..."
cd $API_DIR

# Use existing virtual environment
VENV_PATH="/home/chootka/slime_env"
if [ ! -d "$VENV_PATH" ]; then
    echo "⚠️  Virtual environment not found at $VENV_PATH"
    echo "   Creating new virtual environment at $API_DIR/venv..."
    python3 -m venv "$API_DIR/venv"
    VENV_PATH="$API_DIR/venv"
fi

# Activate virtual environment and install dependencies
echo "Using virtual environment: $VENV_PATH"
source "$VENV_PATH/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# Setup nginx configuration
echo "Setting up nginx configuration..."
if [ -f "$NGINX_CONF" ]; then
    echo "Backing up existing nginx configuration..."
    cp $NGINX_CONF "${NGINX_CONF}.backup.$(date +%Y%m%d_%H%M%S)"
fi

# Check if nginx config template exists
if [ -f "etc/nginx.conf" ]; then
    cp etc/nginx.conf $NGINX_CONF
elif [ -f "nginx.conf" ]; then
    cp nginx.conf $NGINX_CONF
else
    echo "⚠️  nginx.conf not found. Please create nginx configuration manually."
    echo "   Expected location: etc/nginx.conf"
    echo "   See documentation for nginx configuration example."
fi

# Enable site if not already enabled
NGINX_ENABLED="/etc/nginx/sites-enabled/$(basename $NGINX_CONF)"
if [ ! -L "$NGINX_ENABLED" ]; then
    ln -s $NGINX_CONF $NGINX_ENABLED
fi

# Test nginx configuration
echo "Testing nginx configuration..."
if nginx -t 2>/dev/null; then
    echo "✅ Nginx configuration test passed"
    read -p "Reload nginx now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        systemctl reload nginx
        echo "✅ Nginx reloaded"
    fi
else
    echo "⚠️  Nginx configuration test failed or nginx not installed"
    echo "   Please install nginx and configure manually:"
    echo "   sudo apt install nginx"
    echo "   See DEPLOYMENT.md for configuration"
fi

# Determine virtual environment path
VENV_PATH="/home/chootka/slime_env"
if [ ! -d "$VENV_PATH" ]; then
    VENV_PATH="$API_DIR/venv"
fi

# Setup Flask API service
if [ -f "/etc/systemd/system/sllm-api.service" ]; then
    echo "Updating Flask API service to use virtual environment..."
    
    # Update service file to use venv
    cat > /tmp/sllm-api.service <<EOF
[Unit]
Description=sLLM Flask API Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=$API_DIR
Environment="PATH=$VENV_PATH/bin:/usr/bin:/usr/local/bin"
ExecStart=$VENV_PATH/bin/python $API_DIR/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    cp /tmp/sllm-api.service /etc/systemd/system/
    systemctl daemon-reload
    echo "Restarting Flask API service..."
    systemctl restart sllm-api
else
    echo "Setting up Flask API systemd service..."
    
    # Create service file
    cat > /tmp/sllm-api.service <<EOF
[Unit]
Description=sLLM Flask API Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=$API_DIR
Environment="PATH=$VENV_PATH/bin:/usr/bin:/usr/local/bin"
ExecStart=$VENV_PATH/bin/python $API_DIR/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    cp /tmp/sllm-api.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable sllm-api
    systemctl start sllm-api
    echo "✅ Flask API service started"
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Verify Tailscale is working:"
echo "   sudo tailscale status"
echo "   Your Tailscale IP: 100.85.144.126"
echo "   (If not set up, see TAILSCALE_SETUP.md)"
echo "2. For public web access, choose one:"
echo "   - Option A: Use Tailscale Funnel (sudo tailscale funnel 80)"
echo "   - Option B: Use regular DNS + port forwarding"
echo "3. Setup SSL certificate:"
echo "   - If using Tailscale Funnel: SSL is automatic!"
echo "   - If using regular DNS: sudo certbot --nginx -d sllm.visceral.systems"
echo "   - OR copy existing cert from other server"
echo "4. Configure API:"
echo "   sudo nano $API_DIR/config.py"
echo "5. Check services:"
echo "   sudo systemctl status sllm-api"
echo "   sudo systemctl status nginx"
echo "6. Test:"
echo "   Via Tailscale IP: curl http://100.85.144.126/api/status"
echo "   Via domain: curl https://sllm.visceral.systems/api/status"

