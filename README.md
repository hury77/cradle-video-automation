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

## 🚀 Installation

### Development Mode (Chrome/Edge)

1. **Clone the repository:**
   git clone https://github.com/hury77/cradle-video-automation.git
   cd cradle-video-automation
   ```

## 🖥️ Uruchamianie środowiska lokalnego

Aby autodetekcja i porównywanie wideo zadziałało, musisz odpalić lokalne serwisy w 3 osobnych oknach terminala:

### 1. Uruchamianie Backendu (FastAPI)
W pierwszym oknie terminala:
```bash
cd ~/Documents/cradle-video-automation/new_video_compare/backend
source ../../.venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### 2. Uruchamianie Frontendu (React)
W drugim oknie terminala:
```bash
cd ~/Documents/cradle-video-automation/new_video_compare/frontend
npm start
```

### 3. Uruchamianie Desktop App (WebSocket + Obsługa Plików Lokalnych)
W trzecim oknie terminala:
```bash
cd ~/Documents/cradle-video-automation/desktop-app
source ../.venv/bin/activate
python src/main.py
```