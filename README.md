# cradle-video-automation
Browser extension for automating Cradle video comparison workflow
# 🎬 Cradle Video Automation

> Browser extension for automating video file comparison workflow in Cradle system

## ✨ Features

- 🔍 **Automatic Task Scanning** - Finds pending QA final proofreading tasks
- 📁 **Smart File Discovery** - Locates accept and emisyjny files from multiple sources
- 🎬 **Video Compare Integration** - Automates comparison setup in Video Compare
- 📊 **Real-time Progress** - Live updates and activity logging
- ⚙️ **User Control** - Full start/stop control and configuration
- 🔄 **Background Monitoring** - Optional auto-scanning every 2 minutes

## ⚡ Szybki Start (LIVE)

**Terminal 1 (Backend):**
```bash
cd ~/Documents/cradle-video-automation/new_video_compare/backend && source $HOME/miniforge3/bin/activate && conda activate cradle-env && uvicorn main:app --host 0.0.0.0 --port 8001
```
➡️ **LIVE dostępny pod: http://localhost:8001**

**Terminal 2 (Desktop App - wymagane do pobierania plików):**
```bash
cd ~/Documents/cradle-video-automation/desktop-app && source $HOME/miniforge3/bin/activate && conda activate cradle-env && python src/main.py
```

## 🚀 Installation

### Development Mode (Chrome/Edge)

1. **Clone the repository:**
```bash
git clone https://github.com/hury77/cradle-video-automation.git
cd cradle-video-automation
```

2. **Setup Virtual Environment:**
```bash
source $HOME/miniforge3/bin/activate
conda create -n cradle-env python=3.11 nodejs=20 ffmpeg git -y
conda activate cradle-env
pip install -r new_video_compare/backend/requirements.txt
pip install -r desktop-app/requirements.txt
```

## 🖥️ Uruchamianie środowiska lokalnego

System działa w dwóch trybach: **LIVE** (produkcja) i **DEV** (development).

### LIVE — 2 terminale

#### 1. Backend LIVE (FastAPI — serwuje frontend + API + uploads)
```bash
cd ~/Documents/cradle-video-automation/new_video_compare/backend
source $HOME/miniforge3/bin/activate
conda activate cradle-env
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```
➡️ http://localhost:8001 (frontend + API w jednym)

#### 2. Desktop App (WebSocket + Obsługa Plików)
```bash
cd ~/Documents/cradle-video-automation/desktop-app
source $HOME/miniforge3/bin/activate
conda activate cradle-env
python src/main.py
```

---

### DEV — 3 terminale

#### 1. Backend DEV
```bash
cd ~/Documents/cradle-video-automation/new_video_compare/backend
source $HOME/miniforge3/bin/activate
conda activate cradle-env
uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

#### 2. Frontend DEV (hot reload z src/)
```bash
cd ~/Documents/cradle-video-automation/new_video_compare/frontend
PORT=3001 REACT_APP_API_URL=http://localhost:8002 REACT_APP_WS_URL=ws://localhost:8002/ws npm start
```
➡️ http://localhost:3001

#### 3. Desktop App
```bash
cd ~/Documents/cradle-video-automation/desktop-app
source $HOME/miniforge3/bin/activate
conda activate cradle-env
python src/main.py
```

## 🔄 Jak zrestartować poszczególne serwisy (po aktualizacji kodu)

### 1. Przeładowanie Rozszerzenia Chrome
Gdy kod w `extension/` zostanie zaktualizowany:
1. Wejdź pod `chrome://extensions/`
2. Znajdź **Cradle Scanner** → kliknij **Odśwież**
3. Odśwież kartę z systemem Cradle

### 2. Restart Desktop App (Python)
1. Terminal z `python src/main.py` → `Ctrl + C`
2. Ponownie uruchom:
```bash
python src/main.py
```

### 3. Restart Backendu LIVE (FastAPI :8001)
Wymagany po `npm run build` lub zmianie kodu backendowego:
1. Terminal z `uvicorn` → `Ctrl + C`
2. Ponownie uruchom:
```bash
uvicorn main:app --host 0.0.0.0 --port 8001
```
> ⚠️ LIVE backend **nie ma** `--reload`. Restart jest świadomy i celowy.

### 4. Restart Frontendu DEV (React :3001)
Zazwyczaj **nie jest wymagany** — DEV korzysta z hot reload. W razie problemów:
1. Terminal z `npm start` → `Ctrl + C`
2. Ponownie uruchom:
```bash
PORT=3001 REACT_APP_API_URL=http://localhost:8002 REACT_APP_WS_URL=ws://localhost:8002/ws npm start
```

### 5. Wdrożenie nowej wersji frontendu na LIVE
```bash
cd ~/Documents/cradle-video-automation/new_video_compare/frontend
npm run build
# Następnie zrestartuj backend LIVE (:8001)
```

## 🧹 Czyszczenie miejsca na dysku (Zgodne z SOUL.md)

Jeśli projekt zacznie zajmować za dużo miejsca (ponad 25 GB) przez nagromadzone filmy testowe i logi, możesz bezpiecznie wyczyścić przestrzeń za pomocą wbudowanego skryptu `disk_monitor.py`.

Skrypt skanuje pliki, znajduje te najstarsze i największe, a następnie prosi Cię o potwierdzenie przed ich usunięciem. Działa ze ścisłym poszanowaniem bazy danych (`new_video_compare.db`), więc statystyki i historia QA zawsze pozostają bezpieczne.

Aby go uruchomić, wykonaj w terminalu będąc w głównym katalogu projektu:
```bash
cd ~/Documents/cradle-video-automation
python3 disk_monitor.py
```