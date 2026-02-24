#!/bin/bash
# Download ALL Ragnar sprite images for the payload
# Run with: bash download_images.sh
# Images go to loot/Ragnar/images/

set -e

SCRIPT_DIR="${1:-/root/Raspyjack/loot/Ragnar}"
IMAGES_DIR="$SCRIPT_DIR/images"

echo "Downloading ALL Ragnar sprite images to $IMAGES_DIR..."

# List of all animation folders
ANIMATIONS=(
    "IDLE"
    "NetworkScanner"
    "NmapVulnScanner"
    "FTPBruteforce"
    "SSHBruteforce"
    "SMBBruteforce"
    "RDPBruteforce"
    "SQLBruteforce"
    "StealDataSQL"
    "LogStandalone"
    "LogStandalone2"
)

# Create directories
for ANIM in "${ANIMATIONS[@]}"; do
    mkdir -p "$IMAGES_DIR/$ANIM"
done

# Download frames for each animation
for ANIM in "${ANIMATIONS[@]}"; do
    echo "Downloading $ANIM frames..."
    for i in 0 1 2 3 4 5 6 7 8 9; do
        if [ $i -eq 0 ]; then
            SUFFIX=""
        else
            SUFFIX="$i"
        fi
        URL="https://raw.githubusercontent.com/PierreGode/Ragnar/main/resources/images/status/$ANIM/${ANIM}${SUFFIX}.bmp"
        curl -sL "$URL" -o "$IMAGES_DIR/$ANIM/${ANIM}${SUFFIX}.bmp" 2>/dev/null || true
    done
    # Also try without suffix (base frame)
    URL="https://raw.githubusercontent.com/PierreGode/Ragnar/main/resources/images/status/$ANIM/${ANIM}.bmp"
    curl -sL "$URL" -o "$IMAGES_DIR/$ANIM/${ANIM}.bmp" 2>/dev/null || true
    
    COUNT=$(ls -1 "$IMAGES_DIR/$ANIM"/*.bmp 2>/dev/null | wc -l)
    echo "  -> Got $COUNT frames"
done

echo ""
echo "Done! Downloaded to $IMAGES_DIR"
echo "Animations: ${ANIMATIONS[*]}"
