import os
import shutil
import sqlite3
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Config
DB_PATH = "new_video_compare.db"
BACKUP_DIR = "backups"
UPLOADS_DIR = "uploads"
RETENTION_DAYS = 5
MIN_JOBS_TO_KEEP = 10

def backup_db():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"new_video_compare_{timestamp}.db")
    print(f"📦 Backing up database to {backup_path}...")
    try:
        shutil.copy2(DB_PATH, backup_path)
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return
    
    # Keep only last 7 backups
    try:
        backups = sorted([os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith(".db")])
        if len(backups) > 7:
            for old_backup in backups[:-7]:
                os.remove(old_backup)
                print(f"🗑️ Removed old backup: {old_backup}")
    except Exception as e:
        print(f"⚠️ Error cleaning old backups: {e}")

def get_connection():
    return sqlite3.connect(DB_PATH)

def cleanup(dry_run=True):
    if dry_run:
        print("🔍 DRY RUN MODE - No files will be deleted. Use --run to execute.")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Determine Active vs Old Jobs early
    print(f"🧹 Checking for files older than {RETENTION_DAYS} days (keeping min {MIN_JOBS_TO_KEEP} latest jobs)...")
    
    # Get 10 most recent jobs to exclude them
    cursor.execute("SELECT id FROM comparison_jobs ORDER BY id DESC LIMIT ?", (MIN_JOBS_TO_KEEP,))
    keep_job_ids = {row[0] for row in cursor.fetchall()}
    
    # Get jobs older than 5 days
    cutoff_date = (datetime.now() - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        SELECT id, acceptance_file_id, emission_file_id 
        FROM comparison_jobs 
        WHERE (UPPER(status) = 'COMPLETED' OR UPPER(status) = 'FAILED') 
        AND completed_at < ?
    """, (cutoff_date,))
    old_jobs = cursor.fetchall()
    
    jobs_to_delete_ids = set()
    files_to_delete_ids = set()
    for job_id, acc_id, emi_id in old_jobs:
        if job_id not in keep_job_ids:
            jobs_to_delete_ids.add(job_id)
            if acc_id: files_to_delete_ids.add(acc_id)
            if emi_id: files_to_delete_ids.add(emi_id)
            
    # Remove files that are still needed by the "keep" jobs (overlap check)
    if keep_job_ids and files_to_delete_ids:
        placeholders = ','.join(['?'] * len(keep_job_ids))
        cursor.execute(f"SELECT acceptance_file_id, emission_file_id FROM comparison_jobs WHERE id IN ({placeholders})", list(keep_job_ids))
        kept_file_ids = set()
        for acc_id, emi_id in cursor.fetchall():
            if acc_id: kept_file_ids.add(acc_id)
            if emi_id: kept_file_ids.add(emi_id)
        
        files_to_delete_ids -= kept_file_ids

    # All jobs in the DB
    cursor.execute("SELECT id FROM comparison_jobs")
    all_job_ids = {row[0] for row in cursor.fetchall()}
    active_job_ids_str = {str(jid) for jid in all_job_ids if jid not in jobs_to_delete_ids}

    # 2. Identify Orphaned Files
    print("🧹 Checking for orphaned files...")
    cursor.execute("SELECT file_path FROM files")
    # Store absolute paths for matching
    db_files = set()
    for row in cursor.fetchall():
        path_str = row[0]
        if path_str:
            db_files.add(str(Path(path_str).absolute()))
    
    uploads_path = Path(UPLOADS_DIR).absolute()
    orphaned_count = 0
    orphaned_size = 0
    
    # Scan uploads directory recursively
    if uploads_path.exists():
        for file_path in uploads_path.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith("."):
                abs_path = str(file_path.absolute())
                
                # Check if file is NOT in DB
                if abs_path not in db_files:
                    # Safety check for job temp files (e.g. diff_frames for ACTIVE jobs)
                    is_active_job_file = False
                    for part in file_path.parts:
                        if part.startswith("job_"):
                            job_id_str = part[4:]
                            if job_id_str in active_job_ids_str:
                                is_active_job_file = True
                                break
                                
                    if is_active_job_file:
                        continue
                        
                    orphaned_count += 1
                    try:
                        size = file_path.stat().st_size
                        orphaned_size += size
                        if not dry_run:
                            os.remove(file_path)
                            print(f"🗑️ Deleted orphan: {file_path.name}")
                        else:
                            print(f"Found orphan: {file_path.name} ({size / 1024 / 1024:.2f} MB)")
                    except Exception as e:
                        print(f"⚠️ Error processing orphan {file_path}: {e}")

    # 3. Clean empty directories (optional, but good for cleanup)
    if not dry_run and uploads_path.exists():
        for dir_path in uploads_path.rglob("*"):
            if dir_path.is_dir():
                try:
                    dir_path.rmdir()
                except:
                    pass
            
    job_files_deleted = 0
    job_files_size = 0
    
    if files_to_delete_ids:
        placeholders = ','.join(['?'] * len(files_to_delete_ids))
        cursor.execute(f"SELECT file_path FROM files WHERE id IN ({placeholders})", list(files_to_delete_ids))
        paths_to_delete = [row[0] for row in cursor.fetchall()]
        
        for path in paths_to_delete:
            p = Path(path)
            if p.exists():
                try:
                    size = p.stat().st_size
                    job_files_deleted += 1
                    job_files_size += size
                    if not dry_run:
                        os.remove(p)
                        print(f"🗑️ Deleted video: {p.name}")
                    else:
                        print(f"Found old job video: {p.name} ({size / 1024 / 1024:.2f} MB)")
                    
                    # Cleanup proxies
                    proxy_dir = p.parent / "proxies"
                    if proxy_dir.exists():
                        for pf in proxy_dir.iterdir():
                            if p.stem in pf.name:
                                p_size = pf.stat().st_size
                                job_files_deleted += 1
                                job_files_size += p_size
                                if not dry_run:
                                    pf.unlink()
                                else:
                                    print(f"Found proxy: {pf.name} ({p_size / 1024 / 1024:.2f} MB)")
                except Exception as e:
                    print(f"⚠️ Error deleting {path}: {e}")

    conn.close()
    
    print("-" * 40)
    print(f"🎉 Cleanup Summary:")
    print(f"Orphaned files found/deleted: {orphaned_count}")
    print(f"Orphaned space: {orphaned_size / 1024 / 1024:.2f} MB")
    print(f"Job video/proxy files deleted: {job_files_deleted}")
    print(f"Job space: {job_files_size / 1024 / 1024:.2f} MB")
    print(f"TOTAL RECLAIMED SPACE: {(orphaned_size + job_files_size) / (1024 * 1024 * 1024):.2f} GB")
    print("-" * 40)
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart cleanup for video automation files.")
    parser.add_argument("--run", action="store_true", help="Actually run deletion (otherwise dry-run)")
    args = parser.parse_args()
    
    print(f"🚀 Starting Smart Cleanup at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    backup_db()
    cleanup(dry_run=not args.run)
