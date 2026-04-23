import sys
import os
import json

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "new_video_compare/backend"))

from services.analyst_service import AnalystService

def test():
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
    
    print("--- SYSTEM PROMPT (HIERARCHY CHECK) ---")
    
    check_keywords = [
        "HIERARCHIA PRAWDY",
        "TWARDE REGUŁY (Truth Table powyżej) — Są nadrzędne nad WSZYSTKIM",
        "NIGDY nie może unieważnić TWARDYCH REGUŁ",
        "DECYZJE AI (Niesprawdzone sugestie — mogą zawierać błędy!)"
    ]
    
    all_found = True
    for kw in check_keywords:
        if kw in system_prompt:
            print(f"✅ Found: {kw[:50]}...")
        else:
            print(f"❌ MISSING: {kw}")
            all_found = False
            
    if all_found:
        print("\n🚀 HIERARCHY OF TRUTH PROMPT VERIFIED.")
    else:
        print("\n⚠️ PROMPT INCOMPLETE.")

if __name__ == "__main__":
    test()
