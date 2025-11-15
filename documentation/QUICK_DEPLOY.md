# Quick Deployment Steps

Since you have Tailscale and DNS set up, here's the quick deployment process:

## Step 1: Transfer Files to Pi

From your dev machine (where you are now), transfer files to the Pi:

```bash
# Make sure you're in the project directory
cd /Users/sarah/Documents/_projects/sLLM/dev/sLLM

# Transfer frontend files
scp -r frontend/* pi@100.85.144.126:/tmp/sllm-frontend/

# Transfer API files
scp -r api/* pi@100.85.144.126:/tmp/sllm-api/

# Transfer nginx config
scp nginx.conf pi@100.85.144.126:/tmp/nginx-sllm.conf
```

## Step 2: SSH into Pi and Deploy

```bash
# SSH into your Pi
ssh pi@100.85.144.126
```

Then on the Pi, run these commands:

```bash
# Create directories
sudo mkdir -p /var/www/sllm/frontend
sudo mkdir -p /var/www/sllm/api

# Move frontend files
sudo mv /tmp/sllm-frontend/* /var/www/sllm/frontend/
sudo chown -R www-data:www-data /var/www/sllm/frontend
sudo chmod -R 755 /var/www/sllm/frontend

# Move API files
sudo mv /tmp/sllm-api/* /var/www/sllm/api/
sudo chown -R www-data:www-data /var/www/sllm/api
sudo chmod -R 755 /var/www/sllm/api

# Install Python dependencies
cd /var/www/sllm/api
sudo pip3 install -r requirements.txt

# Setup nginx config
sudo cp /tmp/nginx-sllm.conf /etc/nginx/sites-available/sllm.visceral.systems
sudo ln -s /etc/nginx/sites-available/sllm.visceral.systems /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Step 3: Configure API

```bash
# Copy config template
cd /var/www/sllm/api
sudo cp config_template.py config.py
sudo nano config.py
# Edit settings as needed
```

## Step 4: Setup Flask API Service

```bash
# Create systemd service
sudo nano /etc/systemd/system/sllm-api.service
```

Add this content:

```ini
[Unit]
Description=sLLM Flask API Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/sllm/api
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 /var/www/sllm/api/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable sllm-api
sudo systemctl start sllm-api
sudo systemctl status sllm-api
```

## Step 5: Test

```bash
# Test API
curl http://localhost:5000/api/status

# Test via Funnel URL
curl https://sllm.tailf7c7fb.ts.net/api/status

# Test via your domain (after DNS propagates)
curl https://sllm.visceral.systems/api/status
```

## Step 6: Fix Permissions (if needed)

```bash
# GPIO permissions
sudo usermod -a -G gpio www-data

# Camera permissions
sudo usermod -a -G video www-data

# Reboot if needed
sudo reboot
```

