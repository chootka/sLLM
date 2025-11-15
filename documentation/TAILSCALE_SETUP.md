# Tailscale Setup Guide for Raspberry Pi

This guide will walk you through setting up Tailscale on your Raspberry Pi 5 to make it accessible from anywhere without port forwarding.

## What is Tailscale?

Tailscale creates a secure VPN mesh network. Your Pi will get a private IP address (like `100.x.x.x`) that you can access from anywhere, even if you're on a different network. No port forwarding needed!

## Step 1: Sign Up for Tailscale

1. Go to https://tailscale.com
2. Click "Sign Up" (you can use Google, Microsoft, or GitHub account)
3. Complete the signup process
4. You'll be taken to the Tailscale admin console

## Step 2: Install Tailscale on Raspberry Pi

SSH into your Raspberry Pi, then run:

```bash
# Download and run the Tailscale installer
curl -fsSL https://tailscale.com/install.sh | sh
```

This will:
- Detect your Pi's architecture
- Download the appropriate Tailscale package
- Install it automatically

## Step 3: Start Tailscale

```bash
# Start Tailscale
sudo tailscale up
```

You'll see a message like:
```
To authenticate, visit:
	https://login.tailscale.com/a/xxxxx?token=xxxxx
```

## Step 4: Authenticate Your Pi

1. **Copy the URL** from the terminal output
2. **Open it in a web browser** (on any device - your computer, phone, etc.)
3. **Sign in** with your Tailscale account
4. **Approve the device** - you'll see your Raspberry Pi listed
5. Click "Connect" or "Approve"

## Step 5: Verify Connection

Back on your Pi, check the status:

```bash
# Check Tailscale status
sudo tailscale status
```

You should see your Pi listed with a Tailscale IP address (starts with `100.`).

You can also check your IP:

```bash
# Get your Tailscale IP
sudo tailscale ip -4
```

This will show something like `100.64.1.2` - this is your Pi's Tailscale IP address!

## Step 6: Test Access from Another Device

### Option A: Install Tailscale on Your Computer

1. **On your Mac/PC:**
   - Go to https://tailscale.com/download
   - Download and install Tailscale
   - Sign in with the same account
   - Your computer will connect to the same network

2. **Test connection:**
   ```bash
   # From your computer, ping the Pi
   ping 100.64.1.2
   # (Replace with your Pi's actual Tailscale IP)
   ```

### Option B: Use Tailscale Web Interface

1. Go to https://login.tailscale.com/admin/machines
2. You'll see all your devices listed
3. Click on your Raspberry Pi to see its details

## Step 7: Access Your Pi's Services

Now you can access your Pi using its Tailscale IP:

```bash
# SSH to your Pi
ssh pi@100.64.1.2

# Or access web services
# http://100.64.1.2:5000  (Flask API)
# http://100.64.1.2:80    (Nginx, once set up)
```

## Step 8: Setup Tailscale to Start Automatically

Tailscale should already be set up as a service, but verify:

```bash
# Check if Tailscale service is running
sudo systemctl status tailscaled

# Enable it to start on boot (if not already)
sudo systemctl enable tailscaled
```

## Step 9: Configure DNS (Optional but Recommended)

You can use Tailscale's MagicDNS to access your Pi by name instead of IP:

1. **Go to Tailscale Admin Console:**
   - Visit https://login.tailscale.com/admin/dns
   - Enable "MagicDNS"
   - Add a name for your Pi (e.g., `sllm-pi`)

2. **Now you can access by name:**
   ```bash
   ssh pi@sllm-pi
   # or
   http://sllm-pi:5000
   ```

## Step 10: Point Your Domain for Public Web Access

Since you want `sllm.visceral.systems` to be publicly accessible, you need to use **Tailscale Funnel**:

### Use Tailscale Funnel (Required for Public Access)

**Important**: You CANNOT point DNS directly to your Tailscale IP (like `100.85.144.126`) because:
- Tailscale IPs are private and only work within your Tailscale network
- Only devices with Tailscale installed can access Tailscale IPs
- For public web access, you must use Tailscale Funnel

**Setup Tailscale Funnel:**

```bash
# On your Pi, enable Funnel for port 80 (HTTP)
sudo tailscale funnel 80

# Enable Funnel for port 443 (HTTPS)
sudo tailscale funnel 443
```

This will give you a public URL like:
`https://sllm.tailf7c7fb.ts.net`

**Point DNS to Funnel URL:**

In your DNS provider, create a **CNAME record** (not A record!):
- **Name**: `sllm`
- **Type**: `CNAME`
- **Value**: `sllm.tailf7c7fb.ts.net` (your Funnel URL without `https://`)

Example:
```
sllm.visceral.systems  CNAME  sllm.tailf7c7fb.ts.net
```

**Important**: 
- Funnel makes your service public - ensure your security is configured properly!
- The Funnel URL works immediately, even before DNS propagates
- See `FUNNEL_DNS_SETUP.md` for detailed DNS setup instructions

### Alternative: Use Tailscale for Admin Only

If you have a public IP and can configure port forwarding:
- Keep `sllm.visceral.systems` pointing to your public IP (A record)
- Use Tailscale IP (`100.85.144.126`) for SSH and secure admin access
- Best of both worlds - public web access + secure admin

## Step 11: Update Your Deployment

When deploying sLLM, you can now:

1. **Access Pi via Tailscale IP** for SSH and setup
2. **Configure nginx** to listen on Tailscale IP or all interfaces
3. **Test locally** using Tailscale IP
4. **For public access**, either:
   - Use Tailscale Funnel
   - Or keep using public IP + port forwarding for web traffic
   - Use Tailscale just for secure admin access

## Troubleshooting

### Tailscale won't start
```bash
# Check logs
sudo journalctl -u tailscaled -f

# Restart service
sudo systemctl restart tailscaled
```

### Can't see other devices
- Make sure all devices are signed in with the same Tailscale account
- Check that devices are approved in the admin console
- Verify firewall isn't blocking Tailscale (it uses port 41641/udp)

### Connection is slow
- Tailscale routes through the internet, so speed depends on your connection
- For better performance, enable "Direct Connection" in admin console
- Or use "Exit Nodes" if you have a faster server

### Check your Tailscale IP
```bash
sudo tailscale ip -4
```

## Next Steps

Once Tailscale is set up:
1. Continue with the sLLM deployment (see DEPLOYMENT.md)
2. You can SSH to your Pi from anywhere using the Tailscale IP
3. Access your services securely without port forwarding
4. Consider setting up Tailscale on your other devices too!

## Security Notes

- Tailscale uses WireGuard encryption - very secure
- Only devices on your Tailscale network can access each other
- You control which devices are on your network
- No need to expose ports to the public internet
- Perfect for secure remote access!

