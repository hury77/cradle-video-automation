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

## 🔄 Jak zrestartować poszczególne serwisy (po aktualizacji kodu)

### 1. Przeładowanie Rozszerzenia Chrome (Agenta 1)
Gdy kod w folderze `extension/` zostanie zaktualizowany (zwłaszcza główny skrypt `cradle-scanner.js`):
1. Wejdź w przeglądarce pod adres `chrome://extensions/`
2. Znajdź rozszerzenie **Cradle Scanner**
3. Kliknij okrągłą ikonę **Odśwież (Reload)** w prawym dolnym rogu kafelka rozszerzenia
4. Odśwież otwartą główną kartę z systemem Cradle, aby skrypty załadowały się ponownie

### 2. Restart Desktop App (Python)
Aplikacja Desktopowa **nie ma** mechanizmu auto-reload. Gdy kod w `desktop-app/` ulegnie zmianie:
1. Otwórz 3. terminal, w którym aktualnie działa na pierwszym planie proces `python src/main.py`
2. Wciśnij na klawiaturze `Ctrl + C`, aby bezpiecznie wymusić zatrzymanie serwera WebSocket i zwolnić port
3. Wciśnij strzałkę w górę (aby przywołać poprzednią komendę wiersza poleceń) lub wpisz ręcznie:
```bash
python src/main.py
```
> **Uwaga**: Kliknięcie Enter zatwierdzi komendę i połączy WebSocketa od nowa.

### 3. Restart Backendu (FastAPI)
Zazwyczaj **nie jest wymagany** - uvicorn przeładowuje się sam dzięki fladze `--reload`. Jeśli jednak proces zawiesi się lub musisz zrestartować go ręcznie:
1. Wyszukaj główny terminal (z działającym procesem `uvicorn`)
2. Wciśnij `Ctrl + C`, by bezpiecznie wyłączyć serwer.
3. Wciśnij strzałkę w górę lub wklej pełną komendę:
```bash
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### 4. Restart Frontendu (React)
Zazwyczaj również **nie jest wymagany** - React używa na nowo *Fast Refresh*. W razie problemów (np. zmiana paczek w `node_modules`):
1. Wyszukaj terminal, w którym działa proces `npm start`
2. Wciśnij `Ctrl + C` (jeśli system zapyta "Terminate batch job?", wpisz `Y` i zatwierdź Enterem).
3. Wciśnij strzałkę w górę lub wpisz komendę startową:
```bash
npm start
```