#!/bin/sh
# Download a Google Drive file shared as "Anyone with the link", including big files (virus-scan confirm page).
# Usage: sh fetch_drive.sh <drive link or file id> <out.mp4>
# Needs drive.google.com and drive.usercontent.google.com allowed in the environment's network settings.
set -e
ID=$(echo "$1" | sed -n 's#.*/d/\([A-Za-z0-9_-]*\).*#\1#p'); [ -n "$ID" ] || ID=$(echo "$1" | sed -n 's#.*[?&]id=\([A-Za-z0-9_-]*\).*#\1#p'); [ -n "$ID" ] || ID="$1"
OUT="$2"; TMP=$(mktemp -d)
URL="https://drive.usercontent.google.com/download?id=$ID&export=download"
curl -sSL -c "$TMP/c" "$URL" -o "$TMP/first"
if head -c 200 "$TMP/first" | grep -qi "<!doctype html\|<html"; then
  UUID=$(grep -o 'name="uuid" value="[^"]*"' "$TMP/first" | cut -d'"' -f4)
  grep -o '<span class="uc-name-size">.*</span>' "$TMP/first" | sed 's/<[^>]*>//g' || true
  curl -sSL -b "$TMP/c" "$URL&confirm=t&uuid=$UUID" -o "$OUT"
else mv "$TMP/first" "$OUT"; fi
rm -rf "$TMP"; ls -la "$OUT"; file "$OUT"
