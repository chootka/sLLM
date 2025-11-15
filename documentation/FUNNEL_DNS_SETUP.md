# Setting Up DNS for Tailscale Funnel

This guide explains how to point `sllm.visceral.systems` to your Tailscale Funnel.

## Understanding Tailscale Funnel

When you run `sudo tailscale funnel 80`, Tailscale creates a **public URL** that anyone can access. This URL looks like:
```
https://your-device-name.your-tailnet-name.ts.net
```

**Important**: You cannot point DNS directly to your Tailscale IP (`100.85.144.126`) because:
- That IP is private to your Tailscale network
- Only devices with Tailscale installed and connected can access it
- The Funnel URL is what makes it publicly accessible

## Step-by-Step DNS Setup

### Step 1: Enable Tailscale Funnel

On your Raspberry Pi:

```bash
# Enable Funnel for HTTP
sudo tailscale funnel 80

# Enable Funnel for HTTPS
sudo tailscale funnel 443
```

Tailscale will output something like:
```
Available on the internet:
https://raspberrypi.yourname.ts.net
```

**Copy this URL** - you'll need it for DNS!

### Step 2: Get Your Device Name

If you need to find your device name:

```bash
# Check your Tailscale status
sudo tailscale status

# Or check your hostname
hostname
```

The Funnel URL uses your device's hostname.

### Step 3: Configure DNS CNAME Record

In your DNS provider (where you manage `visceral.systems`):

1. **Create a CNAME record:**
   - **Name/Host**: `sllm`
   - **Type**: `CNAME` (not A record!)
   - **Value/Target**: `raspberrypi.yourname.ts.net` (your Funnel URL without `https://`)
   - **TTL**: `3600` or default

2. **Example** (what it looks like in different DNS providers):

   **Cloudflare:**
   - Type: `CNAME`
   - Name: `sllm`
   - Target: `raspberrypi.yourname.ts.net`
   - Proxy status: Can be proxied (orange cloud) or DNS only (grey cloud)

   **Route 53 (AWS):**
   - Record name: `sllm.visceral.systems`
   - Record type: `CNAME`
   - Value: `raspberrypi.yourname.ts.net`

   **Namecheap/GoDaddy/etc:**
   - Host: `sllm`
   - Type: `CNAME Record`
   - Value: `raspberrypi.yourname.ts.net`

### Step 4: Wait for DNS Propagation

DNS changes can take 5-30 minutes (sometimes up to 48 hours, but usually much faster).

Check if it's propagated:
```bash
# Check DNS resolution
dig sllm.visceral.systems +short
# Should show: raspberrypi.yourname.ts.net

# Or use nslookup
nslookup sllm.visceral.systems
```

### Step 5: Test

Once DNS has propagated:

```bash
# Test via your domain
curl https://sllm.visceral.systems/api/status

# Or test the Tailscale URL directly (works immediately)
curl https://raspberrypi.yourname.ts.net/api/status
```

## Troubleshooting

### DNS Not Resolving

1. **Check CNAME record exists:**
   ```bash
   dig sllm.visceral.systems CNAME
   ```

2. **Verify Funnel is enabled:**
   ```bash
   sudo tailscale funnel --status
   ```

3. **Check Funnel URL is correct:**
   - Make sure you're using the exact URL shown by `tailscale funnel`
   - Don't include `https://` in the CNAME value
   - Don't include trailing slashes

### SSL Certificate Issues

If you're using nginx with SSL, you may need to:

1. **Get a certificate for your domain:**
   ```bash
   sudo certbot --nginx -d sllm.visceral.systems
   ```

2. **Or configure nginx to accept the Tailscale certificate** (Funnel handles SSL automatically, but nginx may need configuration)

### Funnel Not Working

1. **Check Funnel status:**
   ```bash
   sudo tailscale funnel --status
   ```

2. **Restart Funnel:**
   ```bash
   sudo tailscale funnel --reset
   sudo tailscale funnel 80
   sudo tailscale funnel 443
   ```

3. **Check nginx is running:**
   ```bash
   sudo systemctl status nginx
   ```

## Alternative: Use Tailscale URL Directly

If you don't want to set up DNS, you can just use the Tailscale Funnel URL directly:
- `https://raspberrypi.yourname.ts.net`

This works immediately and doesn't require any DNS configuration!

## Security Notes

⚠️ **Important**: Tailscale Funnel makes your service publicly accessible to anyone on the internet. Make sure:

1. Your nginx security headers are configured
2. Your API has proper authentication if needed
3. You're not exposing sensitive data
4. Your firewall rules are appropriate

You can disable Funnel anytime:
```bash
sudo tailscale funnel --reset
```

