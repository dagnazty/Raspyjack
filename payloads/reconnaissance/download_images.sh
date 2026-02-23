#!/bin/bash
# Download Ragnar sprite images for the payload
# Run this from the payloads/reconnaissance directory

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGES_DIR="$SCRIPT_DIR/images"

echo "Downloading Ragnar sprite images..."

mkdir -p "$IMAGES_DIR/IDLE" "$IMAGES_DIR/NetworkScanner"

# Download IDLE frames
for i in 0 1 2 3 4; do
    if [ $i -eq 0 ]; then
        SUFFIX=""
    else
        SUFFIX="$i"
    fi
    URL="https://raw.githubusercontent.com/PierreGode/Ragnar/main/resources/images/status/IDLE/IDLE${SUFFIX}.bmp"
    echo "Downloading IDLE${SUFFIX}.bmp..."
    curl -sL "$URL" -o "$IMAGES_DIR/IDLE/IDLE${SUFFIX}.bmp" || echo "Failed: $URL"
done

# Download NetworkScanner frames
for i in 0 1 2 3 4; do
    if [ $i -eq 0 ]; then
        SUFFIX=""
    else
        SUFFIX="$i"
    fi
    URL="https://raw.githubusercontent.com/PierreGode/Ragnar/main/resources/images/status/NetworkScanner/NetworkScanner${SUFFIX}.bmp"
    echo "Downloading NetworkScanner${SUFFIX}.bmp..."
    curl -sL "$URL" -o "$IMAGES_DIR/NetworkScanner/NetworkScanner${SUFFIX}.bmp" || echo "Failed: $URL"
done

echo "Done! Downloaded images to $IMAGES_DIR"
