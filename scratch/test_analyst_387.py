import sys
from pathlib import Path
sys.path.append(str(Path("new_video_compare/backend").absolute()))

from services.analyst_service import AnalystService
from models.database import SessionLocal
from models.models import ComparisonResult, AudioComparisonResult
import json

db = SessionLocal()
res = db.query(ComparisonResult).filter_by(job_id=387).first()
audio_res = db.query(AudioComparisonResult).filter_by(job_id=387).first()

analyst = AnalystService()

metrics = res.report_data if res.report_data else {}
metrics["audio_similarity"] = res.audio_similarity
metrics["audio_analysis_data"] = audio_res.audio_analysis_data if audio_res else {}

analyst._last_metrics = metrics

# Mock LLM reasoning simulating what the user posted:
sample_response = '{"verdict": "approve", "reasoning": "Obraz: zgodny (similarity=1.0000, 0 różnych klatek). Audio: akceptowalne (audio_similarity=0.9417). Głośność: OK (|LUFS diff|=0.03). Transkrypcja: zgodna (text_similarity=1.0000)."}'

result = analyst._parse_response(sample_response)
print("VERDICT:", result['verdict'])
print("REASONING:", result['reasoning'])

