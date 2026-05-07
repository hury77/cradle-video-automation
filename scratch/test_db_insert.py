import sys
from pathlib import Path
sys.path.append(str(Path("new_video_compare/backend").absolute()))

from models.database import SessionLocal
from models.models import File, FileType, FileFormat

db = SessionLocal()
try:
    file_record = File(
        filename="test1.mp4",
        original_name="test1.mp4",
        file_path="/tmp/test1.mp4",
        file_type=FileType.ACCEPTANCE,
        file_format=FileFormat.MP4,
        file_size=123,
    )
    db.add(file_record)
    db.commit()
    print("Success")
except Exception as e:
    print("Error:", repr(e))
    db.rollback()
