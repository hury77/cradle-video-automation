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
4. Ochrona przed resztkami .tmp: Wykrywa pliki *.tmp starsze niż 1 godzina.
   Jeśli takich plików jest 3 lub więcej, skrypt fail-closed przerywa działanie
   (exit 1) i nie tworzy kolejnego .tmp, chroniąc dysk przed pętlą awarii.
   Nigdy nie usuwa ich automatycznie.
5. Plik stanu audytowego (backup_status.json): Zapisywany atomowo (tmp + rename)
   w LOG_DIR po każdym cyklu: timestamp, result (created / skipped_duplicate / failed),
   nazwa ostatniej kopii, consecutive_skips, consecutive_failures, last_failure_at,
   last_failure_reason.
6. Powiadomienia macOS (osascript): Przy blokadzie przez resztki .tmp oraz po >= 3
   kolejnych awariach (consecutive_failures >= 3) skrypt wysyła powiadomienie OS.
   Wywołanie to jest całkowicie nieblokujące i nie wpływa na kod wyjścia.
7. Atomowe linkowanie: Wykorzystuje os.link (no-clobber) do zapisu docelowego.
8. Zamrożenie (uchg): Każda zatwierdzona kopia otrzymuje flagę systemową uchg.
9. Retencja: Automatyczne usuwanie jest WYŁĄCZONE (zarządzana osobnym procesem retencji).
10. Offsite / iCloud: Osobna decyzja architektoniczna, poza podstawowym cyklem lokalnym.
"""
import hashlib
import json
import logging
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone

# Ścieżki
DB_PATH = Path(os.environ.get("DB_PATH", Path.home() / ".cradle_data/new_video_compare.db"))
BACKUPS_DIR = Path(os.environ.get("BACKUPS_DIR", Path.home() / ".cradle_data/backups"))
LOG_DIR = Path(os.environ.get("LOG_DIR", Path.home() / ".cradle_data/logs"))
LOG_PATH = LOG_DIR / "backup.log"
STATUS_FILE = LOG_DIR / "backup_status.json"

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


def send_macos_notification(title: str, message: str):
    """Wysyła powiadomienie macOS przez osascript. Błąd powiadomienia nie może przerwać działania."""
    try:
        # Bezpieczne oczyszczenie cudzysłowów
        safe_title = title.replace('"', '\"')
        safe_msg = message.replace('"', '\"')
        script = f'display notification "{safe_msg}" with title "{safe_title}"'
        subprocess.run(["osascript", "-e", script], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logger.warning(f"Nie udało się wysłać powiadomienia macOS: {e}")


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


def load_previous_status() -> dict:
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Nie udało się odczytać pliku stanu {STATUS_FILE}: {e}")
    return {}


def update_status(result: str, last_backup_name: str, error_message: str = None):
    """Zapisuje stan wykonania atomowo (plik tymczasowy + rename) w LOG_DIR."""
    try:
        prev = load_previous_status()
        consecutive_skips = prev.get("consecutive_skips", 0)
        consecutive_failures = prev.get("consecutive_failures", 0)
        now_iso = datetime.now(timezone.utc).isoformat()

        if result == "skipped_duplicate":
            consecutive_skips += 1
            consecutive_failures = 0
        elif result == "created":
            consecutive_skips = 0
            consecutive_failures = 0
        elif result == "failed":
            consecutive_failures += 1

        effective_last_backup = last_backup_name or prev.get("last_successful_backup")

        status_data = {
            "timestamp": now_iso,
            "result": result,
            "last_successful_backup": effective_last_backup,
            "consecutive_skips": consecutive_skips,
            "consecutive_failures": consecutive_failures,
        }

        # Zachowanie / aktualizacja znaczników czasu
        if result == "created":
            status_data["last_created_at"] = now_iso
            status_data["last_success_at"] = now_iso
        elif result == "skipped_duplicate":
            if "last_created_at" in prev:
                status_data["last_created_at"] = prev["last_created_at"]
            status_data["last_success_at"] = now_iso
        else:
            if "last_created_at" in prev:
                status_data["last_created_at"] = prev["last_created_at"]
            if "last_success_at" in prev:
                status_data["last_success_at"] = prev["last_success_at"]

        if result == "failed":
            status_data["last_failure_at"] = now_iso
            status_data["last_failure_reason"] = error_message or "Unknown failure"
        else:
            # Po udanym cyklu pola błędu są zerowane / brak aktywnego błędu
            status_data["last_failure_at"] = None
            status_data["last_failure_reason"] = None

        tmp_status = LOG_DIR / f"backup_status_{os.getpid()}_{int(time.time()*1000)}.tmp"
        tmp_status.write_text(json.dumps(status_data, indent=2), encoding="utf-8")
        os.replace(str(tmp_status), str(STATUS_FILE))

        # Alert macOS po >= 3 kolejnych błędach
        if result == "failed" and consecutive_failures >= 3:
            send_macos_notification(
                "Cradle DB Backup Alert",
                f"Kolejna awaria ({consecutive_failures}/3)! Powód: {error_message or 'Błąd zrzutu'}"
            )
    except Exception as e:
        logger.warning(f"Nie udało się zaktualizować pliku stanu {STATUS_FILE}: {e}")


def check_stale_tmp_files() -> bool:
    """
    Sprawdza obecność resztek *.tmp w BACKUPS_DIR starszych niż 1 godzina.
    Zwraca False (blokada wykonania), jeśli jest ich 3 lub więcej.
    """
    if not BACKUPS_DIR.exists():
        return True

    now = time.time()
    one_hour_ago = now - 3600
    stale_tmps = []

    for tmp_file in BACKUPS_DIR.glob("*.tmp"):
        try:
            mtime = tmp_file.stat().st_mtime
            if mtime < one_hour_ago:
                stale_tmps.append((tmp_file, mtime))
        except Exception:
            pass

    if stale_tmps:
        logger.warning(
            f"⚠️ Wykryto {len(stale_tmps)} porzuconych plików *.tmp starszych niż 1h w {BACKUPS_DIR}: "
            f"{[f[0].name for f in stale_tmps]}. Pliki te nie są usuwane automatycznie."
        )

    if len(stale_tmps) >= 3:
        msg = f"Blokada: {len(stale_tmps)} starych plików *.tmp w katalogu backups!"
        logger.error(
            f"❌ BLOKADA FAIL-CLOSED: {msg} Przerywam cykl, aby zapobiec nawarstwianiu niespójnych danych na dysku."
        )
        send_macos_notification("Cradle DB Backup Blokada", msg)
        return False

    return True


def run_backup() -> bool:
    # 0. Sprawdzenie resztek .tmp przed jakimkolwiek zapisem
    if not check_stale_tmp_files():
        update_status("failed", None, error_message="Blocked by >= 3 stale .tmp files")
        return False

    if not DB_PATH.exists():
        logger.error(f"❌ Plik bazy nie istnieje: {DB_PATH}")
        update_status("failed", None, error_message=f"DB file not found: {DB_PATH}")
        return False

    BACKUPS_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    final_backup_name = f"db_backup_{timestamp}.db"
    final_backup_path = BACKUPS_DIR / final_backup_name
    tmp_backup_path = BACKUPS_DIR / f"{final_backup_name}.tmp"

    if final_backup_path.exists() or tmp_backup_path.exists():
        logger.error(f"❌ Plik docelowy lub tymczasowy już istnieje: {final_backup_name}")
        update_status("failed", None, error_message=f"Target or tmp file collision: {final_backup_name}")
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
            update_status("failed", None, error_message="Integrity check failed on .tmp backup")
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
                        update_status("skipped_duplicate", latest_existing.name)
                        return True
            except Exception as dedup_err:
                logger.warning(f"⚠️ Błąd podczas sprawdzania deduplikacji ({dedup_err}). Kontynuuję standardowy zapis (fail-closed).")

        # 4. Zmiana nazwy z .tmp na finalną (Atomic No-Clobber)
        try:
            os.link(str(tmp_backup_path), str(final_backup_path))
            tmp_backup_path.unlink()
        except FileExistsError:
            logger.error(f"❌ Kolizja! Plik docelowy {final_backup_name} niespodziewanie istnieje podczas próby zapisu. Przerywam.")
            update_status("failed", None, error_message=f"Collision during os.link: {final_backup_name}")
            return False

        # 5. Zamrożenie (uchg)
        subprocess.run(["chflags", "uchg", str(final_backup_path)], check=True)
        size_mb = final_backup_path.stat().st_size / (1024 * 1024)
        logger.info(f"✅ Backup zapisany, sprawdzony (ok) i zamrożony (uchg): {final_backup_name} ({size_mb:.1f} MB)")
        update_status("created", final_backup_name)
    except Exception as e:
        logger.error(f"❌ Błąd podczas wykonywania zrzutu bazy: {e}")
        update_status("failed", None, error_message=str(e))
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
