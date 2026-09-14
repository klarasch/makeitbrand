#!/bin/sh
# tools/shoot.sh URL OUT.png [WIDTH HEIGHT] — screenshot a sheet with headless Chrome (dev aid).
URL=$1; OUT=$2; W=${3:-1700}; H=${4:-4400}
PROF=$(mktemp -d)
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --no-first-run \
  --hide-scrollbars --window-size=$W,$H --user-data-dir="$PROF" --screenshot="$OUT" "$URL" >/dev/null 2>&1 &
PID=$!
for i in $(seq 1 40); do [ -s "$OUT" ] && break; sleep 0.5; done
sleep 0.5; kill $PID 2>/dev/null; rm -rf "$PROF"
[ -s "$OUT" ] && echo "$OUT" || { echo "no screenshot"; exit 1; }
