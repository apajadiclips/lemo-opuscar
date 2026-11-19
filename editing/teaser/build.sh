#!/bin/sh
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
LIB=${LIB:-$(cd "$HERE/../.." && pwd)}   # editing/teaser/ or films/<name>/
export LIB
[ -f "$LIB/core/render/video.mjs" ] || { echo "set LIB to the library folder"; exit 1; }
cd "$LIB"
S=1080x1920
node core/render/events.mjs "$HERE" --size $S
node core/render/video.mjs "$HERE" --fps 24 --workers 4 --size $S --out "$HERE/out/video.mp4"
"$LIB/.venv/bin/python" "$HERE/mix.py"
# needs ffmpeg 7+; with ffmpeg 6 run loudnorm (two-pass, -14 LUFS) + a limiter + mux by hand
sh core/render/mux.sh "$HERE/out/video.mp4" "$HERE/out/mix.wav" "$HERE/teaser-5-gaya-edit.mp4" 24 2
ffmpeg -y -loglevel error -ss 27.8 -i "$HERE/teaser-5-gaya-edit.mp4" -frames:v 1 -q:v 2 "$HERE/poster.jpg"
