#!/bin/bash

# Ustalenie katalogu roboczego (folder Resources wewnątrz .app)
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

export PATH="/opt/homebrew/bin:/usr/local/bin:$DIR:$PATH"
exec > >(tee -a "/tmp/cradle_dualplay.log") 2>&1
echo "Starting Cradle DualPlay at $(date)"
# 1. Sprawdzenie i pobranie FFmpeg jeśli brakuje
if [ ! -f "ffmpeg" ]; then
    curl -L -s -o ffmpeg.zip "https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v6.1/ffmpeg-6.1-mac-64.zip"
    unzip -o -q ffmpeg.zip
    rm ffmpeg.zip
    chmod +x ffmpeg
    xattr -cr ffmpeg 2>/dev/null || true
fi

# 2. Sprawdzenie i utworzenie wirtualnego środowiska Pythona
if [ ! -d "backend/.venv" ]; then
    python3 -m venv backend/.venv
    source backend/.venv/bin/activate
    pip install -q -r backend/requirements.txt
else
    source backend/.venv/bin/activate
fi

# 3. Uruchomienie serwera
cd backend

# Używamy 'exec', aby proces Pythona zastąpił proces bash.
# Dzięki temu PID zwrócony do AppleScript to PID serwera, 
# a jego zabicie (kill) poprawnie zwolni port 8002.
exec python server.py
