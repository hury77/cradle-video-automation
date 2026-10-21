#!/usr/bin/env bash
# git_hook_backup.sh - Zabezpieczenie bazy danych przed modyfikacjami Git
# Wykorzystuje SQLite Online Backup API przez backup_db.py --prefix git_pre_op_backup_
#
# ZASADY DZIAŁANIA I KODY WYJŚCIA:
# 1. Korzysta z tego samego bezpiecznego silnika co cykliczny backup (Online Backup API,
#    weryfikacja integralności PRAGMA integrity_check, deduplikacja, zamrożenie uchg).
# 2. Zachowuje zmienne środowiskowe: DB_PATH, BACKUPS_DIR, LOG_DIR.
# 3. Zapisuje oddzielny stan w backup_status_git_pre_op_backup.json (nie narusza monitoringu db_backup).
# 4. Propaguje niezerowy kod wyjścia, aby nie ukrywać awarii (brak || true).
# 5. Jeśli hook wywołany jest po przełączeniu gałęzi (post-checkout), awaria backupu
#    zostaje wypisana na stderr, lecz nie cofa automatycznie checkoutu (przełączenie już nastąpiło).
# 6. Jeśli hook wywołany jest przed zatwierdzeniem merge (pre-merge-commit), niezerowy kod
#    zablokuje utworzenie commitu merge; operator może wykonać `git merge --abort`
#    lub rozwiązać problem spójności bazy danych.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_PY="$SCRIPT_DIR/backup_db.py"

if [ ! -f "$BACKUP_PY" ]; then
    echo "❌ BŁĄD KRYTYCZNY HOOKA: Nie znaleziono skryptu zrzutu bazy: $BACKUP_PY" >&2
    exit 1
fi

# Wywołanie bezpiecznego silnika z dedykowanym prefiksem hooka
python3 "$BACKUP_PY" --prefix git_pre_op_backup_
rc=$?
if [ $rc -ne 0 ]; then
    echo "" >&2
    echo "❌ BŁĄD BACKUPU: Nie udało się zabezpieczyć bazy danych przed operacją Git (kod błędu: $rc)!" >&2
    echo "ℹ️ Wskazówka:" >&2
    echo "  - Przy pre-merge-commit: merge commit został wstrzymany. Użyj git merge --abort lub napraw bazę." >&2
    echo "  - Przy post-checkout: gałąź została już zmieniona w Git, lecz baza NIE została zabezpieczona." >&2
    echo "  - Sprawdź logi w: ${LOG_DIR:-$HOME/.cradle_data/logs}/backup.log" >&2
    exit $rc
fi
