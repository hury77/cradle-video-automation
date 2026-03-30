import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from services.analyst_service import get_analyst

def test_ai():
    print("Testing Analyst Brain with dummy data...")
    test_metrics = {
        "job_id": 999,
        "job_name": "Test Job M4",
        "client_name": "Electrolux",
        "overall_similarity": 0.985,
        "video_similarity": 0.985,
        "video_differences_count": 12,
        "audio_similarity": 0.999,
        "audio_transcription_diff": "Odkryj nową pralkę vs Odkryj nową lodówkę",
        "audio_loudness": {
            "acceptance_lufs": -23.1,
            "emission_lufs": -21.4,
            "lufs_difference": 1.7,
            "peak_difference_db": 0.5,
            "has_loudness_issue": False
        }
    }
    
    result = get_analyst().analyze_job_results(test_metrics)
    print("\n--- AI Result ---")
    print(f"Verdict: {result.get('verdict')}")
    print(f"Reasoning: {result.get('reasoning')}")
    print(f"Confidence: {result.get('confidence')}")

if __name__ == "__main__":
    test_ai()
