# AI Optimization for MacBook M4 (Local Processing)

This plan optimizes the video comparison pipeline to leverage the MacBook Air M4 hardware (Neural Engine, Metal GPU, and Unified Memory). It aims to reduce processing time by 300-500% and enable local AI decision-making.

## Proponowane Fazy:

### Faza 1: Prędkość (Optymalizacja M4) - Działa niezależnie
1. **Whisper na Neural Engine**: Przejście na `mlx-whisper` (10x szybciej).
2. **Audio na GPU**: Przełączenie Demucs na tryb Metal (MPS).
3. **Wideo na Hardware**: Wykorzystanie VideoToolbox w FFmpeg.

### Faza 2: Inteligencja (Opcjonalna) - Wymaga Ollama
4. **Analyst Brain**: Automatyczna analiza wyników przez lokalny model LLM (np. Llama 3).

---

## Szczegóły Techniczne

### 1. Whisper Acceleration (STT)
- Zastąpienie biblioteki `openai-whisper` biblioteką **`mlx-whisper`**.
- Wykorzystanie modelu `mlx-community/whisper-small-mlx-4bit` (optymalny balans prędkość/jakość).

### 2. Demucs Acceleration
- Zmiana urządzenia przetwarzania w `audio_service.py` z `-d cpu` na **`-d mps`**.
- Przeniesienie separacji ścieżek dźwiękowych na GPU Metal.

### 3. FFmpeg Hardware Acceleration
- Dodanie flagi `-c:v h264_videotoolbox` do wszystkich poleceń transkodowania wideo.

### 4. Local LLM Analyst (Agent 2 Brain)
- Stworzenie usługi `analyst_service.py` łączącej się z lokalnym serwerem **Ollama** (localhost:11434).
- Automatyczne generowanie werdyktu i uzasadnienia (Reasoning) na podstawie metryk SSIM i transkrypcji.

---

## Instrukcja uruchomienia (Faza 1):

1. Zainstaluj biblioteki MLX:
   ```bash
   pip install mlx-whisper mlx
   ```
2. Zainstaluj Ollama (tylko dla Fazy 2): [ollama.com](https://ollama.com/)
