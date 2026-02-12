from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, text
import os
from pathlib import Path
from typing import Dict, Any

from models.database import get_db
from models.models import ComparisonJob, File, JobStatus

router = APIRouter(tags=["Dashboard"])

def get_dir_size(path: str) -> int:
    """Calculate total size of a directory in bytes"""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_dir_size(entry.path)
    except Exception:
        pass
    return total

@router.get("/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get dashboard statistics including storage usage"""
    
    # 1. Job statistics
    total_jobs = db.query(ComparisonJob).count()
    completed_jobs = db.query(ComparisonJob).filter(ComparisonJob.status == JobStatus.COMPLETED).count()
    failed_jobs = db.query(ComparisonJob).filter(ComparisonJob.status == JobStatus.FAILED).count()
    
    # 2. File storage usage
    # We can query all files and sum their size on disk
    files = db.query(File).all()
    total_size_bytes = 0
    
    # Also count files in upload directory directly to be accurate about disk usage
    # Assuming standard upload path structure
    upload_dir = Path("new_video_compare/backend/uploads")
    if not upload_dir.exists():
        # Fallback if running from backend dir
        upload_dir = Path("uploads")
    if upload_dir.exists():
        total_size_bytes = get_dir_size(str(upload_dir))
    
    # Convert to GB
    total_size_gb = round(total_size_bytes / (1024 * 1024 * 1024), 2)
    
    return {
        "jobs": {
            "total": total_jobs,
            "completed": completed_jobs,
            "failed": failed_jobs
        },
        "storage": {
            "total_size_bytes": total_size_bytes,
            "total_size_gb": total_size_gb,
            "file_count": len(files)
        }
    }

@router.delete("/cleanup")
async def cleanup_old_jobs(count: int = 10, db: Session = Depends(get_db)):
    """Delete N oldest completed/failed jobs and their files, plus clean up orphans."""
    
    import shutil
    
    # Find N oldest jobs that are completed or failed
    jobs_to_delete = (
        db.query(ComparisonJob)
        .filter(ComparisonJob.status.in_([JobStatus.COMPLETED, JobStatus.FAILED]))
        .order_by(ComparisonJob.created_at.asc())
        .limit(count)
        .all()
    )
    
    deleted_count = 0
    freed_space_bytes = 0

    for job in jobs_to_delete:
        # 1. Identify files to potentially delete
        files_to_check = [job.acceptance_file, job.emission_file]
        
        # 2. Delete the job first (cascade deletes results)
        try:
            db.delete(job)
            db.flush()
            deleted_count += 1
        except Exception as e:
            print(f"Error deleting job {job.id}: {e}")
            continue

        # 3. Check if files are orphaned and delete them
        for file_model in files_to_check:
            if file_model:
                try:
                    # Check if file is used by ANY other job
                    usage_count = db.query(ComparisonJob).filter(
                        or_(
                            ComparisonJob.acceptance_file_id == file_model.id,
                            ComparisonJob.emission_file_id == file_model.id
                        )
                    ).count()
                    
                    if usage_count == 0:
                        # File is orphan, safe to delete
                        file_path = Path(file_model.file_path)
                        if file_path.exists():
                            size = file_path.stat().st_size
                            freed_space_bytes += size
                            os.remove(file_path)
                        
                        # Also delete proxy files for this file
                        proxy_dir = file_path.parent / "proxies"
                        if proxy_dir.exists():
                            # Proxy filenames contain the original file's stem
                            stem = file_path.stem
                            for proxy_file in proxy_dir.iterdir():
                                if stem in proxy_file.name:
                                    freed_space_bytes += proxy_file.stat().st_size
                                    proxy_file.unlink()

                        # Remove parent dir if it's empty and not "uploads"
                        if file_path.parent.name != "uploads" and file_path.parent.exists():
                            try:
                                os.rmdir(file_path.parent)
                            except:
                                pass
                                
                        db.delete(file_model)
                except Exception as e:
                    print(f"Error deleting file {file_model.id}: {e}")
    
    # 4. Clean up orphan File records (DB rows with no referencing jobs)
    all_file_ids_in_jobs = set()
    for job in db.query(ComparisonJob).all():
        if job.acceptance_file_id:
            all_file_ids_in_jobs.add(job.acceptance_file_id)
        if job.emission_file_id:
            all_file_ids_in_jobs.add(job.emission_file_id)
    
    orphan_files = db.query(File).filter(~File.id.in_(all_file_ids_in_jobs)).all() if all_file_ids_in_jobs else db.query(File).all()
    orphan_count = 0
    for orphan in orphan_files:
        try:
            file_path = Path(orphan.file_path)
            if file_path.exists():
                freed_space_bytes += file_path.stat().st_size
                os.remove(file_path)
            db.delete(orphan)
            orphan_count += 1
        except Exception as e:
            print(f"Error deleting orphan file {orphan.id}: {e}")
    
    # 5. Clean temp directory
    upload_base = Path("uploads")
    if not upload_base.exists():
        upload_base = Path("new_video_compare/backend/uploads")
    temp_dir = upload_base / "temp"
    if temp_dir.exists():
        for temp_file in temp_dir.iterdir():
            try:
                if temp_file.is_file():
                    freed_space_bytes += temp_file.stat().st_size
                    temp_file.unlink()
                elif temp_file.is_dir():
                    size = get_dir_size(str(temp_file))
                    freed_space_bytes += size
                    shutil.rmtree(temp_file)
            except Exception as e:
                print(f"Error deleting temp file {temp_file}: {e}")
    
    # 6. Clean orphan proxy files (proxies for files no longer on disk)
    proxy_dir = upload_base / "proxies"
    if proxy_dir.exists():
        # Get stems of all files still referenced by active jobs
        active_stems = set()
        for fid in all_file_ids_in_jobs:
            f = db.query(File).get(fid)
            if f:
                active_stems.add(Path(f.file_path).stem)
        
        for proxy_file in proxy_dir.iterdir():
            if proxy_file.is_file():
                # Check if any active file stem is a substring of the proxy filename
                is_active = any(stem in proxy_file.name for stem in active_stems)
                if not is_active:
                    try:
                        freed_space_bytes += proxy_file.stat().st_size
                        proxy_file.unlink()
                    except Exception as e:
                        print(f"Error deleting proxy {proxy_file}: {e}")
    
    db.commit()
    
    return {
        "message": f"Cleanup finished. Deleted {deleted_count} jobs, {orphan_count} orphan file records.",
        "deleted_jobs": deleted_count,
        "orphan_files_cleaned": orphan_count,
        "freed_space_mb": round(freed_space_bytes / (1024 * 1024), 2)
    }

