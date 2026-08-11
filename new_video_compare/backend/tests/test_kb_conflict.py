import pytest
from services.analyst_service import AnalystService

def test_kb_conflict_hierarchy():
    analyst = AnalystService()
    
    # Mock historical context with "bad" AI decisions (Spoticar test cases)
    historical_context = [
        {
            "verdict": "approve",
            "decided_by": "agent",
            "overall_similarity": 1.0,
            "lufs_difference": -12.34,
            "text_similarity": 1.0,
            "human_comment": None,
            "override_reason": None,
            "ai_was_wrong": False
        }
    ]
    
    system_prompt = analyst._build_system_prompt(historical_context)
    
    check_keywords = [
        "HIERARCHIA PRAWDY",
        "TWARDE REGUŁY (Truth Table powyżej) — nadrzędne nad WSZYSTKIM",
        "DECYZJE AI — tylko sugestie"
    ]
    
    for kw in check_keywords:
        assert kw in system_prompt, f"Missing keyword in system prompt: {kw}"
