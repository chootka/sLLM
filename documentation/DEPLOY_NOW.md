# Quick Deployment - Run This Now!

## Step 1: Transfer Everything to Pi

From your dev machine (where you are now), run:

```bash
# Make sure you're in the project directory
cd /Users/sarah/Documents/_projects/sLLM/dev/sLLM

# Transfer everything to Pi
scp -r frontend api nginx.conf deploy.sh pi@100.85.144.126:/home/pi/sllm-deploy/
```

## Step 2: SSH into Pi and Run Deploy Script

```bash
# SSH into your Pi
ssh pi@100.85.144.126

# Go to the deployment directory
cd /home/pi/sllm-deploy

# Run the deploy script with sudo
sudo ./deploy.sh
```

That's it! The script will:
- ✅ Create directories
- ✅ Copy frontend and API files
- ✅ Install Python dependencies
- ✅ Setup nginx configuration
- ✅ Create and start the Flask API service

## Step 3: Configure API (if needed)

After deployment, you may need to configure the API:

```bash
cd /var/www/sllm/api
sudo cp config_template.py config.py
sudo nano config.py
# Edit GPIO pins, camera settings, etc.
```

## Step 4: Test

```bash
# Test API
curl http://localhost:5000/api/status

# Test via Funnel URL
curl https://sllm.tailf7c7fb.ts.net/api/status

# Open in browser
# Visit: https://sllm.tailf7c7fb.ts.net
```

## Troubleshooting

If you get permission errors:
```bash
# Make deploy.sh executable
chmod +x deploy.sh
```

If nginx config fails:
```bash
# Check nginx is installed
sudo apt install nginx

# Test config manually
sudo nginx -t
```

