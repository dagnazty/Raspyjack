#!/bin/bash
# Download Ragnar sprite images for the payload
# Run this from anywhere - images go to loot/Ragnar/images

set -e

# Default to loot folder
SCRIPT_DIR="${1:-/root/Raspyjack/loot/Ragnar}"
IMAGES_DIR="$SCRIPT_DIR/images"

echo "Downloading Ragnar sprite images to $IMAGES_DIR..."

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
