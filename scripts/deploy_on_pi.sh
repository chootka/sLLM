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
# DEPLOY_DIR can be overridden via environment variable (set in config.sh on local machine)
# When running deploy_to_pi.sh, it will pass this as an environment variable
DEPLOY_DIR="${DEPLOY_DIR:-/var/www/sllm}"
FRONTEND_DIR="$DEPLOY_DIR/frontend"
API_DIR="$DEPLOY_DIR/api"
NGINX_CONF="/etc/nginx/sites-available/sllm.visceral.systems"

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    IS_LINUX=true
    WEB_USER="www-data"
    WEB_GROUP="www-data"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    IS_LINUX=false
    WEB_USER=$(whoami)
    WEB_GROUP=$(id -gn)
    echo "⚠️  Running on macOS - this script is designed for Raspberry Pi deployment"
    echo "   Some operations will be skipped or adapted for macOS"
else
    IS_LINUX=false
    WEB_USER=$(whoami)
    WEB_GROUP=$(id -gn)
fi

# Check if running as root or with sudo (only required on Linux)
if [ "$IS_LINUX" = true ] && [ "$EUID" -ne 0 ]; then 
    echo "Please run with sudo on Linux"
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

# Build and copy frontend files
echo "Building frontend..."
cd "$PROJECT_ROOT/frontend"
if [ -f "package.json" ]; then
    # Install npm dependencies if node_modules doesn't exist
    if [ ! -d "node_modules" ]; then
        echo "Installing npm dependencies..."
        npm install
    fi
    # Build the frontend
    echo "Running Vite build..."
    npm run build
    # Copy built files
    echo "Copying built frontend files..."
    cp -r dist/* $FRONTEND_DIR/
else
    # Fallback: copy frontend files directly if no package.json
    echo "No package.json found, copying frontend files directly..."
    cp -r "$PROJECT_ROOT/frontend"/* $FRONTEND_DIR/
fi
if [ "$IS_LINUX" = true ]; then
    chown -R $WEB_USER:$WEB_GROUP $FRONTEND_DIR
fi
chmod -R 755 $FRONTEND_DIR

# Copy API files
echo "Copying API files..."
cd "$PROJECT_ROOT"
if [ -d "api" ]; then
    if ! command -v rsync >/dev/null 2>&1; then
        echo "❌ rsync is required for deployment"
        exit 1
    fi
    # --delete so files removed from the repo also leave the deployment; that
    # is the whole point of a deploy step rather than a copy. Excluded paths
    # are protected from deletion by rsync, so venv and config.py survive it.
    #
    # config.py is excluded in BOTH directions: it is per-machine and
    # untracked, and the deployed copy is the only record of the deployed
    # settings. Overwriting it from the repo is precisely how the two trees
    # drifted before -- the repo said /home/pi/sllm/data, the deployment said
    # /var/www/sllm/data, and a sed further down quietly patched it every
    # time. config_template.py still ships, so a fresh deployment can seed one.
    rsync -av --delete \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='venv' \
        --exclude='config.py' \
        api/ $API_DIR/

    if [ ! -f "$API_DIR/config.py" ]; then
        echo "No config.py at $API_DIR - seeding one from config_template.py"
        cp "$API_DIR/config_template.py" "$API_DIR/config.py"
        chown chootka:chootka "$API_DIR/config.py"
    fi
else
    echo "⚠️  Warning: api directory not found at $PROJECT_ROOT/api"
fi

# The hardware modules live outside api/ and the API imports them by path.
echo "Copying hardware modules..."
mkdir -p "$DEPLOY_DIR/gpio"
rsync -av --delete --exclude='__pycache__' --exclude='*.pyc' \
    gpio/ "$DEPLOY_DIR/gpio/"
if [ "$IS_LINUX" = true ]; then
    chown -R chootka:chootka "$DEPLOY_DIR/gpio"
fi
    if [ "$IS_LINUX" = true ]; then
        # Set ownership to chootka (service runs as chootka, needs write access for GPIO)
        chown -R chootka:chootka $API_DIR
    fi
chmod -R 755 $API_DIR

# config.py no longer needs patching: config_template.py derives DATA_DIR from
# the directory the file itself sits in, so a checkout at ~/sllm and a deploy
# at /var/www/sllm each resolve to their own data directory with no edit.

# Create data directories
echo "Creating data directories..."
DATA_DIR="$DEPLOY_DIR/data"
mkdir -p "$DATA_DIR/images"
mkdir -p "$DATA_DIR/logs"
mkdir -p "$DATA_DIR/readings"
if [ "$IS_LINUX" = true ]; then
    # Service runs as chootka, so data directory needs to be owned by chootka for write access
    chown -R chootka:chootka "$DATA_DIR"
fi
chmod -R 755 "$DATA_DIR"

# Install Python dependencies in virtual environment
echo "Installing Python dependencies..."
cd $API_DIR

# Create virtual environment if it doesn't exist
VENV_PATH="$API_DIR/venv"
if [ ! -d "$VENV_PATH" ]; then
    echo "Creating virtual environment at $VENV_PATH..."
    python3 -m venv "$VENV_PATH"
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

# Check if nginx config template exists (from project root)
cd "$PROJECT_ROOT"
if [ -f "etc/nginx.conf" ]; then
    cp etc/nginx.conf $NGINX_CONF
    echo "✅ Nginx configuration copied from etc/nginx.conf"
elif [ -f "nginx.conf" ]; then
    cp nginx.conf $NGINX_CONF
    echo "✅ Nginx configuration copied from nginx.conf"
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

# Virtual environment path (always use project-local venv)
VENV_PATH="$API_DIR/venv"

# Detect Python version and site-packages path
PYTHON_VERSION=$($VENV_PATH/bin/python -c "import sys; print(f'python{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "python3")
VENV_SITE_PACKAGES="$VENV_PATH/lib/$PYTHON_VERSION/site-packages"

# PYTHONNOUSERSITE=1 prevents Python from finding user site-packages
# PYTHONPATH explicitly set to ONLY venv site-packages to prevent system-wide NumPy conflicts
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
User=chootka
Group=chootka
WorkingDirectory=/home/chootka
Environment="PATH=$VENV_PATH/bin:/usr/bin:/usr/local/bin"
Environment="PYTHONNOUSERSITE=1"
Environment="PYTHONPATH=$VENV_SITE_PACKAGES"
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
User=chootka
Group=chootka
WorkingDirectory=/home/chootka
Environment="PATH=$VENV_PATH/bin:/usr/bin:/usr/local/bin"
Environment="PYTHONNOUSERSITE=1"
Environment="PYTHONPATH=$VENV_SITE_PACKAGES"
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

