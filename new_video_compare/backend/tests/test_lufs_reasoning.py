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
    
    # Verify if the prompt contains our updated rules.
    assert "2. GŁOŚNOŚĆ (LUFS):" in system_prompt, "Prompt MISSING LUFS logic section."
    assert "WYJĄTEK DLA SPECYFIKACJI (LUFS OVERRIDE)" in system_prompt, "Prompt MISSING LUFS exception rule."
    assert "audio_spectral" in user_prompt, "Prompt MISSING audio_spectral difference!"

def test_audio_similarity_threshold_green_flags_no_override():
    analyst = AnalystService()
    job_data = {
        "job_id": 992,
        "overall_similarity": 1.0,
        "video_similarity": 1.0,
        "audio_similarity": 0.88,
        "audio_loudness": {"has_loudness_issue": False},
        "audio_transcription": {"is_text_match": True, "skipped": False}
    }
    dummy_llm_response = '{"verdict": "approve", "reasoning": "OK", "confidence": 0.95}'
    analyst._last_metrics = job_data
    result = analyst._parse_response(dummy_llm_response)
    
    assert result["verdict"] == "approve", "False positive! Should not override green flags if audio_sim >= 0.75"

def test_audio_similarity_threshold_green_flags_drastic_drop():
    analyst = AnalystService()
    job_data = {
        "overall_similarity": 1.0,
        "video_similarity": 1.0,
        "audio_similarity": 0.70,  # Below 0.75
        "audio_loudness": {"has_loudness_issue": False},
        "audio_transcription": {"is_text_match": True, "skipped": False}
    }
    dummy_llm_response = '{"verdict": "approve", "reasoning": "OK", "confidence": 0.95}'
    analyst._last_metrics = job_data
    result = analyst._parse_response(dummy_llm_response)
    
    assert result["verdict"] == "review", "Should force REVIEW when audio_sim < 0.75 even with green flags"
    assert "Zgodność audio" in result["reasoning"]

def test_audio_similarity_threshold_no_green_flags():
    analyst = AnalystService()
    job_data = {
        "overall_similarity": 1.0,
        "video_similarity": 1.0,
        "audio_similarity": 0.85,  # Below 0.90
        "audio_loudness": {"has_loudness_issue": True},  # Red flag
        "audio_transcription": {"is_text_match": True, "skipped": False}
    }
    dummy_llm_response = '{"verdict": "approve", "reasoning": "OK", "confidence": 0.95}'
    analyst._last_metrics = job_data
    result = analyst._parse_response(dummy_llm_response)
    
    assert result["verdict"] == "review", "Should force REVIEW when audio_sim < 0.90 without green flags"
    assert "Zgodność audio" in result["reasoning"]
