# Deployment

Box is `sllm` at Tailscale `100.85.144.126`, LAN `192.168.10.130`, login
`chootka`. Repo at `~/sllm`, services run from `/var/www/sllm`. A commit is not
a deploy.

`deploy/` is the source of truth for everything outside the code:

```
deploy/50-sllm-loop.rules
deploy/nginx-sllm.visceral.systems.conf
deploy/sllm-api.service
deploy/sllm-demo.service
deploy/sllm-loop.service
deploy/sllm-matrixd.service
```

## Deploy

On the Pi:

```bash
cd ~/sllm && git pull
sudo ./scripts/deploy_on_pi.sh              # code + config, restarts sllm-api
sudo ./scripts/deploy_on_pi.sh --dry-run    # what would change, no side effects
sudo ./scripts/deploy_on_pi.sh --deps       # also pip install, when requirements moved
sudo ./scripts/deploy_on_pi.sh --no-restart # stage it, restart nothing
```

The script builds the frontend with Vite, copies to `/var/www/sllm/`, creates
the venv, installs the nginx site and polkit rule when they differ from live,
and restarts `sllm-api`.

What it does not do, and why, is in `bring_up.md` under **Deploying**.

From the laptop: `./scripts/deploy_to_pi.sh`, which needs `scripts/config.sh`
(see `scripts/config.example.sh`).

## Network path

```
public ──TLS──> DigitalOcean droplet 77.42.69.156      (tailnet: sllm-reverse-proxy)
                └──plain HTTP/1.0 over Tailscale──> this Pi, from 100.75.40.22
                                                     nginx :80 ──> Flask :5000
```

`sllm.visceral.systems` resolves to the droplet, not to this Pi. Tailscale
Funnel is not in use.

- Port 80 on the Pi is the production path. Redirecting it to HTTPS gives every
  public visitor an infinite redirect loop.
- The droplet sends no `X-Forwarded-Proto` and no `X-Forwarded-For`. nginx
  synthesises the header from a `geo`/`map` block keyed on `100.75.40.22`.
  Admin routes reject anything not marked https, so plain LAN access to them
  returns 403. That block is why `etc/nginx.conf` must never be copied over the
  live site.

Live site: `/etc/nginx/sites-enabled/sllm.visceral.systems`, installed from
`deploy/nginx-sllm.visceral.systems.conf`. The script runs `nginx -t` before
reloading.

Tailscale setup: `TAILSCALE_SETUP.md`.

## Service accounts

```
sllm-matrixd   root    owns the WS2812B panel. The ONLY privileged process.
sllm-api       sllm    web API, sampling, logging, camera timelapse, fan.
sllm-loop      sllm    the model loop.
sllm-demo      sllm    invented data driving the panel. Not enabled at boot.
```

`sllm-api`, `sllm-loop` and `sllm-matrixd` are enabled; `sllm-demo` is not.
Units are installed from `deploy/`, never generated.

## Test

```bash
curl -s localhost:5000/api/status | python3 -m json.tool   # Flask direct
curl -s localhost/api/status                               # through nginx
curl -s https://sllm.visceral.systems/api/status           # through the droplet
```

## Troubleshooting

```bash
sudo journalctl -u sllm-api -f
sudo tail -f /var/log/nginx/sllm.error.log
sudo tail -f /var/log/nginx/sllm.access.log
sudo systemctl restart sllm-api
sudo systemctl reload nginx
```
