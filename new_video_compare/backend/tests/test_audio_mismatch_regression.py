"""
Regression tests verifying edge cases for audio streams in DOOH materials (no streams)
vs export errors (audio stream in one file, missing in the other — audio_mismatch=True),
using ComparisonService._save_results and DeterministicDecisionEngineV1.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from services.comparison_service import ComparisonService
from services.deterministic_decision_engine import DeterministicDecisionEngineV1
from services.deterministic_metrics_adapter import adapt_comparison_metrics


@patch("services.utils.ffmpeg_utils.FFmpegUtils.__init__", return_value=None)
def test_audio_both_silent_no_penalty(mock_ffmpeg_init):
    """
    Scenario A: BOTH files lack audio streams (no_audio_tracks=True).
    overall_similarity is not penalized and DeterministicDecisionEngineV1 approves when video matches.
    """
    comp_service = ComparisonService()
    mock_db = MagicMock()
    mock_job = MagicMock()
    mock_job.id = 123

    results = {
        "video_result": {
            "overall_similarity": 0.99,
            "frames_with_differences": 0,
            "duration_difference": 0.0,
            "is_arpp_slate": False,
        },
        "audio_result": {
            "has_audio": False,
            "acc_has_audio": False,
            "emi_has_audio": False,
            "no_audio_tracks": True,
            "audio_mismatch": False,
            "is_binary_duplicate": False,
            "audio_analysis_data": {},
            "similarity_score": 1.0,
            "audio_comparison_skipped": True,
        },
    }

    comp_service._save_results(mock_db, mock_job, results)

    overall_res = None
    for call in mock_db.add.call_args_list:
        obj = call[0][0]
        if type(obj).__name__ == "ComparisonResult":
            overall_res = obj
            break

    assert overall_res is not None
    assert overall_res.overall_similarity == 0.99

    canonical = adapt_comparison_metrics(results)
    decision = DeterministicDecisionEngineV1().evaluate(canonical)
    assert decision["verdict"] == "approve"


@patch("services.utils.ffmpeg_utils.FFmpegUtils.__init__", return_value=None)
def test_audio_mismatch_penalty(mock_ffmpeg_init):
    """
    Scenario B: ONE file has audio, the other does not (audio_mismatch=True).
    overall_similarity MUST be penalized (0.0) and DeterministicDecisionEngineV1 MUST force REVIEW.
    """
    comp_service = ComparisonService()
    mock_db = MagicMock()
    mock_job = MagicMock()
    mock_job.id = 124

    results = {
        "video_result": {
            "overall_similarity": 0.99,
            "frames_with_differences": 0,
            "duration_difference": 0.0,
            "is_arpp_slate": False,
        },
        "audio_result": {
            "has_audio": False,
            "acc_has_audio": True,
            "emi_has_audio": False,
            "audio_mismatch": True,
            "no_audio_tracks": False,
            "is_binary_duplicate": False,
            "audio_analysis_data": {},
            "similarity_score": 0.0,
            "audio_comparison_skipped": True,
        },
    }

    comp_service._save_results(mock_db, mock_job, results)

    overall_res = None
    for call in mock_db.add.call_args_list:
        obj = call[0][0]
        if type(obj).__name__ == "ComparisonResult":
            overall_res = obj
            break

    assert overall_res is not None
    assert overall_res.overall_similarity == 0.0

    canonical = adapt_comparison_metrics(results)
    decision = DeterministicDecisionEngineV1().evaluate(canonical)
    assert decision["verdict"] == "review"
    assert "AUDIO_MISMATCH" in decision["reasoning"]
