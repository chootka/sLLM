# Deployment Guide for Raspberry Pi 5

This guide covers deploying sLLM to your Raspberry Pi 5 using Tailscale for secure remote access.

## Prerequisites

- Raspberry Pi 5 with slime mold monitoring hardware
- Tailscale account (free at https://tailscale.com)
- Optional: Custom domain (e.g., `sllm.visceral.systems`) if you want to use your own domain name
- Optional: Cloudflare account if using custom domain with Tailscale Funnel

## Step 1: Verify Tailscale Setup

**If you already have Tailscale installed and connected, you can skip this step!**

Your Pi's Tailscale IP: `100.85.144.126`

You can access your Pi from anywhere using this IP. To verify Tailscale is working:

```bash
# Check Tailscale status
sudo tailscale status

# Verify your IP
sudo tailscale ip -4
# Should show: 100.85.144.126
```

**If you need to set up Tailscale**, see `TAILSCALE_SETUP.md` for detailed step-by-step instructions.

## Step 2: Setup Public Web Access

For public web access, you have three options:

### Option A: Use Tailscale Funnel (Recommended - Simplest)

Tailscale Funnel makes your service publicly accessible without port forwarding:

```bash
# Enable Funnel to proxy to nginx on port 80
sudo tailscale funnel --bg http://127.0.0.1:80
```

After running this command, Tailscale will display a public URL. Your Funnel URL will be something like:
```
https://sllm.tailf7c7fb.ts.net
```

**Advantages:**
- Works immediately - no DNS or port forwarding needed
- SSL/HTTPS handled automatically by Tailscale
- No router configuration required
- Accessible from anywhere on the internet

**Note**: Funnel makes your service public - ensure your security is configured properly!

### Option B: Use Custom Domain with Cloudflare

If you want to use your custom domain (`sllm.visceral.systems`) with proper SSL:

1. **Set up Tailscale Funnel** (as in Option A)
2. **Add your domain to Cloudflare**
3. **In Cloudflare DNS**, create a CNAME record:
   - Name: `sllm`
   - Target: `sllm.tailf7c7fb.ts.net`
   - Proxy status: **Proxied** (orange cloud) - this is important!
4. Cloudflare will handle SSL for your custom domain and proxy to the Tailscale URL

**Result**: `https://sllm.visceral.systems` will work with proper SSL certificates.

### Option C: Use Port Forwarding + Public DNS

If you have a public IP and can configure port forwarding:

1. Point `sllm.visceral.systems` DNS to your public IP (A or AAAA record for IPv6)
2. Configure port forwarding on your router (ports 80 and 443)
3. Set up SSL certificate with Let's Encrypt (see Step 5)
4. Use Tailscale for secure admin/SSH access only

## Step 3: Deploy Frontend and API

### 3.1 Create Directories

```bash
sudo mkdir -p /var/www/sllm/{frontend,api}
```

### 3.2 Copy Files

```bash
# Copy frontend
sudo cp -r frontend/* /var/www/sllm/frontend/
sudo chown -R www-data:www-data /var/www/sllm/frontend
sudo chmod -R 755 /var/www/sllm/frontend

# Copy API
sudo cp -r api/* /var/www/sllm/api/
sudo chown -R www-data:www-data /var/www/sllm/api
sudo chmod -R 755 /var/www/sllm/api
```

### 3.3 Install Python Dependencies

```bash
cd /var/www/sllm/api
sudo pip3 install -r requirements.txt
```

### 3.4 Configure API

```bash
cd /var/www/sllm/api
sudo cp config_template.py config.py
sudo nano config.py
```

Update settings as needed.

## Step 4: Setup Nginx

### 4.1 Install Nginx (if not already installed)

```bash
sudo apt update
sudo apt install nginx
```

### 4.2 Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/sllm.visceral.systems
```

Add this configuration:

**If using Tailscale Funnel (Option A or B):**

```nginx
# Nginx configuration for sllm.visceral.systems
# HTTP-only version (SSL handled by Tailscale Funnel)

server {
    listen 80;
    listen [::]:80;
    server_name sllm.visceral.systems;

    # Root directory for static files
    root /var/www/sllm/frontend;
    index index.html;

    # Logging
    access_log /var/log/nginx/sllm.access.log;
    error_log /var/log/nginx/sllm.error.log;

    # Serve static frontend files
    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }

    # Proxy API requests to Flask backend
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Proxy Socket.IO requests
    location /socket.io/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

**If using Port Forwarding (Option C), add an HTTPS server block:**

```nginx
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name sllm.visceral.systems;

    # SSL configuration (get certificate in Step 5)
    ssl_certificate /etc/letsencrypt/live/sllm.visceral.systems/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sllm.visceral.systems/privkey.pem;
    
    # SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # ... (same location blocks as HTTP server above)
}
```

### 4.3 Enable Site

```bash
sudo ln -s /etc/nginx/sites-available/sllm.visceral.systems /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Step 5: Setup SSL Certificate

### If using Tailscale Funnel (Option A or B)

SSL is handled automatically by Tailscale - no certificate setup needed! Your site will be accessible at `https://sllm.tailf7c7fb.ts.net` (or via Cloudflare at `https://sllm.visceral.systems` if you set that up).

### If using Port Forwarding (Option C): Get Let's Encrypt Certificate

If using port forwarding, get a certificate:

**Prerequisites**: 
- DNS must be pointing to your Pi's public IP
- Port 80 must be accessible from internet (for HTTP-01 challenge)
- Or use DNS-01 challenge if port 80 isn't accessible

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate (make sure DNS is pointing to Pi first!)
sudo certbot --nginx -d sllm.visceral.systems

# If port 80 isn't accessible, use DNS challenge:
sudo certbot certonly --manual --preferred-challenges dns -d sllm.visceral.systems
```

This will automatically update your nginx config with the certificate paths.

### Option C: Copy Certificate from Other Server

If you already have a valid certificate on another server:

```bash
# On the other server, copy the certificate using Tailscale IP
sudo scp -r /etc/letsencrypt/live/sllm.visceral.systems pi@100.85.144.126:/tmp/

# On the Pi, move it to the right place
sudo mkdir -p /etc/letsencrypt/live/sllm.visceral.systems
sudo mv /tmp/sllm.visceral.systems/* /etc/letsencrypt/live/sllm.visceral.systems/
sudo chown -R root:root /etc/letsencrypt/live/sllm.visceral.systems
```

**Note**: Replace `100.85.144.126` with your actual Tailscale IP if different.

## Step 6: Setup Flask API Service

### 6.1 Create Systemd Service

```bash
sudo nano /etc/systemd/system/sllm-api.service
```

Add:

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

### 6.2 Enable and Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable sllm-api
sudo systemctl start sllm-api
sudo systemctl status sllm-api
```

## Step 7: Configure Firewall

### On Raspberry Pi:

```bash
# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Check status
sudo ufw status
```

### On Your Router (Port Forwarding):

**Only needed if using Option C (Port Forwarding) from Step 2:**

1. Log into your router's admin panel
2. Find "Port Forwarding" or "Virtual Server" settings
3. Add rules:
   - **External Port 80** → **Internal IP** (Pi's local IP) **Port 80**
   - **External Port 443** → **Internal IP** (Pi's local IP) **Port 443**
4. Save and apply

**Security Note**: Consider using a non-standard port for SSH (22) and disabling it from external access if not needed.

**If using Tailscale Funnel (Option A or B)**: Skip port forwarding - it's not needed! Tailscale handles everything.

## Step 8: Test

1. **Test API directly on Pi:**
   ```bash
   curl http://localhost:5000/api/status
   ```

2. **Test via Tailscale IP (from any device with Tailscale):**
   ```bash
   curl http://100.85.144.126:5000/api/status
   # Or via nginx:
   curl http://100.85.144.126/api/status
   ```

3. **Test via Tailscale Funnel URL:**
   ```bash
   curl https://sllm.tailf7c7fb.ts.net/api/status
   ```

4. **Test via custom domain (if using Cloudflare):**
   ```bash
   curl https://sllm.visceral.systems/api/status
   ```

5. **Open in browser:**
   - Via Tailscale IP: `http://100.85.144.126` (from devices with Tailscale)
   - Via Funnel URL: `https://sllm.tailf7c7fb.ts.net` (public access)
   - Via custom domain: `https://sllm.visceral.systems` (if using Cloudflare or port forwarding)

## Troubleshooting

### GPIO Permissions
```bash
sudo usermod -a -G gpio www-data
sudo reboot
```

### Camera Permissions
```bash
sudo usermod -a -G video www-data
sudo reboot
```

### Check Service Logs
```bash
sudo journalctl -u sllm-api -f
```

### Check Nginx Logs
```bash
sudo tail -f /var/log/nginx/sllm.error.log
sudo tail -f /var/log/nginx/sllm.access.log
```

### Restart Services
```bash
sudo systemctl restart sllm-api
sudo systemctl restart nginx
```

