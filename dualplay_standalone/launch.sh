#!/bin/bash

# Ustalenie katalogu roboczego (folder Resources wewnątrz .app)
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

export PATH="/opt/homebrew/bin:/usr/local/bin:$DIR:$PATH"
exec > >(tee -a "/tmp/cradle_dualplay.log") 2>&1
echo "Starting Cradle DualPlay at $(date)"
# 1. Sprawdzenie i pobranie FFmpeg jeśli brakuje
if [ ! -f "ffmpeg" ]; then
    curl -L -s -o ffmpeg.zip "https://evermeet.cx/ffmpeg/getrelease/zip"
    unzip -o -q ffmpeg.zip
    rm ffmpeg.zip
    chmod +x ffmpeg
    xattr -cr ffmpeg 2>/dev/null || true
fi

# 2. Sprawdzenie i utworzenie wirtualnego środowiska Pythona
if [ ! -d "backend/.venv" ]; then
    python3 -m venv backend/.venv
fi
backend/.venv/bin/pip install -q -r backend/requirements.txt

# 3. Uruchomienie serwera
cd backend
exec .venv/bin/python server.py
