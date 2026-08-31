#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APPDIR="$ROOT_DIR/FSKit.AppDir"
BIN_DEST="$APPDIR/usr/bin/FSKit"
APPIMAGETOOL="$SCRIPT_DIR/appimagetool-aarch64.AppImage"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-aarch64.AppImage"
OUTPUT="$ROOT_DIR/FSKit-aarch64.AppImage"

if [ ! -f "$APPIMAGETOOL" ]; then
    echo "[INFO] fetching AppImageTool"
    curl -fsSL "$APPIMAGETOOL_URL" -o "$APPIMAGETOOL"
    chmod +x "$APPIMAGETOOL"
    echo "[INFO] fetched AppImageTool: $APPIMAGETOOL"
else
    echo "[INFO] AppImageTool is OK: $APPIMAGETOOL"
fi

HOST_ARCH="$(uname -m)"
if [ "$HOST_ARCH" != "aarch64" ]; then
    echo "[ERROR] This script must be run on an aarch64 Linux environment."
    echo "[ERROR] Current architecture: $HOST_ARCH"
    echo "[ERROR] Nuitka does not perform this x86_64 -> aarch64 cross-compilation automatically."
    exit 1
fi

echo "[INFO] Building binary with nuitka for aarch64..."
cd "$ROOT_DIR"

uv run nuitka \
    --standalone --onefile \
    --enable-plugin=pyside6 \
    --company-name=ABATBeliever \
    --product-name="Free Signage Kit" \
    --file-description="Free Signage Kit" \
    FSKit.py

echo "[INFO] Building binary OK"

NUITKA_OUTPUT="$ROOT_DIR/FSKit.bin"
if [ ! -f "$NUITKA_OUTPUT" ]; then
    echo "[ERROR] Failed to find FSKit.bin: $NUITKA_OUTPUT"
    exit 1
fi

mkdir -p "$APPDIR/usr/bin"
cp "$NUITKA_OUTPUT" "$BIN_DEST"

echo "[INFO] chmod..."
chmod +x "$APPDIR/AppRun"
chmod +x "$BIN_DEST"
chmod +x "$APPDIR/app.png"

echo "[INFO] Building .AppImage with AppImageTool..."
cd "$ROOT_DIR"

ARCH=aarch64 "$APPIMAGETOOL" "$APPDIR" "$OUTPUT"

chmod +x "$OUTPUT"

echo ""
echo "[INFO] Build Success! [aarch64]"
