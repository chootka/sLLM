# Tailscale

## This tailnet

| Tailscale IP | Name | Role |
|---|---|---|
| `100.85.144.126` | `sllm` | this Pi |
| `100.75.40.22` | `sllm-reverse-proxy` | DigitalOcean droplet, terminates TLS, forwards to this Pi |
| `100.127.41.6` | `chootka-pro` | laptop, runs Ollama |

LAN address of the Pi is `192.168.10.130`. Login is `chootka`.

Public access goes through the droplet, not through Tailscale Funnel. Funnel is
not configured and `tailscale funnel status` reports "No serve config". Do not
enable it — the network path in `DEPLOYMENT.md` is what nginx and the admin
routes are built around.

## Install on a new machine

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

`tailscale up` prints a `https://login.tailscale.com/a/...` URL. Open it, sign
in, approve the device.

```bash
sudo tailscale status
sudo tailscale ip -4
sudo systemctl enable tailscaled
```

## Access

```bash
ssh chootka@100.85.144.126
ssh chootka@sllm                      # with MagicDNS enabled
curl http://100.85.144.126/api/status
```

Tailscale IPs are reachable only from devices on this tailnet.

## Troubleshooting

```bash
sudo journalctl -u tailscaled -f
sudo systemctl restart tailscaled
sudo tailscale ip -4
```

Devices must be signed in to the same account and approved at
https://login.tailscale.com/admin/machines. Tailscale uses 41641/udp.
