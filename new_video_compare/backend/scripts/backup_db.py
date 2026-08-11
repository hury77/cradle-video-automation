#!/usr/bin/env python3
"""
backup_db.py — Automatyczny backup bazy danych Knowledge Base (new_video_compare.db)

Kopiuje aktualną bazę do katalogu backups/ z datą w nazwie.
Sprawdza integralność bazy przed zamrożeniem (uchg).
Kompresuje bazę i wysyła do iCloud Drive (Offsite Backup).
Usuwa backupy starsze niż 30 dni, ale ZAWSZE zachowuje minimum 3 najnowsze kopie.
"""
import shutil
import logging
import subprocess
import sqlite3
import gzip
from pathlib import Path
from datetime import datetime, timedelta

# Ścieżki
SCRIPT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = SCRIPT_DIR.parent
DB_PATH = Path.home() / ".cradle_data/new_video_compare.db"
BACKUPS_DIR = Path.home() / ".cradle_data/backups"
ICLOUD_BACKUPS_DIR = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/CradleBackups"
LOG_DIR = BACKEND_DIR / "logs"
LOG_PATH = LOG_DIR / "backup.log"
KEEP_DAYS = 30
MIN_BACKUPS_TO_KEEP = 3

# Logging
LOG_DIR.mkdir(exist_ok=True)
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
        logger.error(f"❌ Błąd integralności bazy: {result}")
        return False
    except Exception as e:
        logger.error(f"❌ Wyjątek podczas sprawdzania integralności: {e}")
        return False


def run_backup():
    if not DB_PATH.exists():
        logger.error(f"❌ Plik bazy nie istnieje: {DB_PATH}")
        return False

    BACKUPS_DIR.mkdir(exist_ok=True)
    ICLOUD_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    # Nazwa backupu z datą i godziną
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_name = f"db_backup_{timestamp}.db"
    backup_path = BACKUPS_DIR / backup_name
    icloud_backup_path = ICLOUD_BACKUPS_DIR / f"{backup_name}.gz"

    try:
        # 1. Kopiowanie
        shutil.copy2(DB_PATH, backup_path)
        
        # 2. Test Integralności
        if not check_integrity(backup_path):
            logger.error("❌ SKORUMPOWANY BACKUP! Baza nie przeszła PRAGMA integrity_check. Usuwam zrzut.")
            backup_path.unlink()
            return False
            
        # 3. Offsite Backup (iCloud Drive Gzip)
        logger.info(f"☁️ Kompresowanie i wysyłanie backupu do iCloud...")
        with open(backup_path, 'rb') as f_in:
            with gzip.open(icloud_backup_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        icloud_size_mb = icloud_backup_path.stat().st_size / (1024 * 1024)
        logger.info(f"☁️ iCloud Backup zapisany: {icloud_backup_path.name} ({icloud_size_mb:.1f} MB)")

        # 4. Zamrożenie (uchg)
        subprocess.run(["chflags", "uchg", str(backup_path)], check=True)
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        logger.info(f"✅ Backup zapisany, sprawdzony (ok) i zamrożony (uchg): {backup_name} ({size_mb:.1f} MB)")
    except Exception as e:
        logger.error(f"❌ Błąd podczas wykonywania zrzutu bazy: {e}")
        return False

    # 5. Bezpieczna retencja (Zawsze zostawiaj MIN_BACKUPS_TO_KEEP)
    all_backups = sorted(BACKUPS_DIR.glob("db_backup_*.db"), key=lambda p: p.stat().st_mtime)
    if len(all_backups) <= MIN_BACKUPS_TO_KEEP:
        logger.info(f"🛡️ Retencja pominięta: liczba backupów ({len(all_backups)}) <= minimum ({MIN_BACKUPS_TO_KEEP}).")
    else:
        # Kandydaci do usunięcia to wszyscy poza najnowszymi MIN_BACKUPS_TO_KEEP
        candidates_for_deletion = all_backups[:-MIN_BACKUPS_TO_KEEP]
        cutoff = datetime.now() - timedelta(days=KEEP_DAYS)
        removed = 0
        
        for old_backup in candidates_for_deletion:
            try:
                mtime = datetime.fromtimestamp(old_backup.stat().st_mtime)
                if mtime < cutoff:
                    # Zdjęcie flagi immutable przed próbą usunięcia
                    subprocess.run(["chflags", "nouchg", str(old_backup)], check=True)
                    old_backup.unlink()
                    removed += 1
                    logger.info(f"🗑️ Usunięto stary backup: {old_backup.name}")
            except Exception as e:
                logger.warning(f"⚠️ Nie można usunąć {old_backup.name}: {e}")

        if removed:
            logger.info(f"🧹 Usunięto {removed} starych backupów (>{KEEP_DAYS} dni)")

    # Podsumowanie
    all_backups = sorted(BACKUPS_DIR.glob("db_backup_*.db"))
    logger.info(f"📦 Łącznie backupów lokalnych: {len(all_backups)}")
    return True


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🔒 Cradle DB Backup — start")
    success = run_backup()
    logger.info(f"{'✅ Zakończono pomyślnie' if success else '❌ Zakończono z błędem'}")
    logger.info("=" * 50)
