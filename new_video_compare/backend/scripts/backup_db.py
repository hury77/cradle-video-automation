#!/usr/bin/env python3
"""
backup_db.py — Automatyczny bezpieczny backup bazy danych Knowledge Base.
Korzysta z SQLite Online Backup API.

ARCHITEKTURA I ZASADY BEZPIECZEŃSTWA:
1. Spójność transakcyjna: Wykorzystuje SQLite Online Backup API (src.backup(dst))
   do pliku tymczasowego .tmp.
2. Weryfikacja integralności: Przed finalizacją każdy zrzut musi przejść PRAGMA integrity_check.
3. Deduplikacja: Przed zamrożeniem zrzut .tmp jest porównywany pod kątem SHA-256
   z najnowszą istniejącą kopią db_backup_*.db. Jeśli hashe są identyczne, plik .tmp
   jest bezpiecznie usuwany, a redundantna kopia jest pomijana (oszczędność dysku).
   W przypadku jakiegokolwiek błędu porównania, skrypt fail-closed tworzy kopię.
4. Atomowe linkowanie: Wykorzystuje os.link (no-clobber) do zapisu docelowego.
5. Zamrożenie (uchg): Każda zatwierdzona kopia otrzymuje flagę systemową uchg.
6. Retencja: Automatyczne usuwanie jest WYŁĄCZONE (zarządzanie retencją to osobna decyzja,
   realizowana przez dedykowane narzędzia z audytem).
7. Offsite / iCloud: Wysyłka zewnętrzna (np. iCloud) to osobna decyzja architektoniczna
   i nie jest wykonywana w podstawowym cyklu lokalnym.
"""
import hashlib
import logging
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from datetime import datetime

# Ścieżki
DB_PATH = Path(os.environ.get("DB_PATH", Path.home() / ".cradle_data/new_video_compare.db"))
BACKUPS_DIR = Path(os.environ.get("BACKUPS_DIR", Path.home() / ".cradle_data/backups"))
LOG_DIR = Path(os.environ.get("LOG_DIR", Path.home() / ".cradle_data/logs"))
LOG_PATH = LOG_DIR / "backup.log"

# Logging
LOG_DIR.mkdir(exist_ok=True, mode=0o700)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BACKUP] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def check_integrity(db_path: Path) -> bool:
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        conn.close()
        if result and result[0].lower() == "ok":
            return True
        logger.error(f"❌ Błąd integralności bazy (PRAGMA integrity_check): {result}")
        return False
    except Exception as e:
        logger.error(f"❌ Wyjątek podczas sprawdzania integralności: {e}")
        return False


def calculate_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def run_backup() -> bool:
    if not DB_PATH.exists():
        logger.error(f"❌ Plik bazy nie istnieje: {DB_PATH}")
        return False

    BACKUPS_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    final_backup_name = f"db_backup_{timestamp}.db"
    final_backup_path = BACKUPS_DIR / final_backup_name
    tmp_backup_path = BACKUPS_DIR / f"{final_backup_name}.tmp"

    if final_backup_path.exists() or tmp_backup_path.exists():
        logger.error(f"❌ Plik docelowy lub tymczasowy już istnieje: {final_backup_name}")
        return False

    try:
        # 1. Kopiowanie SQLite Online Backup
        logger.info(f"Tworzenie kopii bazy online do pliku tymczasowego: {tmp_backup_path.name}")
        src = sqlite3.connect(str(DB_PATH))
        dst = sqlite3.connect(str(tmp_backup_path))
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()

        # 2. Test Integralności
        if not check_integrity(tmp_backup_path):
            logger.error("❌ SKORUMPOWANY BACKUP! Plik .tmp nie przeszedł PRAGMA integrity_check. Pozostawiam do analizy bez flagi uchg.")
            return False

        # 3. Deduplikacja: Porównanie z najnowszą istniejącą kopią db_backup_*.db
        existing_db_backups = sorted(
            [f for f in BACKUPS_DIR.glob("db_backup_*.db") if f.is_file() and not f.name.endswith(".tmp")],
            key=lambda p: p.stat().st_mtime
        )
        if existing_db_backups:
            latest_existing = existing_db_backups[-1]
            try:
                # Szybki pre-check rozmiaru
                if tmp_backup_path.stat().st_size == latest_existing.stat().st_size:
                    tmp_sha = calculate_sha256(tmp_backup_path)
                    latest_sha = calculate_sha256(latest_existing)
                    if tmp_sha and latest_sha and tmp_sha == latest_sha:
                        logger.info(f"🛡️ Deduplikacja: Baza danych jest identyczna z najnowszą kopią ({latest_existing.name}). Pomijam zrzut.")
                        tmp_backup_path.unlink()
                        return True
            except Exception as dedup_err:
                logger.warning(f"⚠️ Błąd podczas sprawdzania deduplikacji ({dedup_err}). Kontynuuję standardowy zapis (fail-closed).")

        # 4. Zmiana nazwy z .tmp na finalną (Atomic No-Clobber)
        try:
            os.link(str(tmp_backup_path), str(final_backup_path))
            tmp_backup_path.unlink()
        except FileExistsError:
            logger.error(f"❌ Kolizja! Plik docelowy {final_backup_name} niespodziewanie istnieje podczas próby zapisu. Przerywam.")
            return False

        # 5. Zamrożenie (uchg)
        subprocess.run(["chflags", "uchg", str(final_backup_path)], check=True)
        size_mb = final_backup_path.stat().st_size / (1024 * 1024)
        logger.info(f"✅ Backup zapisany, sprawdzony (ok) i zamrożony (uchg): {final_backup_name} ({size_mb:.1f} MB)")
    except Exception as e:
        logger.error(f"❌ Błąd podczas wykonywania zrzutu bazy: {e}")
        return False

    # 6. RETENCJA WYŁĄCZONA (Zarządzana osobnym procesem retencji)
    all_backups = sorted(BACKUPS_DIR.glob("db_backup_*.db"))
    logger.info(f"📦 Łącznie backupów lokalnych: {len(all_backups)}")
    return True


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🔒 Cradle DB Backup — start (Bezpieczny Online Backup z deduplikacją)")
    success = run_backup()
    if success:
        logger.info("✅ Zakończono pomyślnie")
        logger.info("=" * 50)
        sys.exit(0)
    else:
        logger.info("❌ Zakończono z błędem")
        logger.info("=" * 50)
        sys.exit(1)
