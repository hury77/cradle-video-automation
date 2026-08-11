#!/usr/bin/env bash
# git_hook_backup.sh - Zabezpieczenie przed modyfikacjami Git
# Ten skrypt kopiuje bazę danych przed zmianą gałęzi lub mergem.

DB_PATH="$HOME/.cradle_data/new_video_compare.db"
BACKUP_DIR="$HOME/.cradle_data/backups"
TIMESTAMP=$(date +"%Y-%m-%d_%H%M%S")

if [ -f "$DB_PATH" ]; then
    mkdir -p "$BACKUP_DIR"
    cp "$DB_PATH" "$BACKUP_DIR/git_pre_op_backup_${TIMESTAMP}.db" 2>/dev/null || true
    chflags uchg "$BACKUP_DIR/git_pre_op_backup_${TIMESTAMP}.db" 2>/dev/null || true
    echo "🛡️ Git Hook: Wykonano zrzut bazy po operacji Git (git_pre_op_backup_${TIMESTAMP}.db)"
fi
