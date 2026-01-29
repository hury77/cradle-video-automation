from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
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
    """Delete N oldest completed/failed jobs and their files"""
    
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
        
        # 2. Delete the job first (this removes dependencies on files)
        # Note: SQLAlchemy handles cascading delete for results due to cascade="all, delete-orphan" in model
        try:
            db.delete(job)
            db.flush() # Ensure job deletion is registered in session for subsequent queries
            deleted_count += 1
        except Exception as e:
            print(f"Error deleting job {job.id}: {e}")
            continue # Skip file deletion if job deletion failed

        # 3. Check if files are orphaned and delete them
        for file_model in files_to_check:
            if file_model:
                try:
                    # Check if file is used by ANY other job
                    # (The current job is already marked for deletion in this session)
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
                            
                        # Also try to remove parent directory if it was created for this file (uuid based)
                        if file_path.parent.name != "uploads" and file_path.parent.exists():
                            try:
                                os.rmdir(file_path.parent) # Only removes if empty
                            except:
                                pass
                                
                        db.delete(file_model)
                except Exception as e:
                    print(f"Error deleting file {file_model.id}: {e}")
    
    db.commit()
    

    
    return {
        "message": f"Cleanup finished. Deleted {deleted_count} jobs.",
        "deleted_jobs": deleted_count,
        "freed_space_mb": round(freed_space_bytes / (1024 * 1024), 2)
    }
