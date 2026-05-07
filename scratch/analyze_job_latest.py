import sys
from pathlib import Path
sys.path.append(str(Path("new_video_compare/backend").absolute()))
from models.database import SessionLocal
from models.models import AudioComparisonResult
import json

db = SessionLocal()
res = db.query(AudioComparisonResult).filter_by(job_id=384).first()
if res:
    print(json.dumps(res.audio_analysis_data, indent=2))
