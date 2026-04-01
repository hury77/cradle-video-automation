import os
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.models import ComparisonJob, File

def get_dir_size(path):
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

def analyze_cleanup():
    db_path = "sqlite:///new_video_compare.db"
    engine = create_engine(db_path)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    jobs = db.query(ComparisonJob).order_by(ComparisonJob.id.desc()).all()
    
    keep_count = 15
    keep_jobs = jobs[:keep_count]
    delete_jobs = jobs[keep_count:]

    keep_ids = [j.id for j in keep_jobs]
    delete_ids = [j.id for j in delete_jobs]
    
    # Analyze Files belonging to delete_jobs
    delete_file_ids = set()
    for j in delete_jobs:
        if j.acceptance_file_id:
            delete_file_ids.add(j.acceptance_file_id)
        if j.emission_file_id:
            delete_file_ids.add(j.emission_file_id)
            
    # Remove files that are used by kept jobs
    for j in keep_jobs:
        if j.acceptance_file_id in delete_file_ids:
            delete_file_ids.discard(j.acceptance_file_id)
        if j.emission_file_id in delete_file_ids:
            delete_file_ids.discard(j.emission_file_id)

    files_to_delete = db.query(File).filter(File.id.in_(delete_file_ids)).all() if delete_file_ids else []
    
    space_to_free = 0
    files_count = 0
    
    for f in files_to_delete:
        p = Path(f.file_path)
        if p.exists():
            space_to_free += p.stat().st_size
            files_count += 1
            
        # check proxy
        proxy_dir = p.parent / "proxies"
        if proxy_dir.exists():
            for pf in proxy_dir.iterdir():
                if p.stem in pf.name:
                    space_to_free += pf.stat().st_size
                    files_count += 1
                    
    # Temp dir
    temp_dir = Path("uploads/temp")
    temp_space = 0
    if temp_dir.exists():
        temp_space = get_dir_size(str(temp_dir))
    
    total_space_gb = (space_to_free + temp_space) / (1024**3)
    
    print(f"Total jobs to KEEP: {len(keep_jobs)}")
    print(f"Total jobs to DELETE: {len(delete_jobs)}")
    print(f"Files to delete: {files_count}")
    print(f"Space from files: {space_to_free / (1024**3):.2f} GB")
    print(f"Space from temp folder: {temp_space / (1024**3):.2f} GB")
    print(f"TOTAL ESTIMATED FREED SPACE: {total_space_gb:.2f} GB")
    
    v = input("Do you want to proceed with deletion? (y/n): ")
    if v.lower() == 'y':
        # delete jobs
        for j in delete_jobs:
            db.delete(j)
        db.flush()
        
        # delete files from disk and db
        deleted_disk = 0
        for f in files_to_delete:
            p = Path(f.file_path)
            if p.exists():
                os.remove(p)
                deleted_disk += 1
            # proxy
            proxy_dir = p.parent / "proxies"
            if proxy_dir.exists():
                for pf in proxy_dir.iterdir():
                    if p.stem in pf.name:
                        pf.unlink()
            db.delete(f)
            
        # delete temp
        import shutil
        if temp_dir.exists():
            for x in temp_dir.iterdir():
                if x.is_file(): x.unlink()
                elif x.is_dir(): shutil.rmtree(x)
                
        db.commit()
        print(f"Cleanup complete! Deleted {len(delete_jobs)} jobs and {deleted_disk} physical videos.")
    else:
        print("Aborted.")

if __name__ == '__main__':
    analyze_cleanup()
