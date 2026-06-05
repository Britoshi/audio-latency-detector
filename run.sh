#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "Installing dependencies..."
    "$VENV_DIR/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"
    echo "Setup complete."
    echo ""
fi

if [ $# -eq 0 ] || [ "$1" = "--gui" ]; then
    "$PYTHON" "$SCRIPT_DIR/audio_latency_detector.py"
else
    "$PYTHON" "$SCRIPT_DIR/detect_offset.py" "$@"
fi