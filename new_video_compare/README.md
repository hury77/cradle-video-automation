# New Video Compare

🎬 **Inteligentne porównywanie plików wideo i audio dla procesu akceptacji w Cradle**

## 🎯 Cel

Automatyzacja procesu porównywania plików acceptance i emission z wykorzystaniem zaawansowanych algorytmów analizy wideo i audio.

## 🏗️ Architektura

- **Backend**: FastAPI + Python 3.11+
- **Frontend**: React 18 + TypeScript
- **Processing**: FFmpeg, OpenCV, librosa
- **Queue**: Celery + Redis
- **Database**: PostgreSQL
- **Container**: Docker

## 🚀 Quick Start

```bash
# Development setup
cd new_video_compare
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Start backend
cd backend
uvicorn main:app --reload

# Start frontend (new terminal)
cd frontend
npm install
npm run dev
EOF
```
