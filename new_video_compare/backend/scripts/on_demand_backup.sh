#!/usr/bin/env bash
# on_demand_backup.sh
# Skrypt do ręcznego wymuszenia backupu przed operacjami na systemie (np. deploy)

echo "⏳ Uruchamianie backupu on-demand..."
python3 "$(dirname "$0")/backup_db.py"
echo "✅ Backup on-demand zakończony."
