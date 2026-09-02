#!/bin/bash
# Pull, build, and put the piece back on the display. Run on the object itself.
#
#   ./exhibit/deploy.sh          # pull, build, deploy, restart
#   ./exhibit/deploy.sh --local  # skip the pull, build what is in the tree
#
# The object runs from /home/chootka/drift, not from this checkout: the systemd
# units point there, and a git tree is not somewhere a sealed object should be
# reading its own files from at three in the morning in a stranger's house.

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
DEST="${DRIFT_DEST:-/home/chootka/drift}"

cd "$ROOT"

if [ "${1:-}" != "--local" ]; then
    echo "==> pulling"
    git pull --ff-only
fi

echo "==> building"
./exhibit/build.sh >/dev/null
du -sh "$HERE/object"

echo "==> deploying to $DEST"
mkdir -p "$DEST"
rsync -a --delete "$HERE/object/" "$DEST/"

echo "==> restarting"
sudo systemctl restart drift-server drift-kiosk
sleep 2

for u in drift-server drift-kiosk; do
    printf '  %-14s %s\n' "$u" "$(systemctl is-active "$u")"
done

# The piece is silent until someone touches SOUND ON, so the card reads closed
# here even when everything is right. Worth printing anyway: if a second card
# ever reappears, that is the HDMI audio coming back and stealing the output.
echo "==> audio"
aplay -l 2>/dev/null | sed -n 's/^card \([0-9]*\): \([^ ]*\).*/  card \1  \2/p'
amixer -c 0 sget Digital 2>/dev/null | sed -n 's/.*\(\[[0-9]*%\]\).*\(\[-\?[0-9.]*dB\]\).*/  volume \1 \2/p' | head -1

echo
echo "done. tap SOUND ON, then:  top -bn1 -o %CPU | head -8"
