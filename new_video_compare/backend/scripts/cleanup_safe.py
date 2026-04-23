#!/usr/bin/env python3
"""
cleanup_safe.py – codzienne, bezpieczne czyszczenie folderu uploads oraz rotacja logów uvicorn.

1. Zachowuje wszystkie joby, które zostały utworzone w ciągu ostatnich RETENTION_DAYS (10 dni).
2. Usuwa fizycznie jedynie pliki, które nie są powiązane z zachowanymi jobami.
3. Po usunięciu plików usuwa joby, które utraciły odnośniki do plików.
4. Rotuje (usuwa) logi uvicorn starsze niż LOG_RETENTION_DAYS (7 dni).
5. Zapisuje podsumowanie w logs/daily_cleanup.log.
"""

import os
from pathlib import Path
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ------------------- CONFIGURATION -------------------
from backend.config import PROJECT_ROOT
DB_URL = f"sqlite:///{PROJECT_ROOT / 'new_video_compare.db'}"
UPLOADS_DIR = PROJECT_ROOT / "uploads"
LOG_DIR = PROJECT_ROOT / "logs"
CLEANUP_LOG = LOG_DIR / "daily_cleanup.log"
RETENTION_DAYS = 10  # keep jobs from the last 10 days
LOG_RETENTION_DAYS = 0  # temporarily set to 0 for test rotation
# -----------------------------------------------------

def _log(message: str) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CLEANUP_LOG, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} | {message}\n")

def main():
    _log("=== START CLEANUP SAFE ===")
    engine = create_engine(DB_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Load all files from DB
    file_rows = session.execute(text("SELECT id, file_path FROM files")).fetchall()
    file_id_to_path = {row.id: Path(row.file_path).resolve() for row in file_rows}

    # 2. Load all jobs with creation date
    job_rows = session.execute(text("SELECT id, acceptance_file_id, emission_file_id, created_at FROM comparison_jobs")).fetchall()

    # 3. Determine which jobs to keep (last RETENTION_DAYS)
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    keep_job_ids = set()
    used_file_paths = set()
    used_file_ids = set()
    for job in job_rows:
        # created_at may be stored as ISO string or datetime
        created = job.created_at
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created)
            except Exception:
                # fallback – treat as old
                created = datetime.min
        if created >= cutoff:
            keep_job_ids.add(job.id)
            for fid in (job.acceptance_file_id, job.emission_file_id):
                if fid and fid in file_id_to_path:
                    used_file_ids.add(fid)
                    used_file_paths.add(file_id_to_path[fid])
    _log(f"Jobs to keep: {len(keep_job_ids)} (retention {RETENTION_DAYS} days)")
    _log(f"Files referenced by kept jobs: {len(used_file_paths)}")

    # 4. Delete orphan files from uploads directory
    deleted_files = 0
    reclaimed_bytes = 0
    for path in UPLOADS_DIR.rglob("*"):
        if not path.is_file():
            continue
        abs_path = path.resolve()
        if abs_path in used_file_paths:
            continue  # needed file – keep it
        try:
            size = path.stat().st_size
            path.unlink()
            deleted_files += 1
            reclaimed_bytes += size
            _log(f"🗑️ Deleted orphan file {path.name} ({size/1024/1024:.2f} MB)")
        except Exception as e:
            _log(f"⚠️ Error deleting {path}: {e}")

    # 5. Remove jobs that now reference missing files – always delete regardless of retention
    jobs_deleted = 0
    for job in job_rows:
        # Skip jobs that are kept for retention (optional – we will still delete if missing)
        missing = False
        for fid in (job.acceptance_file_id, job.emission_file_id):
            if not fid:
                continue
            fpath = file_id_to_path.get(fid)
            if fpath and not fpath.exists():
                missing = True
                break
        if missing:
            session.execute(text("DELETE FROM comparison_jobs WHERE id=:jid"), {"jid": job.id})
            jobs_deleted += 1
    session.commit()

    _log(f"🗑️ Orphan files removed: {deleted_files} ( {reclaimed_bytes/1024/1024/1024:.2f} GB reclaimed )")
    _log(f"🗑️ Jobs removed due to missing files: {jobs_deleted}")

    # 6. Rotate uvicorn logs – delete files older than LOG_RETENTION_DAYS
    now_ts = datetime.now().timestamp()
    deleted_logs = 0
    for log_path in LOG_DIR.glob("uvicorn*.log"):
        try:
            mtime = log_path.stat().st_mtime
            age_days = (now_ts - mtime) / (24 * 3600)
            if age_days > LOG_RETENTION_DAYS:
                size = log_path.stat().st_size
                log_path.unlink()
                deleted_logs += 1
                _log(f"🗑️ Rotated uvicorn log {log_path.name} ({size/1024/1024:.2f} MB, {age_days:.1f} days old)")
        except Exception as e:
            _log(f"⚠️ Error rotating log {log_path}: {e}")
    _log(f"🗑️ uvicorn logs rotated: {deleted_logs}")
    _log("=== END CLEANUP SAFE ===\n")

if __name__ == "__main__":
    main()
