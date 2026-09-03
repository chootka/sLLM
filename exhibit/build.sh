#!/bin/bash
# Assemble the shippable folder: page, worklet, recording, server.
#
#   ./exhibit/build.sh                                   # -> exhibit/object/
#   ./exhibit/build.sh replay_run6.json object-run6      # a second one
#
# The result is self-contained. No API, no network, no writes at runtime.
#
# The optional arguments exist so two recordings can be built from one tree and
# served on different ports for comparison. The recording is the only thing
# that differs; both get the same page and the same worklet.

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

REPLAY="$HERE/${1:-replay.json}"
OUT="$HERE/${2:-object}"

[ -f "$REPLAY" ] || {
    echo "no $REPLAY -- run scripts/export_replay.py first" >&2
    exit 1
}

cd "$ROOT/frontend"
npm run build

rm -rf "$OUT"
mkdir -p "$OUT"
cp -r "$ROOT/frontend/dist/." "$OUT/"
# Always lands as replay.json in the output: the page asks for that name.
cp "$REPLAY" "$OUT/replay.json"
cp "$HERE/serve.py" "$OUT/"
# The out-of-browser synth runs from the same directory, beside the recording
# and the worklet the page already ships. One copy of ring-processor.js, so the
# two cannot drift into different instruments.
cp "$HERE/synth/synth.js" "$OUT/"

echo
echo "$OUT"
du -sh "$OUT"
echo "test it:  python3 $OUT/serve.py 8080  ->  http://127.0.0.1:8080/drift"
