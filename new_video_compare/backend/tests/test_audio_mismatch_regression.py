"""
Testy regresyjne weryfikujące poprawność obsługi skrajnych przypadków strumieni audio 
w materiałach DOOH (brak strumieni) vs błędy eksportu (strumień audio w jednym, brak w drugim).

KONTEKST BIZNESOWY:
System nowej generacji automatycznie odrzuca i raportuje błędy przy różnicach materiałów.
Materiały DOOH często nie posiadają jakichkolwiek strumieni audio w obu plikach (acceptance i emission). 
Z kolei błąd eksportu polega na tym, że jeden materiał ma włączone audio, a z drugiego zostało usunięte (mismatch).
Baza danych narzuca sztywny NOT NULL constraint na `similarity_score` w wynikach audio.
W związku z tym system przypisuje sztuczne wartości (sentinel values):
- `similarity_score = 1.0` (brak różnic, by nie obniżać overall_similarity) dla plików DOOH (no_audio_tracks=True)
- `similarity_score = 0.0` (absolutny błąd, by mocno obniżyć overall_similarity) dla błędów eksportu (audio_mismatch=True)

Ten test gwarantuje, że:
1) W przypadku DOOH, `overall_similarity` Jobu pozostaje wysokie (niekarane), a LLM generuje łagodny komunikat ("plik niemy").
2) W przypadku mismatchu, `overall_similarity` Jobu jest natychmiast zerowane, a LLM zgłasza "KRYTYCZNA RÓŻNICA".
Odróżnienie obu tych stanów na poziomie `overall_similarity` oraz raportu dla ludzkiego QA jest kluczowe, 
aby pliki DOOH mogły bezbłędnie przechodzić (APPROVE), a uszkodzone materiały z brakującym audio były zatrzymywane (REJECT/REVIEW).
"""

import pytest
from unittest.mock import MagicMock, patch
from services.comparison_service import ComparisonService
from services.analyst_service import AnalystService

@patch('services.utils.ffmpeg_utils.FFmpegUtils.__init__', return_value=None)
def test_audio_both_silent_no_penalty(mock_ffmpeg_init):
    """
    Scenariusz A: OBA pliki nie mają ścieżki dźwiękowej (no_audio_tracks=True).
    System nie może nakładać kary na overall_similarity, a analityk ma to zaraportować neutralnie.
    """
    # 1. Weryfikacja overall_similarity w _save_results
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
            "similarity_score": 1.0,
            "audio_comparison_skipped": True
        }
    }
    
    # Wywołanie _save_results (wstawia wyniki do mock_db)
    comp_service._save_results(mock_db, mock_job, results)
    
    # Znajdź wywołanie dodające ComparisonResult do bazy
    overall_res = None
    for call in mock_db.add.call_args_list:
        obj = call[0][0]
        # Sprawdzamy typ po nazwie klasy, żeby nie importować modelu jeśli nie trzeba
        if type(obj).__name__ == "ComparisonResult":
            overall_res = obj
            break
            
    assert overall_res is not None, "ComparisonResult was not added to the database"
    assert overall_res.overall_similarity == 0.99, "overall_similarity should NOT be penalized for fully silent files"
    
    # 2. Weryfikacja komunikatu w AnalystService
    analyst = AnalystService()
    metrics = {
        "overall_similarity": 0.99,
        "video_similarity": 0.99,
        "audio_similarity": 1.0,
        "audio_analysis_data": results["audio_result"]
    }
    reasoning = analyst._generate_rule_based_reasoning("APPROVE", metrics)
    
    assert "brak ścieżki dźwiękowej w materiałach (plik niemy / GIF)" in reasoning, "Neutral message about silent file is missing"
    assert "KRYTYCZNA" not in reasoning, "KRYTYCZNA word should not be used for fully silent files"
    assert "mismatch" not in reasoning.lower(), "Mismatch word should not be used for fully silent files"

@patch('services.utils.ffmpeg_utils.FFmpegUtils.__init__', return_value=None)
def test_audio_mismatch_penalty(mock_ffmpeg_init):
    """
    Scenariusz B: JEDEN plik ma ścieżkę dźwiękową, drugi nie (audio_mismatch=True).
    System MUSI nałożyć karę (overall_similarity = 0.0), a analityk zgłasza "KRYTYCZNA RÓŻNICA".
    """
    # 1. Weryfikacja overall_similarity w _save_results
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
            "similarity_score": 0.0,
            "audio_comparison_skipped": True
        }
    }
    
    # Wywołanie _save_results (wstawia wyniki do mock_db)
    comp_service._save_results(mock_db, mock_job, results)
    
    # Znajdź wywołanie dodające ComparisonResult do bazy
    overall_res = None
    for call in mock_db.add.call_args_list:
        obj = call[0][0]
        if type(obj).__name__ == "ComparisonResult":
            overall_res = obj
            break
            
    assert overall_res is not None, "ComparisonResult was not added to the database"
    assert overall_res.overall_similarity == 0.0, "overall_similarity MUST be penalized (0.0) for audio mismatch"
    
    # 2. Weryfikacja komunikatu w AnalystService
    analyst = AnalystService()
    metrics = {
        "overall_similarity": 0.0,
        "video_similarity": 0.99,
        "audio_similarity": 0.0,
        "audio_analysis_data": results["audio_result"]
    }
    reasoning = analyst._generate_rule_based_reasoning("REJECT", metrics)
    
    assert "KRYTYCZNA RÓŻNICA" in reasoning, "Critical difference warning is missing"
    assert "brak ścieżki dźwiękowej w jednym z plików (mismatch)" in reasoning, "Mismatch description is missing"
    assert "plik niemy / GIF" not in reasoning, "Neutral DOOH message should not be used for mismatch"
