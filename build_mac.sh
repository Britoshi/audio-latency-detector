#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

# Bootstrap venv if needed
if [ ! -f "$PYTHON" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    "$PIP" install --quiet -r "$SCRIPT_DIR/requirements.txt"
fi

# Install PyInstaller into the venv if missing
if ! "$PYTHON" -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    "$PIP" install --quiet pyinstaller
fi

APP_NAME="Audio Latency Detector"
OS="$(uname -s)"

echo "Building for $OS..."

cd "$SCRIPT_DIR"

if [ "$OS" = "Darwin" ]; then
    "$PYTHON" -m PyInstaller \
        --onedir \
        --windowed \
        --name "$APP_NAME" \
        --clean \
        audio_latency_detector.py
    echo ""
    echo "Done: dist/${APP_NAME}.app"
    echo "Tip: right-click → Open on first launch to bypass Gatekeeper."
else
    # Linux — produce a single binary
    "$PYTHON" -m PyInstaller \
        --onefile \
        --name "audio-latency-detector" \
        --clean \
        audio_latency_detector.py
    echo ""
    echo "Done: dist/audio-latency-detector"
fi

# Clean up build artefacts, keep only dist/
rm -rf "$SCRIPT_DIR/build" "$SCRIPT_DIR"/*.spec
