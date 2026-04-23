#!/usr/bin/env bash
# daily_cleanup.sh – wrapper uruchamiający cleanup_safe.py w wirtualnym środowisku

# Przejdź do katalogu repozytorium (zakładamy, że skrypt jest w new_video_compare/backend/scripts/)
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/../../.." && pwd)

cd "$PROJECT_ROOT"

# Aktywuj wirtualne środowisko (przyjmujemy, że .venv znajduje się w repozytorium)
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "[ERROR] Nie znaleziono .venv – upewnij się, że środowisko jest skonfigurowane."
    exit 1
fi

# Uruchom skrypt czyszczący
python "new_video_compare/backend/scripts/cleanup_safe.py"
