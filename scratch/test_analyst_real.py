import sys
from pathlib import Path
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "new_video_compare" / "backend"))

from services.analyst_service import AnalystService
from models.database import SessionLocal
from models.models import ComparisonJob, VideoComparisonResult, AudioComparisonResult
import json

db = SessionLocal()
job_id = 512

job = db.query(ComparisonJob).filter_by(id=job_id).first()
video_res = db.query(VideoComparisonResult).filter_by(job_id=job_id).first()
audio_res_db = db.query(AudioComparisonResult).filter_by(job_id=job_id).first()

if not job:
    print("❌ Job 512 not found in DB!")
    sys.exit(1)

print(f"Loaded Job {job_id} for client: {job.client_name}")

# Rebuild metrics exactly as comparison_service._run_ai_analyst does now:
computed_video_similarity = float(video_res.similarity_score) if video_res else 1.0
video_differences_count = int(video_res.different_frames) if video_res else 0

metrics = {
    "job_id": job_id,
    "job_name": job.job_name,
    "client_name": job.client_name,
    "overall_similarity": computed_video_similarity,
    "video_similarity": computed_video_similarity,
    "video_differences_count": video_differences_count,
    "is_arpp_slate": False,
    "duration_difference": 0.0,
}

if audio_res_db:
    audio_res = audio_res_db.audio_analysis_data or {}
    metrics["audio_similarity"] = float(audio_res_db.similarity_score)
    
    stt = audio_res.get("speech_to_text", {})
    
    # ── PRUNED VERSION (OUR FIX) ──
    metrics["audio_analysis_data"] = {
        "similarity": {
            "error": audio_res.get("similarity", {}).get("error", "") if isinstance(audio_res.get("similarity"), dict) else ""
        },
        "speech_to_text": {
            "comparison": {
                "word_count_a": stt.get("comparison", {}).get("word_count_a", 0) if isinstance(stt.get("comparison"), dict) else 0,
                "word_count_b": stt.get("comparison", {}).get("word_count_b", 0) if isinstance(stt.get("comparison"), dict) else 0,
            } if isinstance(stt, dict) else {}
        }
    }
    
    stt_similarity = stt.get("text_similarity")
    acceptance_text = stt.get("acceptance_text", "")
    emission_text = stt.get("emission_text", "")
    comparison_data = stt.get("comparison", {})
    word_diffs = comparison_data.get("word_differences", [])
    
    if stt_similarity is not None:
        metrics["audio_transcription"] = {
            "text_similarity": stt_similarity,
            "is_text_match": stt.get("is_text_match", True),
            "acceptance_text": acceptance_text[:300] if acceptance_text else "",
            "emission_text": emission_text[:300] if emission_text else "",
            "word_differences_count": len(word_diffs),
            "word_differences_sample": word_diffs[:5],
            "skipped": stt.get("skipped", False),
            "skipped_reason": stt.get("skipped_reason"),
        }
    else:
        metrics["audio_transcription"] = {"status": "not_run"}
    
    metrics["stt_skipped"] = stt.get("skipped", False)
    metrics["stt_skipped_reason"] = stt.get("skipped_reason")
    
    loudness = audio_res.get("loudness", {})
    loudness_comparison = loudness.get("comparison", {})
    metrics["audio_loudness"] = {
        "acceptance_lufs": loudness.get("acceptance", {}).get("integrated_lufs"),
        "emission_lufs": loudness.get("emission", {}).get("integrated_lufs"),
        "lufs_difference": loudness_comparison.get("lufs_difference"),
        "peak_difference_db": loudness_comparison.get("peak_difference_db"),
        "has_loudness_issue": loudness.get("has_loudness_differences", False)
    }

# Check payload size:
prompt_payload = json.dumps(metrics, indent=2)
print(f"Generated prompt payload size: {len(prompt_payload)} characters")
print("Preview of payload:")
print(prompt_payload)

print("\n🚀 Running live Ollama Analyst analysis...")
analyst = AnalystService()
result = analyst.analyze_job_results(metrics, db=db)

print("\n✅ ANALYSIS RESULTS FROM OLLAMA:")
print(json.dumps(result, indent=2, ensure_ascii=False))
