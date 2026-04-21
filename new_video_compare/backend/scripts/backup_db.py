#!/usr/bin/env python3
"""
backup_db.py — Automatyczny backup bazy danych Knowledge Base (new_video_compare.db)

Uruchamiany codziennie o 21:00 przez launchd.
Kopiuje aktualną bazę do katalogu backups/ z datą w nazwie.
Usuwa backupy starsze niż 30 dni.

Zgodny z zasadami SOUL.md: baza jest "Biblią systemu" i musi być regularnie archiwizowana.
"""
import shutil
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Ścieżki
SCRIPT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = SCRIPT_DIR.parent
DB_PATH = BACKEND_DIR / "new_video_compare.db"
BACKUPS_DIR = BACKEND_DIR / "backups"
LOG_DIR = BACKEND_DIR / "logs"
LOG_PATH = LOG_DIR / "backup.log"
KEEP_DAYS = 30

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


def run_backup():
    if not DB_PATH.exists():
        logger.error(f"❌ Plik bazy nie istnieje: {DB_PATH}")
        return False

    BACKUPS_DIR.mkdir(exist_ok=True)

    # Nazwa backupu z datą i godziną
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_name = f"db_backup_{timestamp}.db"
    backup_path = BACKUPS_DIR / backup_name

    try:
        shutil.copy2(DB_PATH, backup_path)
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        logger.info(f"✅ Backup zapisany: {backup_name} ({size_mb:.1f} MB)")
    except Exception as e:
        logger.error(f"❌ Błąd podczas kopiowania bazy: {e}")
        return False

    # Usuń backupy starsze niż KEEP_DAYS dni
    cutoff = datetime.now() - timedelta(days=KEEP_DAYS)
    removed = 0
    for old_backup in BACKUPS_DIR.glob("db_backup_*.db"):
        try:
            mtime = datetime.fromtimestamp(old_backup.stat().st_mtime)
            if mtime < cutoff:
                old_backup.unlink()
                removed += 1
                logger.info(f"🗑️ Usunięto stary backup: {old_backup.name}")
        except Exception as e:
            logger.warning(f"⚠️ Nie można usunąć {old_backup.name}: {e}")

    if removed:
        logger.info(f"🧹 Usunięto {removed} starych backupów (>{KEEP_DAYS} dni)")

    # Podsumowanie
    all_backups = sorted(BACKUPS_DIR.glob("db_backup_*.db"))
    logger.info(f"📦 Łącznie backupów: {len(all_backups)}")
    return True


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🔒 Cradle DB Backup — start")
    success = run_backup()
    logger.info(f"{'✅ Zakończono pomyślnie' if success else '❌ Zakończono z błędem'}")
    logger.info("=" * 50)
