#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export PATH="/opt/homebrew/bin:/usr/local/bin:$DIR:$PATH"
exec >> "/tmp/cradle_dualplay.log" 2>&1
echo "Starting Cradle DualPlay at $(date)"

APP_SUPPORT_DIR="$HOME/Library/Application Support/Cradle DualPlay"
mkdir -p "$APP_SUPPORT_DIR"
cd "$APP_SUPPORT_DIR"

# 1. Pobranie FFmpeg jeśli brakuje w App Support
if [ ! -f "ffmpeg" ]; then
    echo "Downloading FFmpeg to App Support..."
    curl -L -s -o ffmpeg.zip "https://evermeet.cx/ffmpeg/getrelease/zip"
    unzip -o -q ffmpeg.zip
    rm ffmpeg.zip
    chmod +x ffmpeg
    xattr -cr ffmpeg 2>/dev/null || true
fi

# 2. Utworzenie środowiska w App Support
if [ ! -d ".venv" ]; then
    echo "Creating virtualenv..."
    python3 -m venv .venv
fi
echo "Installing requirements..."
.venv/bin/pip install -q -r "$DIR/backend/requirements.txt"

# 3. Uruchomienie serwera
echo "Starting server..."
exec .venv/bin/python "$DIR/backend/server.py"
