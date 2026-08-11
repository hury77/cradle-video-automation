import pytest
import json
from services.analyst_service import AnalystService

def test_stt_skip_reasoning():
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
    
    expected_rule = "'Transkrypcja została pominięta dla optymalizacji z powodu braku różnic w warstwie audio.'"
    assert expected_rule in system_prompt, f"Missing rule in system prompt: {expected_rule}"
    assert '"stt_skipped": true' in user_prompt, "Missing stt_skipped flag in user data."
