#!/bin/sh
# Render several clips one after another, then free their frame caches (each 1080p clip caches ~0.7 GB of JPEGs).
# Usage: sh run_batch.sh films/<name>/clip02 films/<name>/clip03 ...    (each folder has spec.json)
# Needs DEMUCS_PY and HTTPS_PROXY in the environment (see SKILL.md). Log: <folder>/render.log
HERE=$(cd "$(dirname "$0")" && pwd); LIB=$(cd "$HERE/../../../.." && pwd)
for d in "$@"; do
  echo "=== $d $(date +%H:%M:%S)"
  if HF_HUB_DISABLE_XET=1 "$LIB/.venv/bin/python" "$HERE/make_clip.py" "$d/spec.json" > "$d/render.log" 2>&1; then
    tail -1 "$d/render.log"; find "$d/frames" -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} +     # keep frames/cover.jpg
  else echo "FAILED: see $d/render.log"; tail -3 "$d/render.log"; fi
done
echo "BATCH DONE $(date +%H:%M:%S)"
