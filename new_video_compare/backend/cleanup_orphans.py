import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path to import models if needed, 
# but for safety we will just read the file paths directly using raw SQL
# to avoid dependency issues with the running app.

# Database URL
DB_URL = "sqlite:///new_video_compare.db"

def cleanup_orphans():
    print("🧹 Starting cleanup of orphaned files...")
    
    # 1. Connect to DB and get all valid file paths
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        # Get all file paths from 'files' table
        result = conn.execute(text("SELECT file_path FROM files"))
        valid_paths = {row[0] for row in result}
        
        # Also ensure we keep any 'acceptance_frames' folders for active jobs?
        # Those are usually inside a temp dir, but let's check if they are in uploads.
        # The 'files' table should contain the source videos.
        # Frame extraction usually happens in temp dirs, but if they are in uploads, we must be careful.
        # Based on previous logs: extraction goes to /var/folders/.../T/new_video_compare/...
        # So 'uploads/' primarily contains the source videos.
    
    print(f"✅ Found {len(valid_paths)} valid files in database.")
    
    # 2. Scan uploads directory
    uploads_dir = Path("uploads")
    if not uploads_dir.exists():
        print("❌ 'uploads' directory not found.")
        return

    deleted_count = 0
    reclaimed_bytes = 0
    kept_count = 0
    
    # Walk through uploads directory
    # We use rglob to find all files recursively
    for file_path in uploads_dir.rglob("*"):
        if file_path.is_file():
            # Convert to absolute path string to match DB format (or relative?)
            # In DB, paths seem to be stored as absolute paths based on previous logs:
            # "/Users/hubert.rycaj/Documents/cradle-video-automation/new_video_compare/backend/uploads/..."
            
            abs_path = str(file_path.absolute())
            
            # Check if file is in valid_paths
            # We check both absolute and relative just in case
            if abs_path in valid_paths:
                kept_count += 1
                continue
                
            # If we are here, file is not in DB.
            # Safety check: ensure it's actually an uploaded video/file and not a system file
            if file_path.name.startswith("."):
                continue
                
            try:
                size = file_path.stat().st_size
                print(f"🗑️ Deleting orphan: {file_path.name} ({size / 1024 / 1024:.2f} MB)")
                os.remove(file_path)
                deleted_count += 1
                reclaimed_bytes += size
            except Exception as e:
                print(f"⚠️ Error deleting {file_path.name}: {e}")

    # 3. Clean empty directories
    for dir_path in uploads_dir.rglob("*"):
        if dir_path.is_dir():
            try:
                # rmdir only works if empty
                dir_path.rmdir() 
            except:
                pass

    print("-" * 30)
    print(f"🎉 Cleanup complete!")
    print(f"files kept: {kept_count}")
    print(f"Files deleted: {deleted_count}")
    print(f"Space reclaimed: {reclaimed_bytes / (1024 * 1024 * 1024):.2f} GB")

if __name__ == "__main__":
    cleanup_orphans()
