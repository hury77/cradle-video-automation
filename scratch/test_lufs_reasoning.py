import sys
import os
import json

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "new_video_compare/backend"))

from services.analyst_service import AnalystService

def test():
    analyst = AnalystService()
    
    # Mock data resembling Job 298
    job_data = {
        "job_id": 298,
        "client_name": "TestClient",
        "overall_result": {
            "overall_similarity": 0.98,  # Video is "good"
            "video_similarity": 0.98,
            "audio_similarity": 0.91,    # Audio content is "bad"
            "report_data": {
                "audio": {
                    "loudness": {
                        "comparison": {
                            "lufs_difference": -12.34
                        }
                    },
                    "similarity": {
                        "overall_audio_similarity": 0.91
                    }
                }
            }
        }
    }
    
    # We dont have an active database for this simple test, so historical_context will be empty
    system_prompt = analyst._build_system_prompt([])
    user_prompt = f"Oto wyniki automatycznej analizy:\n{json.dumps(job_data, indent=2)}\n\nNa podstawie tych danych i historii decyzji, jaki jest Twój werdykt?"
    
    print("--- SYSTEM PROMPT ---")
    print(system_prompt)
    print("\n--- USER PROMPT ---")
    print(user_prompt)
    
    # Note: We can't actually call Ollama in this environment without it running.
    # But we can verify if the prompt contains our new rules.
    
    if "GŁOŚNOŚĆ (LUFS — analiza różnicy bezwzględnej |diff|)" in system_prompt:
        print("\n✅ Prompt contains absolute LUFS logic.")
    else:
        print("\n❌ Prompt MISSING absolute LUFS logic.")
        
    if "Różnica > 2.0 LUFS: KRYTYCZNA RÓŻNICA" in system_prompt:
        print("✅ Prompt contains strict 2.0 threshold.")
    else:
        print("❌ Prompt MISSING strict 2.0 threshold.")

if __name__ == "__main__":
    test()
