#!/bin/bash

# Ustalenie katalogu roboczego (folder MacOS wewnątrz .app)
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=========================================="
echo "    Uruchamianie Cradle DualPlay...       "
echo "=========================================="

# 1. Sprawdzenie i pobranie FFmpeg jeśli brakuje
if [ ! -f "ffmpeg" ]; then
    echo "[1/3] Pobieranie silnika wideo (FFmpeg)... Może to potrwać kilkanaście sekund."
    # Pobranie statycznej binarki FFmpeg dla macOS
    curl -L -s -o ffmpeg.zip "https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v6.1/ffmpeg-6.1-mac-64.zip"
    unzip -o -q ffmpeg.zip
    rm ffmpeg.zip
    chmod +x ffmpeg
    xattr -cr ffmpeg 2>/dev/null || true
    echo "✅ FFmpeg pobrany."
else
    echo "✅ Silnik wideo gotowy."
fi

# Eksport ścieżki, żeby nasz skrypt Pythonowy widział lokalnego ffmpega
export PATH="$DIR:$PATH"

# 2. Sprawdzenie i utworzenie wirtualnego środowiska Pythona
if [ ! -d "backend/.venv" ]; then
    echo "[2/3] Pierwsze uruchomienie. Konfiguracja środowiska..."
    python3 -m venv backend/.venv
    source backend/.venv/bin/activate
    echo "Instalacja pakietów serwera (FastAPI)..."
    pip install -q -r backend/requirements.txt
    echo "✅ Środowisko skonfigurowane."
else
    echo "✅ Środowisko gotowe."
    source backend/.venv/bin/activate
fi

# 3. Uruchomienie serwera w tle i otwarcie przeglądarki
echo "[3/3] Uruchamianie lokalnego serwera Cradle DualPlay na porcie 8002..."
cd backend
# Odpalamy serwer uvicorn
python server.py &
SERVER_PID=$!

# Czekamy 2 sekundy aż serwer wstanie
sleep 2

# Otwieramy domyślną przeglądarkę
open "http://127.0.0.1:8002"

echo "=========================================="
echo " Serwer działa. Możesz zminimalizować to okno."
echo " Aby wyłączyć DualPlay, po prostu zamknij ten terminal (Cmd+Q)."
echo "=========================================="

# Czekamy na proces serwera, żeby terminal się nie zamknął
wait $SERVER_PID
