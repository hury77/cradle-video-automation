#!/usr/bin/env python3
"""
backup_status.py — Narzędzie tylko do odczytu (monitoring stanu kopii bazy).

Sprawdza plik backup_status.json w LOG_DIR.
Kryteria sukcesu (kod 0):
- Plik stanu istnieje i jest poprawny.
- Ostatni udany cykl (last_success_at lub timestamp przy created/skipped) nie jest starszy niż 12 godzin.
- consecutive_failures < 3.

W przeciwnym wypadku kończy działanie z kodem wyjścia != 0 (1 lub 2).
"""
import argparse
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

def inspect_status(status_file_path: Path) -> int:
    if not status_file_path.exists():
        print(f"CRITICAL: Brak pliku stanu backupu: {status_file_path}")
        return 2

    try:
        data = json.loads(status_file_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"CRITICAL: Niepoprawny format pliku stanu ({e})")
        return 2

    last_ts_str = data.get("timestamp")
    last_success_str = data.get("last_success_at") or (last_ts_str if data.get("result") in ("created", "skipped_duplicate") else None)
    result = data.get("result", "unknown")
    consecutive_skips = data.get("consecutive_skips", 0)
    consecutive_failures = data.get("consecutive_failures", 0)
    last_backup_name = data.get("last_successful_backup", "brak")

    now = datetime.now(timezone.utc)
    age_hours = None
    if last_success_str:
        try:
            # Obsługa formatu ISO z timezone
            dt_success = datetime.fromisoformat(last_success_str)
            age_hours = (now - dt_success).total_seconds() / 3600.0
        except Exception:
            pass

    print("=== CRADLE DB BACKUP STATUS ===")
    print(f"Ostatni cykl:            {last_ts_str} (wynik: {result})")
    print(f"Ostatnia udana kopia:    {last_backup_name}")
    if age_hours is not None:
        print(f"Wiek udanego cyklu:      {age_hours:.1f} godz.")
    else:
        print("Wiek udanego cyklu:      NIEZNANY / BRAK UDANYCH CYKLI")
    print(f"Kolejne pominięcia:      {consecutive_skips}")
    print(f"Kolejne awarie:          {consecutive_failures}")

    if data.get("last_failure_reason"):
        print(f"Ostatni błąd:            {data.get('last_failure_reason')} ({data.get('last_failure_at')})")

    # Kryteria zdrowia
    is_healthy = True
    reasons = []

    if consecutive_failures >= 3:
        is_healthy = False
        reasons.append(f"Zbyt wiele kolejnych awarii ({consecutive_failures} >= 3)")

    if age_hours is None or age_hours > 12.0:
        is_healthy = False
        reasons.append(f"Ostatni udany cykl jest starszy niż 12h ({age_hours:.1f}h)" if age_hours is not None else "Brak zarejestrowanego udanego cyklu")

    if is_healthy:
        print("\n✅ STATUS: ZDROWY (OK)")
        return 0
    else:
        print("\n❌ STATUS: NIEZDROWY (CRITICAL)")
        for r in reasons:
            print(f"  - {r}")
        return 1

def resolve_status_file(status_file_arg: str, prefix_arg: str) -> Path:
    if status_file_arg:
        return Path(status_file_arg)

    log_dir = Path(os.environ.get("LOG_DIR", Path.home() / ".cradle_data/logs"))
    clean_prefix = prefix_arg.rstrip("_")
    target_file = log_dir / f"backup_status_{clean_prefix}.json"

    # Fallback dla domyślnego db_backup_: jeśli nie ma nowego pliku, sprawdź legacy backup_status.json
    if not target_file.exists() and clean_prefix == "db_backup":
        legacy_file = log_dir / "backup_status.json"
        if legacy_file.exists():
            return legacy_file

    return target_file

def main():
    parser = argparse.ArgumentParser(description="Monitoring stanu backupów bazy Cradle (read-only).")
    parser.add_argument(
        "--status-file",
        type=str,
        default=None,
        help="Bezpośrednia ścieżka do pliku statusu (nadpisuje --prefix)"
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="db_backup_",
        choices=["db_backup_", "git_pre_op_backup_"],
        help="Prefiks zrzutu (db_backup_ dla cyklicznego, git_pre_op_backup_ dla hooka Git, domyślnie db_backup_)"
    )
    args = parser.parse_args()
    status_path = resolve_status_file(args.status_file, args.prefix)
    rc = inspect_status(status_path)
    sys.exit(rc)

if __name__ == "__main__":
    main()
