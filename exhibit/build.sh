#!/bin/bash
# Assemble the shippable folder: page, worklet, recording, server.
#
#   ./exhibit/build.sh            # -> exhibit/object/
#
# The result is self-contained. No API, no network, no writes at runtime.

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
OUT="$HERE/object"

[ -f "$HERE/replay.json" ] || {
    echo "no exhibit/replay.json -- run scripts/export_replay.py first" >&2
    exit 1
}

cd "$ROOT/frontend"
npm run build

rm -rf "$OUT"
mkdir -p "$OUT"
cp -r "$ROOT/frontend/dist/." "$OUT/"
cp "$HERE/replay.json" "$OUT/"
cp "$HERE/serve.py" "$OUT/"

echo
echo "$OUT"
du -sh "$OUT"
echo "test it:  python3 $OUT/serve.py 8080  ->  http://127.0.0.1:8080/drift"
