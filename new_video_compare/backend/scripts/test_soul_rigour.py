
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from services.analyst_service import AnalystService

def test_soul_rigour():
    analyst = AnalystService()
    
    # CASE 1: The Infamous Job 235 (57% similarity)
    # Previously AI gave APPROVE. Now it MUST give REJECT or REVIEW.
    job_235_data = {
        "job_id": 235,
        "job_name": "Test Job 235 (Failure Case)",
        "client_name": "Electrolux",
        "overall_similarity": 0.573,
        "video_similarity": 0.573,
        "video_differences_count": 120,
        "audio_similarity": 0.9188,
        "audio_transcription_diff": "Some minor text differences",
        "audio_loudness": {
            "acceptance_lufs": -23.0,
            "emission_lufs": -23.03,
            "lufs_difference": 0.03,
            "has_loudness_issue": False
        }
    }
    
    print("\n🧠 Testing AI Rigour for Job 235 (57% similarity)...")
    result = analyst.analyze_job_results(job_235_data)
    
    print(f"VERDICT: {result.get('verdict').upper()}")
    print(f"CONFIDENCE: {result.get('confidence')}")
    print(f"REASONING: {result.get('reasoning')}")
    
    if result.get('verdict').lower() in ['reject', 'review']:
        print("\n✅ SUCCESS: AI correctly flagged the low similarity job.")
    else:
        print("\n❌ FAILURE: AI still approved a 57% similarity job!")

    # CASE 2: High Similarity but Loudness Issue (> 2.0 LUFS)
    job_loudness_data = {
        "job_id": 999,
        "overall_similarity": 0.995,
        "video_similarity": 0.995,
        "audio_similarity": 0.98,
        "audio_loudness": {
            "acceptance_lufs": -23.0,
            "emission_lufs": -20.5,
            "lufs_difference": 2.5,
            "has_loudness_issue": True
        }
    }
    
    print("\n🧠 Testing AI Rigour for Loudness Issue (2.5 LUFS diff)...")
    result = analyst.analyze_job_results(job_loudness_data)
    print(f"VERDICT: {result.get('verdict').upper()}")
    print(f"REASONING: {result.get('reasoning')}")

if __name__ == "__main__":
    test_soul_rigour()
