#!/bin/bash
# Deploy the checkout to /var/www/sllm.
#
# Run from anywhere; it resolves the project root from its own location.
#
#   sudo ./scripts/deploy_on_pi.sh              # code + config, restart the API
#   sudo ./scripts/deploy_on_pi.sh --deps       # also pip install into the venv
#   sudo ./scripts/deploy_on_pi.sh --no-restart # stage everything, restart nothing
#   sudo ./scripts/deploy_on_pi.sh --dry-run    # show what would change
#
# WHAT THIS DOES NOT DO, and why, because the previous version did all three and
# each one silently regressed the box:
#
# 1. It does not generate systemd units inline. It installs deploy/*.service
#    verbatim. The old version wrote its own unit with User=chootka and no
#    hardening, which undid the privilege separation described in
#    documentation/bring_up.md -- the internet-facing Flask app went back to
#    running as the human login, with its SSH keys, git credentials and sudo
#    group membership. A unit file is configuration; it belongs in the repo,
#    not in a heredoc inside the thing that installs it.
#
# 2. It does not read etc/nginx.conf. That file is the pre-reverse-proxy,
#    HTTP-only configuration and is 145 lines divergent from what is live.
#    Copying it over the running config deletes the geo/map block that marks
#    tailnet traffic as TLS, which is the only thing letting this box tell a
#    public HTTPS request from a plaintext one on the studio LAN -- and the
#    admin routes gate on exactly that. deploy/nginx-sllm.visceral.systems.conf
#    is the live config and the only one this touches.
#
# 3. It does not prompt. The old version had an interactive `read -p` for the
#    nginx reload, which hangs any unattended run.
#
# It also never starts or restarts sllm-loop or sllm-demo. Putting light into a
# chamber is a deliberate act, not a side effect of deploying.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

DEPLOY_DIR="${DEPLOY_DIR:-/var/www/sllm}"
API_DIR="$DEPLOY_DIR/api"
FRONTEND_DIR="$DEPLOY_DIR/frontend"
DATA_DIR="$DEPLOY_DIR/data"
NGINX_CONF="/etc/nginx/sites-available/sllm.visceral.systems"
NGINX_SRC="deploy/nginx-sllm.visceral.systems.conf"
POLKIT_RULE="/etc/polkit-1/rules.d/50-sllm-loop.rules"

# The service account the units run as, and the human who owns the tree. Code is
# owned by chootka and world-readable; only data/ is writable by the service.
# That is deliberate -- a compromised API can write readings, not rewrite code.
CODE_OWNER="chootka:chootka"
DATA_OWNER="sllm:sllm"
WEB_OWNER="www-data:www-data"

INSTALL_DEPS=false
RESTART=true
DRY_RUN=false

while [ $# -gt 0 ]; do
    case "$1" in
        --deps)       INSTALL_DEPS=true ;;
        --no-restart) RESTART=false ;;
        --dry-run)    DRY_RUN=true; RESTART=false ;;
        -h|--help)    sed -n '2,32p' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo: sudo $0 $*" >&2
    exit 1
fi

if [ ! -d frontend ] || [ ! -d api ]; then
    echo "frontend/ or api/ not found under $PROJECT_ROOT" >&2
    exit 1
fi

# Verbose only under --dry-run: seeing the file list is the entire point there,
# and noise on a real deploy hides the lines that matter.
RSYNC_DRY=()
$DRY_RUN && RSYNC_DRY=(--dry-run --itemize-changes)

run() {
    # Echo and execute, or just echo under --dry-run. Anything with a side
    # effect outside rsync goes through here so --dry-run is honest.
    if $DRY_RUN; then
        echo "   would run: $*"
    else
        "$@"
    fi
}

say() { echo; echo "== $*"; }

CHANGED_UNITS=()
NGINX_CHANGED=false

# --- frontend ----------------------------------------------------------------

say "Frontend"
if [ -f frontend/package.json ]; then
    if [ ! -d frontend/node_modules ]; then
        echo "   installing npm dependencies"
        run bash -c "cd '$PROJECT_ROOT/frontend' && npm install"
    fi
    # Built as the invoking user, not root: a root-owned node_modules or
    # dist breaks the next non-sudo `npm run build`.
    BUILD_USER="${SUDO_USER:-root}"
    echo "   building as $BUILD_USER"
    run sudo -u "$BUILD_USER" bash -c "cd '$PROJECT_ROOT/frontend' && npm run build"
fi

if [ -d frontend/dist ]; then
    mkdir -p "$FRONTEND_DIR"
    # --delete matters here specifically: Vite emits content-hashed filenames,
    # so without it every deploy leaves the previous index-<hash>.js behind and
    # the assets directory grows forever.
    rsync -a --delete "${RSYNC_DRY[@]}" frontend/dist/ "$FRONTEND_DIR/"
    run chown -R "$WEB_OWNER" "$FRONTEND_DIR"
else
    echo "   no frontend/dist, skipping"
fi

# --- python code -------------------------------------------------------------

say "Code"
# config.py is excluded in BOTH directions: it is per-machine and untracked, and
# the deployed copy is the only record of the deployed settings. Overwriting it
# from the repo is how the two trees drifted before -- the repo said
# /home/pi/sllm/data, the deployment said /var/www/sllm/data, and a sed further
# down quietly patched it on every run. config_template.py still ships so a
# fresh deployment can seed one.
rsync -a --delete "${RSYNC_DRY[@]}" \
    --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='venv' --exclude='config.py' \
    --exclude='.lgd-nfy*' \
    api/ "$API_DIR/"

# gpio/, llm/ and scripts/ are deployed rather than run from the checkout
# because the loop reads the CSV the *service* writes, under $DEPLOY_DIR/data.
# Run from ~/sllm it resolves its own empty data directory and reports 0
# samples, which looks exactly like a dead ADC and is not.
for component in gpio llm scripts; do
    mkdir -p "$DEPLOY_DIR/$component"
    rsync -a --delete "${RSYNC_DRY[@]}" \
        --exclude='__pycache__' --exclude='*.pyc' --exclude='.lgd-nfy*' \
        "$component/" "$DEPLOY_DIR/$component/"
done

if [ ! -f "$API_DIR/config.py" ] && ! $DRY_RUN; then
    echo "   no config.py at $API_DIR, seeding from config_template.py"
    cp "$API_DIR/config_template.py" "$API_DIR/config.py"
fi

# Read and traverse for everyone (the service account reads it), write for the
# owner only. Not 755 on every file -- nothing here needs to be executable
# except the wrapper, which rsync already carries the bit for.
#
# venv/ is pruned rather than walked. It lives inside api/ but rsync never
# touches it, it holds thousands of files, and rewriting modes across an
# interpreter's site-packages on every deploy is a slow way to break something
# subtle. --deps chowns it when it actually changes.
fix_perms() {
    local root="$1"
    run find "$root" -name venv -prune -o -exec chown "$CODE_OWNER" {} +
    run find "$root" -name venv -prune -o -exec chmod u=rwX,go=rX {} +
}
for tree in "$API_DIR" "$DEPLOY_DIR/gpio" "$DEPLOY_DIR/llm" "$DEPLOY_DIR/scripts"; do
    fix_perms "$tree"
done

# --- data --------------------------------------------------------------------

say "Data directories"
for sub in images logs readings; do
    run mkdir -p "$DATA_DIR/$sub"
done
# setgid so files land in the sllm group whoever writes them: the service writes
# readings, and a human running ./scripts/py by hand writes into the same tree.
run chown -R "$DATA_OWNER" "$DATA_DIR"
run chmod -R u=rwX,g=rwXs,o=rX "$DATA_DIR"

# --- dependencies ------------------------------------------------------------

if $INSTALL_DEPS; then
    say "Python dependencies"
    VENV_PATH="$API_DIR/venv"
    if [ ! -d "$VENV_PATH" ]; then
        echo "   creating venv at $VENV_PATH"
        run python3 -m venv "$VENV_PATH"
    fi
    run "$VENV_PATH/bin/pip" install --upgrade pip
    run "$VENV_PATH/bin/pip" install -r "$API_DIR/requirements.txt"
    run chown -R "$CODE_OWNER" "$VENV_PATH"
else
    echo
    echo "   (skipping pip; pass --deps when requirements.txt has changed)"
fi

# --- systemd units -----------------------------------------------------------

say "systemd units"
# Installed only when they actually differ, so a routine code deploy does not
# churn unit files or trigger a daemon-reload it does not need.
for unit_src in deploy/*.service; do
    unit_name="$(basename "$unit_src")"
    unit_dst="/etc/systemd/system/$unit_name"
    if cmp -s "$unit_src" "$unit_dst"; then
        echo "   $unit_name unchanged"
        continue
    fi
    echo "   $unit_name CHANGED -> installing"
    run install -m 0644 -o root -g root "$unit_src" "$unit_dst"
    CHANGED_UNITS+=("$unit_name")
done

if [ -f deploy/50-sllm-loop.rules ]; then
    if cmp -s deploy/50-sllm-loop.rules "$POLKIT_RULE" 2>/dev/null; then
        echo "   polkit rule unchanged"
    else
        echo "   polkit rule CHANGED -> installing"
        run install -m 0644 -o root -g root deploy/50-sllm-loop.rules "$POLKIT_RULE"
    fi
fi

if [ ${#CHANGED_UNITS[@]} -gt 0 ]; then
    run systemctl daemon-reload
fi

# --- nginx -------------------------------------------------------------------

say "nginx"
if [ ! -f "$NGINX_SRC" ]; then
    echo "   $NGINX_SRC not found, leaving nginx alone"
elif cmp -s "$NGINX_SRC" "$NGINX_CONF"; then
    echo "   config unchanged"
else
    echo "   config CHANGED -> installing (backup alongside)"
    if [ -f "$NGINX_CONF" ]; then
        run cp -a "$NGINX_CONF" "${NGINX_CONF}.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    run install -m 0644 -o root -g root "$NGINX_SRC" "$NGINX_CONF"
    enabled="/etc/nginx/sites-enabled/$(basename "$NGINX_CONF")"
    [ -L "$enabled" ] || run ln -s "$NGINX_CONF" "$enabled"
    NGINX_CHANGED=true
fi

if $NGINX_CHANGED && ! $DRY_RUN; then
    # Validate before reloading. A bad config that is never loaded is a
    # non-event; a bad config that is reloaded takes the site down.
    if nginx -t; then
        systemctl reload nginx
        echo "   nginx reloaded"
    else
        echo "   !! nginx -t FAILED -- not reloading. The running config is" >&2
        echo "      still the old one; the backup is beside $NGINX_CONF." >&2
        exit 1
    fi
fi

# --- restart -----------------------------------------------------------------

say "Services"
if ! $RESTART; then
    echo "   not restarting (--no-restart / --dry-run)"
    if [ ${#CHANGED_UNITS[@]} -gt 0 ]; then
        echo "   note: these units changed and are not yet in effect:" \
             "${CHANGED_UNITS[*]}"
    fi
else
    # sllm-api only, by default. Restarting it pauses ADC sampling for a second
    # or two -- a visible gap in the day's electrode CSV -- and clears whatever
    # stimulus zone this service had set.
    systemctl restart sllm-api
    echo "   sllm-api restarted"

    # matrixd is not restarted automatically even when its unit changes: it owns
    # the panel, and bouncing it blanks the matrix, including the barrier zone
    # that must stay lit whenever the organism is in the chamber.
    for unit in "${CHANGED_UNITS[@]}"; do
        case "$unit" in
            sllm-matrixd.service)
                echo "   !! sllm-matrixd.service changed but was NOT restarted."
                echo "      It owns the panel and a restart blanks it, barrier"
                echo "      zone included. Restart it deliberately:"
                echo "        sudo systemctl restart sllm-matrixd"
                ;;
            sllm-loop.service|sllm-demo.service)
                echo "   note: $unit changed; it takes effect the next time you"
                echo "      start it. Neither is started by a deploy."
                ;;
        esac
    done
fi

# --- report ------------------------------------------------------------------

say "State"
if $DRY_RUN; then
    echo "   dry run, nothing was changed"
    exit 0
fi

systemctl is-active sllm-matrixd sllm-api sllm-loop sllm-demo \
    | paste -d' ' <(printf '%s\n' matrixd api loop demo) - \
    | sed 's/^/   /'

echo
echo "   curl -s localhost/api/status | python3 -m json.tool"
echo "   tail -3 $DATA_DIR/readings/electrodes_*.csv"
