import pytest
import json
from services.analyst_service import AnalystService

def test_lufs_reasoning_prompt():
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
        },
        "differences": [
            {
                "timestamp_seconds": 0.0,
                "duration_seconds": 30.0,
                "difference_type": "audio_spectral",
                "severity": "medium",
                "confidence": 1.0,
                "description": "General audio mismatch"
            }
        ]
    }
    
    # We dont have an active database for this simple test, so historical_context will be empty
    system_prompt = analyst._build_system_prompt([])
    user_prompt = f"Oto wyniki automatycznej analizy:\n{json.dumps(job_data, indent=2)}\n\nNa podstawie tych danych i historii decyzji, jaki jest Twój werdykt?"
    
    # Verify if the prompt contains our rules.
    assert "2. GŁOŚNOŚĆ (LUFS):" in system_prompt, "Prompt MISSING LUFS logic section."
    assert "Różnica > 2.0 LUFS: KRYTYCZNA RÓŻNICA" in system_prompt, "Prompt MISSING strict 2.0 threshold."
    assert "audio_spectral" in user_prompt, "Prompt MISSING audio_spectral difference!"
