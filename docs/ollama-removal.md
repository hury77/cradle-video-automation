# Usunięcie Ollamy z maszyny (checklista manualna)

> **Uwaga:** poniższe kroki dotyczą wyłącznie środowiska lokalnego po wdrożeniu usunięcia Ollamy z kodu. Nie wykonuj ich przed potwierdzeniem stabilności `live`.

1. **Weryfikacja aktywnych procesów i portu `11434`:**
   ```bash
   lsof -nP -iTCP:11434 -sTCP:LISTEN
   pgrep -fl ollama
   ```
   Oczekiwany wynik: brak nasłuchu i brak procesów `ollama`.

2. **Usunięcie binarki i aplikacji (jeśli występują):**
   - Binarka CLI: `rm -f ~/.local/bin/ollama`
   - Aplikacja macOS (jeśli zainstalowana): `rm -rf /Applications/Ollama.app`
   - Ewentualne wpisy `LaunchAgents` / Login Items:
     ```bash
     ls -la ~/Library/LaunchAgents/*ollama* /Library/LaunchAgents/*ollama* 2>/dev/null
     ```
     Jeśli istnieją, wyładuj przez `launchctl bootout` i usuń plik `.plist`.

3. **Usunięcie katalogu wag i cache (`~/.ollama`):**
   ```bash
   du -sh ~/.ollama
   rm -rf ~/.ollama
   ```

4. **Usunięcie pakietu Pythona ze środowiska `cradle-env`:**
   ```bash
   /Users/hubert.rycaj/miniforge3/envs/cradle-env/bin/pip uninstall -y ollama
   ```

5. **Końcowa weryfikacja:**
   - Ponowne sprawdzenie `lsof -nP -iTCP:11434 -sTCP:LISTEN` (puste) oraz `which ollama` (brak).
