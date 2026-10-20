#!/usr/bin/env bash
# git_hook_backup.sh - Zabezpieczenie przed modyfikacjami Git
# Ten skrypt kopiuje bazę danych przed zmianą gałęzi lub mergem.
#
# UWAGA DOTYCZĄCA TRYBU WAL (Write-Ahead Logging):
# Obecna produkcyjna baza działa w trybie 'delete' (journal_mode=delete).
# Jeśli baza zostanie przełączona na tryb WAL, bezpośrednie polecenie 'cp'
# oraz haszowanie samego pliku .db będzie niewystarczające (ryzyko braku spójności
# transakcji znajdujących się w pliku -wal). Przy przejściu na WAL należy
# zastąpić 'cp' wywołaniem SQLite Online Backup API:
#   sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/git_pre_op_backup_${TIMESTAMP}.db'"
# lub wymusić uprzednio checkpoint: sqlite3 "$DB_PATH" "PRAGMA wal_checkpoint(TRUNCATE);"

DB_PATH="${DB_PATH:-$HOME/.cradle_data/new_video_compare.db}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/.cradle_data/backups}"
TIMESTAMP=$(date +"%Y-%m-%d_%H%M%S")

if [ -f "$DB_PATH" ]; then
    mkdir -p "$BACKUP_DIR"

    SHOULD_BACKUP=true

    # Znajdź najnowszą istniejącą kopię git_pre_op_backup_*.db (jeśli istnieje)
    LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/git_pre_op_backup_*.db 2>/dev/null | head -n 1)

    if [ -n "$LATEST_BACKUP" ] && [ -f "$LATEST_BACKUP" ]; then
        # Szybkie porównanie rozmiaru w bajtach (fail-closed przy błędzie)
        DB_SIZE=$(stat -f %z "$DB_PATH" 2>/dev/null || stat -c %s "$DB_PATH" 2>/dev/null)
        LATEST_SIZE=$(stat -f %z "$LATEST_BACKUP" 2>/dev/null || stat -c %s "$LATEST_BACKUP" 2>/dev/null)

        if [ -n "$DB_SIZE" ] && [ -n "$LATEST_SIZE" ] && [ "$DB_SIZE" = "$LATEST_SIZE" ]; then
            # Obliczenie hashów SHA-256
            DB_HASH=$(shasum -a 256 "$DB_PATH" 2>/dev/null | awk '{print $1}')
            LATEST_HASH=$(shasum -a 256 "$LATEST_BACKUP" 2>/dev/null | awk '{print $1}')

            # Pomiń kopię TYLKO wtedy, gdy oba hashe są niepuste i identyczne
            if [ -n "$DB_HASH" ] && [ -n "$LATEST_HASH" ] && [ "$DB_HASH" = "$LATEST_HASH" ]; then
                SHOULD_BACKUP=false
                echo "🛡️ Git Hook: Baza danych jest identyczna z najnowszą kopią (${LATEST_BACKUP##*/}). Pomijam redundantny zrzut."
            fi
        fi
    fi

    if [ "$SHOULD_BACKUP" = true ]; then
        cp "$DB_PATH" "$BACKUP_DIR/git_pre_op_backup_${TIMESTAMP}.db" 2>/dev/null || true
        chflags uchg "$BACKUP_DIR/git_pre_op_backup_${TIMESTAMP}.db" 2>/dev/null || true
        echo "🛡️ Git Hook: Wykonano zrzut bazy po operacji Git (git_pre_op_backup_${TIMESTAMP}.db)"
    fi
fi
