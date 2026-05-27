# New Video Compare

🎬 **Inteligentne porównywanie plików wideo i audio dla procesu akceptacji w Cradle**

## 🎯 Cel

Automatyzacja procesu porównywania plików acceptance i emission z wykorzystaniem zaawansowanych algorytmów analizy wideo i audio.

## 🏗️ Architektura

- **Backend**: FastAPI + Python 3.11+ (uvicorn)
- **Frontend**: React 18 + TypeScript + Vite
- **Video Processing**: FFmpeg, OpenCV (SSIM)
- **Audio Processing**: FFmpeg, Demucs (source separation), Whisper (STT), librosa, pyloudnorm
- **Waveform**: WaveSurfer.js
- **Database**: SQLite (local dev)

## ✨ Funkcje

### Video
- 🔍 Porównanie klatek SSIM (Low/Medium/High sensitivity)
- 🌡️ Interactive Heatmap Overlay (Pure Diff Mask + Opacity + Context Toggle)
- 🖼️ 3-Panel Difference Inspector (Source | Target | Diff)
- ⏱️ Timeline z markerami różnic

### Audio
- 📊 Pomiar głośności LUFS (Integrated, Short-term, Loudness Range)
- 🎤 Separacja źródeł audio (Demucs — vocals/drums/bass/other)
- 🗣️ Transkrypcja wielojęzyczna (Whisper — auto-detect language)
- 📈 Wizualizacja waveform (WaveSurfer.js — Acceptance vs Emission)
- 📝 Side-by-Side Dialog Timeline (sequential segment pairing)

### Dashboard
- 💾 Storage Usage monitoring
- 🗑️ Cleanup: Delete oldest jobs + orphan files/DB records + temp/proxies
- 🔄 Retry failed jobs
- 📋 Export raportu

## 🚀 Quick Start

### LIVE (produkcja)
```bash
# Backend — serwuje wszystko: frontend build/, /uploads, /api
cd new_video_compare/backend
source ../../.venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8001
```
➡️ **LIVE: http://localhost:8001**

### DEV (development)
```bash
# Backend DEV (nowy terminal)
cd new_video_compare/backend
source ../../.venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8002 --reload

# Frontend DEV (nowy terminal)
cd new_video_compare/frontend
PORT=3001 REACT_APP_API_URL=http://localhost:8002 REACT_APP_WS_URL=ws://localhost:8002/ws npm start
```
➡️ **DEV frontend: http://localhost:3001 | DEV backend: http://localhost:8002**

### Wdrożenie na LIVE
```bash
# 1. Zbuduj frontend
cd new_video_compare/frontend
npm run build

# 2. Zrestartuj LIVE backend (widzi nowy build/ automatycznie)
```
