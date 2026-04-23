import sys
import os
import json

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "new_video_compare/backend"))

from services.analyst_service import AnalystService

def test():
    analyst = AnalystService()
    
    # Snapshot exactly as it would be for Job 319
    snapshot = {
        "job_id": 319,
        "client_name": "Peugeot",
        "video": {
            "similarity": 1.0,
            "different_frames": 0,
            "total_frames": 375
        },
        "audio": {
            "similarity": 1.0,
            "lufs_difference": 0.0,
            "stt_text_similarity": 1.0,
            "stt_is_match": True,
            "stt_acceptance_text": "",
            "stt_emission_text": "",
            "stt_skipped": True,
            "stt_skipped_reason": "Audio similarity 1.0000 >= 0.98. STT skipped..."
        }
    }
    
    system_prompt = analyst._build_system_prompt([])
    
    print("--- SYSTEM PROMPT (HARD RULES CHECK) ---")
    if "Jeśli stt_skipped = true" in system_prompt:
        print("✅ Found STT skip rule in Hard Rules.")
    else:
        print("❌ MISSING STT skip rule in Hard Rules.")
        
    print("\n--- ANALYZING SAMPLE DATA ---")
    # This actually calls Ollama if running. If not, it will fail, which is fine for local check of logic.
    try:
        result = analyst.analyze_job_results(snapshot)
        print(f"Verdict: {result['verdict']}")
        print(f"Reasoning: {result['reasoning']}")
        
        if "Transkrypcja została pominięta dla optymalizacji" in result['reasoning']:
            print("✅ Reasoning contains mandatory wording.")
        else:
            print("❌ Reasoning DOES NOT contain mandatory wording.")
    except Exception as e:
        print(f"Could not call LLM: {e} (Expected if Ollama is not running)")

if __name__ == "__main__":
    test()
