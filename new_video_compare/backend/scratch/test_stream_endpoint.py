import os
import sys

# Force absolute database URL to prevent relative path resolution in scratch folder
os.environ["DATABASE_URL"] = "sqlite:////Users/hubert.rycaj/Documents/cradle-video-automation/new_video_compare/backend/new_video_compare.db"

sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

from models.database import SessionLocal
from models.models import File as FileModel

db = SessionLocal()
file_record = db.query(FileModel).filter(FileModel.id == 868).first()

print("--- DIRECT DATABASE INQUIRY ---")
if file_record:
    print(f"ID 868 found!")
    print(f"  Filename: {file_record.filename}")
    print(f"  Processed: {file_record.is_processed}")
    print(f"  Codec: {file_record.codec}")
    print(f"  Metadata: {file_record.file_metadata}")
else:
    print("ID 868 NOT found in direct inquiry!")

# Let's list the top 3 IDs
latest_records = db.query(FileModel).order_by(FileModel.id.desc()).limit(3).all()
print("\n--- LATEST 3 DB RECORDS ---")
for r in latest_records:
    print(f"ID {r.id} | {r.filename} | Processed: {r.is_processed}")
db.close()
