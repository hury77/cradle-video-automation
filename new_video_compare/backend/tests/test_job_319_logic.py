import pytest
import requests
import json
from services.analyst_service import AnalystService

@pytest.mark.integration
def test_job_319_logic():
    # Graceful skip if Ollama is unavailable
    try:
        requests.get("http://localhost:11434/", timeout=2)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        pytest.skip("Ollama is not running at localhost:11434. Skipping integration test.")

    analyst = AnalystService()
    
    # Snapshot exactly as it would be for Job 319
    snapshot = {
        "job_id": 319,
        "client_name": "Peugeot",
        "stt_skipped": True,
        "stt_skipped_reason": "Audio similarity 1.0000 >= 0.98. STT skipped...",
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
            "stt_emission_text": ""
        }
    }
    
    # Call the AnalystService (LLM Integration)
    result = analyst.analyze_job_results(snapshot)
    
    # Hard assertions (no flaky risk)
    assert isinstance(result, dict), "Result should be a parsed JSON dictionary"
    assert "verdict" in result, "Result dictionary should contain a 'verdict' key"
    assert "reasoning" in result, "Result dictionary should contain a 'reasoning' key"
    assert result["verdict"] == "approve", f"Expected verdict to be 'approve', but got '{result['verdict']}'"
    
    # Soft check (content verification based on strict system prompt instructions)
    assert "Transkrypcja została pominięta" in result["reasoning"], (
        f"Missing mandatory STT skip reasoning in LLM output. Got: {result['reasoning']}"
    )
