import sys
import os
import json

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "new_video_compare/backend"))

from services.analyst_service import AnalystService

def test():
    analyst = AnalystService()
    
    # Mock data resembling Job 317 (skipped STT)
    job_data = {
        "job_id": 317,
        "client_name": "Peugeot",
        "audio": {
            "similarity": 1.0,
            "stt_skipped": True,
            "stt_skipped_reason": "Audio similarity 1.0000 >= 0.98. STT skipped...",
            "stt_text_similarity": 1.0,
            "stt_acceptance_text": "",
            "stt_emission_text": ""
        }
    }
    
    system_prompt = analyst._build_system_prompt([])
    user_prompt = f"Oto wyniki automatycznej analizy:\n{json.dumps(job_data, indent=2)}\n\nNa podstawie tych danych i historii decyzji, jaki jest Twój werdykt?"
    
    print("--- SYSTEM PROMPT CHECK ---")
    expected_rule = "'Transkrypcja została pominięta dla optymalizacji z powodu braku różnic w warstwie audio.'"
    if expected_rule in system_prompt:
        print(f"✅ Found rule: {expected_rule}")
    else:
        print(f"❌ MISSING rule: {expected_rule}")
        
    print("\n--- USER PROMPT SAMPLE ---")
    print(user_prompt[:300] + "...")
    
    if '"stt_skipped": true' in user_prompt:
        print("✅ Found stt_skipped flag in user data.")
    else:
        print("❌ MISSING stt_skipped flag in user data.")

if __name__ == "__main__":
    test()
