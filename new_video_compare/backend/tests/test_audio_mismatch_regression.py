"""
Testy regresyjne weryfikujące poprawność obsługi skrajnych przypadków strumieni audio 
w materiałach DOOH (brak strumieni) vs błędy eksportu (strumień audio w jednym, brak w drugim).

KONTEKST BIZNESOWY:
Materiały DOOH często nie posiadają jakichkolwiek strumieni audio w obu plikach (acceptance i emission). 
Z kolei błąd eksportu polega na tym, że jeden materiał ma włączone audio, a z drugiego zostało usunięte (mismatch).
Baza danych narzuca sztywny NOT NULL constraint na `similarity_score` w wynikach audio.

W związku z tym system przypisuje sztuczne wartości (sentinel values):
- `similarity_score = 1.0` (brak różnic, by nie obniżać overall_similarity) dla plików DOOH (no_audio_tracks=True)
- `similarity_score = 0.0` (absolutny błąd, by mocno obniżyć overall_similarity) dla błędów eksportu (audio_mismatch=True)

Ten test gwarantuje, że:
1) W przypadku DOOH, `overall_similarity` Jobu pozostaje wysokie (niekarane), a LLM nie nadpisuje werdyktu na REVIEW/REJECT.
2) W przypadku mismatchu, `overall_similarity` Jobu jest natychmiast zerowane, a AnalystService sprzętowo wymusza "REVIEW" + "SYSTEM OVERRIDE: KRYTYCZNA RÓŻNICA", ignorując neutralne oceny LLM.
"""

import pytest
from unittest.mock import MagicMock, patch
from services.comparison_service import ComparisonService
from services.analyst_service import AnalystService

# Neutralna odpowiedź Ollama (symulacja braku wiedzy LLM o mismatchu)
NEUTRAL_OLLAMA_RESPONSE = {
    "message": {
        "content": '{"verdict": "approve", "reasoning": "Idealne dopasowanie w obrazie. Transkrypcja: brak mowy / VO."}'
    }
}

@patch('services.utils.ffmpeg_utils.FFmpegUtils.__init__', return_value=None)
@patch('ollama.chat', return_value=NEUTRAL_OLLAMA_RESPONSE)
def test_audio_both_silent_no_penalty(mock_ollama_chat, mock_ffmpeg_init):
    """
    Scenariusz A: OBA pliki nie mają ścieżki dźwiękowej (no_audio_tracks=True).
    System nie może nakładać kary na overall_similarity, a analityk ma to zaraportować neutralnie (brak override'u karzącego).
    """
    comp_service = ComparisonService()
    mock_db = MagicMock()
    mock_job = MagicMock()
    mock_job.id = 123
    
    results = {
        "video_result": {
            "overall_similarity": 0.99,
            "frames_with_differences": 0
        },
        "audio_result": {
            "has_audio": False,
            "no_audio_tracks": True,
            "audio_mismatch": False,
            "audio_analysis_data": {},
            "similarity_score": 1.0,
            "audio_comparison_skipped": True
        }
    }
    
    # Wywołanie _save_results
    comp_service._save_results(mock_db, mock_job, results)
    
    overall_res = None
    for call in mock_db.add.call_args_list:
        obj = call[0][0]
        if type(obj).__name__ == "ComparisonResult":
            overall_res = obj
            break
            
    assert overall_res is not None
    assert overall_res.overall_similarity == 0.99
    
    # 2. Weryfikacja komunikatu w AnalystService (LLM mówi approve)
    analyst = AnalystService()
    metrics = {
        "overall_similarity": 0.99,
        "video_similarity": 0.99,
        "audio_similarity": 1.0,
        "no_audio_tracks": True,
        "audio_mismatch": False
    }
    
    analysis = analyst.analyze_job_results(metrics, db=None)
    
    assert analysis["verdict"] == "approve", "DOOH files should be approved if video matches"
    assert "KRYTYCZNA RÓŻNICA" not in analysis["reasoning"], "No critical override for DOOH"


@patch('services.utils.ffmpeg_utils.FFmpegUtils.__init__', return_value=None)
@patch('ollama.chat', return_value=NEUTRAL_OLLAMA_RESPONSE)
def test_audio_mismatch_penalty(mock_ollama_chat, mock_ffmpeg_init):
    """
    Scenariusz B: JEDEN plik ma ścieżkę dźwiękową, drugi nie (audio_mismatch=True).
    System MUSI nałożyć karę (overall_similarity = 0.0), a analityk wymusza "REVIEW" + "SYSTEM OVERRIDE: KRYTYCZNA RÓŻNICA".
    """
    comp_service = ComparisonService()
    mock_db = MagicMock()
    mock_job = MagicMock()
    mock_job.id = 124
    
    results = {
        "video_result": {
            "overall_similarity": 0.99,
            "frames_with_differences": 0
        },
        "audio_result": {
            "has_audio": False,
            "audio_mismatch": True,
            "no_audio_tracks": False,
            "audio_analysis_data": {},
            "similarity_score": 0.0,
            "audio_comparison_skipped": True
        }
    }
    
    # Wywołanie _save_results
    comp_service._save_results(mock_db, mock_job, results)
    
    overall_res = None
    for call in mock_db.add.call_args_list:
        obj = call[0][0]
        if type(obj).__name__ == "ComparisonResult":
            overall_res = obj
            break
            
    assert overall_res is not None
    assert overall_res.overall_similarity == 0.0, "overall_similarity MUST be penalized (0.0) for audio mismatch"
    
    # 2. Weryfikacja wymuszonego override'u w AnalystService
    analyst = AnalystService()
    metrics = {
        "overall_similarity": 0.0,
        "video_similarity": 0.99,
        "audio_similarity": 0.0,
        "audio_mismatch": True,
        "no_audio_tracks": False
    }
    
    # LLM zwraca 'approve', ale AnalystService musi nadpisać na 'review'
    analysis = analyst.analyze_job_results(metrics, db=None)
    
    assert analysis["verdict"] == "review", "Verdict MUST be forced to review for audio mismatch"
    assert "SYSTEM OVERRIDE" in analysis["reasoning"], "System override message missing"
    assert "KRYTYCZNA RÓŻNICA" in analysis["reasoning"], "Critical difference warning is missing"
