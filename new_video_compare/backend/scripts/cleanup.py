
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Add parent dir to path to import models
sys.path.append(str(Path(__file__).parent.parent))

from models.database import SessionLocal
from models.models import ComparisonJob, File, JobStatus
from sqlalchemy import or_

def cleanup(days=14, count=50, dry_run=False):
    db = SessionLocal()
    try:
        threshold_date = datetime.now() - timedelta(days=days)
        print(f"🧹 Starting cleanup for jobs older than {days} days ({threshold_date})...")
        
        jobs_to_delete = (
            db.query(ComparisonJob)
            .filter(
                ComparisonJob.status.in_([JobStatus.COMPLETED, JobStatus.FAILED]),
                ComparisonJob.created_at < threshold_date
            )
            .order_by(ComparisonJob.created_at.asc())
            .limit(count)
            .all()
        )
        
        print(f"🔍 Found {len(jobs_to_delete)} jobs to delete.")
        
        if dry_run:
            print("🚀 DRY RUN: No deletions will be performed.")
            
        deleted_count = 0
        freed_space = 0
        
        for job in jobs_to_delete:
            files_to_check = [job.acceptance_file_id, job.emission_file_id]
            
            if not dry_run:
                print(f"🗑️ Deleting Job {job.id}: {job.job_name}")
                db.delete(job)
                db.flush()
                deleted_count += 1
            else:
                print(f"👀 Would delete Job {job.id}: {job.job_name}")
                
            # Orphan file cleanup logic (simplified for CLI)
            for file_id in files_to_check:
                if not file_id: continue
                
                # Check if still used
                usage = db.query(ComparisonJob).filter(
                    or_(ComparisonJob.acceptance_file_id == file_id, 
                        ComparisonJob.emission_file_id == file_id)
                ).count()
                
                if usage == 0:
                    file_record = db.query(File).get(file_id)
                    if file_record:
                        fpath = Path(file_record.file_path)
                        if fpath.exists():
                            freed_space += fpath.stat().st_size
                            if not dry_run:
                                os.remove(fpath)
                                db.delete(file_record)
                                # Cleanup proxies
                                proxy_dir = fpath.parent / "proxies"
                                if proxy_dir.exists():
                                    stem = fpath.stem
                                    for p in proxy_dir.iterdir():
                                        if stem in p.name:
                                            freed_space += p.stat().st_size
                                            os.remove(p)
                                print(f"  └─ 🗒️ Removed orphaned file: {fpath.name}")
                        elif not dry_run:
                            db.delete(file_record)

        if not dry_run:
            db.commit()
            print(f"✅ Cleanup complete. Deleted {deleted_count} jobs. Freed {freed_space/(1024*1024):.2f} MB.")
        else:
            print(f"📊 Dry run finished. Would free approx {freed_space/(1024*1024):.2f} MB.")
            
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanup old comparison jobs and files")
    parser.add_argument("--days", type=int, default=14, help="Delete jobs older than N days")
    parser.add_argument("--limit", type=int, default=50, help="Max jobs to delete")
    parser.add_argument("--dry-run", action="store_true", help="Don't delete, just show what would be done")
    
    args = parser.parse_args()
    cleanup(args.days, args.limit, args.dry_run)
