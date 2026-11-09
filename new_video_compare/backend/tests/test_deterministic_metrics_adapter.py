"""
Unit tests for deterministic metrics adapter.
Validates transformation of realistic raw results and metrics_snapshot dicts
into the canonical contract for DeterministicDecisionEngineV1.
ZERO external dependencies, ZERO database, ZERO Ollama, ZERO network calls.
"""

import pytest
from services.deterministic_metrics_adapter import adapt_comparison_metrics
from services.deterministic_decision_engine import DeterministicDecisionEngineV1


@pytest.fixture
def engine():
    return DeterministicDecisionEngineV1()


# 1. Realistic full audio + STT match (from actual comparison_service pipeline)
def test_adapter_full_audio_stt_match_produces_approve(engine):
    raw_results = {
        "job_id": 101,
        "job_name": "commercial_spot.mp4",
        "client_name": "Acme Corp",
        "overall_similarity": 0.99,
        "video_result": {
            "overall_similarity": 0.99,
            "duration_difference": 0.0,
            "is_arpp_slate": False,
            "frames_with_differences": 0,
        },
        "audio_result": {
            "has_audio": True,
            "has_audio_any": True,
            "audio_pair_comparable": True,
            "no_audio_tracks": False,
            "audio_mismatch": False,
            "is_binary_duplicate": False,
            "acc_has_audio": True,
            "emi_has_audio": True,
            "similarity_score": 0.985,
            "loudness": {
                "has_loudness_differences": False,
                "comparison": {"lufs_difference": 0.4},
            },
            "speech_to_text": {
                "status": "completed",
                "text_similarity": 1.0,
                "is_text_match": True,
                "acceptance_text": "Kup teraz wspaniały produkt",
                "emission_text": "Kup teraz wspaniały produkt",
                "is_uncertain": False,
                "word_count_a": 4,
                "word_count_b": 4,
            },
            "raw_vad_metrics_complete": True,
            "raw_vad_inconclusive": False,
            "raw_vad_speech": True,
            "raw_vad_error": None,
            "raw_vad_status_acc": "speech_detected",
            "raw_vad_status_emi": "speech_detected",
            "raw_vad_speech_acc": True,
            "raw_vad_speech_emi": True,
            "music_proportion": 0.10,
        },
    }

    canonical = adapt_comparison_metrics(raw_results)
    assert canonical["video_similarity"] == 0.99
    assert canonical["duration_difference"] == 0.0
    assert canonical["is_binary_duplicate"] is False
    assert canonical["audio_mismatch"] is False
    assert canonical["no_audio_tracks"] is False
    assert canonical["acc_has_audio"] is True
    assert canonical["emi_has_audio"] is True
    assert canonical["audio_transcription"]["status"] == "completed"
    assert canonical["audio_transcription"]["is_text_match"] is True

    decision = engine.evaluate(canonical)
    assert decision["verdict"] == "approve"
    assert decision["confidence"] == 1.0


# 2. DOOH / No audio tracks on both sides
def test_adapter_dooh_both_silent_produces_approve(engine):
    raw_results = {
        "job_id": 102,
        "job_name": "dooh_banner.mp4",
        "client_name": "DOOH Media",
        "video_result": {
            "overall_similarity": 0.995,
            "duration_difference": 0.0,
            "is_arpp_slate": False,
        },
        "audio_result": {
            "has_audio": False,
            "has_audio_any": False,
            "audio_pair_comparable": False,
            "no_audio_tracks": True,
            "audio_mismatch": False,
            "is_binary_duplicate": False,
            "acc_has_audio": False,
            "emi_has_audio": False,
            "similarity_score": 1.0,
            "audio_comparison_skipped": True,
            "skip_reason": "NO_AUDIO_STREAMS: No audio tracks present in both source files",
        },
    }

    canonical = adapt_comparison_metrics(raw_results)
    assert canonical["no_audio_tracks"] is True
    assert canonical["acc_has_audio"] is False
    assert canonical["emi_has_audio"] is False
    assert canonical["audio_mismatch"] is False

    decision = engine.evaluate(canonical)
    assert decision["verdict"] == "approve"
    assert decision["confidence"] == 1.0


# 3. AUDIO_MISMATCH: One file has audio, the other none
def test_adapter_audio_mismatch_produces_review(engine):
    raw_results = {
        "job_id": 103,
        "video_result": {
            "overall_similarity": 0.99,
            "duration_difference": 0.0,
            "is_arpp_slate": False,
        },
        "audio_result": {
            "has_audio": False,
            "has_audio_any": True,
            "audio_pair_comparable": False,
            "no_audio_tracks": False,
            "audio_mismatch": True,
            "is_binary_duplicate": False,
            "acc_has_audio": True,
            "emi_has_audio": False,
            "similarity_score": 0.0,
            "skip_reason": "AUDIO_MISMATCH: One file contains audio, but the other has no audio streams.",
        },
    }

    canonical = adapt_comparison_metrics(raw_results)
    assert canonical["audio_mismatch"] is True
    assert canonical["acc_has_audio"] is True
    assert canonical["emi_has_audio"] is False

    decision = engine.evaluate(canonical)
    assert decision["verdict"] == "review"
    assert decision["confidence"] == 0.0
    assert any("AUDIO_MISMATCH" in r for r in decision["rule_evaluation"]["reasons"])


# 4. DUPLICATE_INPUT: Identical binary files
def test_adapter_duplicate_input_produces_review(engine):
    raw_results = {
        "job_id": 104,
        "video_result": {
            "overall_similarity": 1.0,
            "duration_difference": 0.0,
            "is_arpp_slate": False,
        },
        "audio_result": {
            "has_audio": True,
            "has_audio_any": True,
            "audio_pair_comparable": True,
            "no_audio_tracks": False,
            "audio_mismatch": False,
            "is_binary_duplicate": True,
            "acc_has_audio": True,
            "emi_has_audio": True,
            "similarity_score": 1.0,
            "speech_to_text": {
                "status": "skipped",
                "skipped_reason": "DUPLICATE_INPUT: Identical binary files",
                "is_uncertain": True,
                "uncertainty_reason": "DUPLICATE_INPUT",
            },
        },
    }

    canonical = adapt_comparison_metrics(raw_results)
    assert canonical["is_binary_duplicate"] is True

    decision = engine.evaluate(canonical)
    assert decision["verdict"] == "review"
    assert decision["confidence"] == 0.0
    assert any("DUPLICATE_INPUT" in r for r in decision["rule_evaluation"]["reasons"])


# 5. completed_no_speech with complete VAD metrics
def test_adapter_completed_no_speech_verified_produces_approve(engine):
    raw_results = {
        "job_id": 105,
        "video_result": {
            "overall_similarity": 0.99,
            "duration_difference": 0.0,
            "is_arpp_slate": False,
        },
        "audio_result": {
            "has_audio": True,
            "has_audio_any": True,
            "audio_pair_comparable": True,
            "no_audio_tracks": False,
            "audio_mismatch": False,
            "is_binary_duplicate": False,
            "acc_has_audio": True,
            "emi_has_audio": True,
            "similarity_score": 0.99,
            "loudness": {
                "has_loudness_differences": False,
                "comparison": {"lufs_difference": 0.2},
            },
            "speech_to_text": {
                "status": "completed_no_speech",
                "text_similarity": 1.0,
                "is_text_match": True,
                "acceptance_text": "",
                "emission_text": "",
                "is_uncertain": False,
                "word_count_a": 0,
                "word_count_b": 0,
            },
            "raw_vad_metrics_complete": True,
            "raw_vad_inconclusive": False,
            "raw_vad_speech": False,
            "raw_vad_error": None,
            "raw_vad_status_acc": "no_speech",
            "raw_vad_status_emi": "no_speech",
            "raw_vad_speech_acc": False,
            "raw_vad_speech_emi": False,
            "music_proportion": 0.15,
        },
    }

    canonical = adapt_comparison_metrics(raw_results)
    assert canonical["raw_vad_metrics_complete"] is True
    assert canonical["raw_vad_speech"] is False
    assert canonical["music_dominant"] is False

    decision = engine.evaluate(canonical)
    assert decision["verdict"] == "approve"
    assert decision["confidence"] == 1.0


# 6. FAILED / uncertain STT
def test_adapter_failed_stt_produces_review(engine):
    raw_results = {
        "job_id": 106,
        "video_result": {
            "overall_similarity": 0.99,
            "duration_difference": 0.0,
            "is_arpp_slate": False,
        },
        "audio_result": {
            "has_audio": True,
            "has_audio_any": True,
            "audio_pair_comparable": True,
            "no_audio_tracks": False,
            "audio_mismatch": False,
            "is_binary_duplicate": False,
            "acc_has_audio": True,
            "emi_has_audio": True,
            "similarity_score": 0.99,
            "speech_to_text": {
                "status": "failed",
                "error_message": "Whisper failed to run on MPS",
                "is_uncertain": True,
                "uncertainty_reason": "GPU OOM",
            },
        },
    }

    canonical = adapt_comparison_metrics(raw_results)
    assert canonical["audio_transcription"]["status"] == "failed"
    assert canonical["audio_transcription"]["is_uncertain"] is True

    decision = engine.evaluate(canonical)
    assert decision["verdict"] == "review"
    assert decision["confidence"] == 0.0
    assert any("Speech-to-Text ('failed')" in r or "STT" in r for r in decision["rule_evaluation"]["reasons"])


# 7. Missing or non-numeric data fails closed to review
def test_adapter_missing_data_fails_closed(engine):
    # Completely empty dictionary
    canonical = adapt_comparison_metrics({})
    decision = engine.evaluate(canonical)
    assert decision["verdict"] == "review"

    # Non-dictionary input
    canonical_non_dict = adapt_comparison_metrics("not_a_dict")
    decision_non_dict = engine.evaluate(canonical_non_dict)
    assert decision_non_dict["verdict"] == "review"

    # Non-numeric video_similarity
    corrupted_data = {
        "video_result": {
            "overall_similarity": "corrupted_string",
            "duration_difference": None,
        },
        "audio_result": {
            "is_binary_duplicate": False,
            "audio_mismatch": False,
            "no_audio_tracks": False,
            "acc_has_audio": True,
            "emi_has_audio": True,
        },
    }
    canonical_corrupted = adapt_comparison_metrics(corrupted_data)
    assert canonical_corrupted["video_similarity"] is None
    decision_corrupted = engine.evaluate(canonical_corrupted)
    assert decision_corrupted["verdict"] == "review"
    assert any("video_similarity" in r for r in decision_corrupted["rule_evaluation"]["reasons"])


# 8. Adapter correctly transforms metrics_snapshot (the output of ComparisonService._build_ai_metrics)
def test_adapter_metrics_snapshot_transformation(engine):
    metrics_snapshot = {
        "job_id": 999,
        "job_name": "snapshot_test.mov",
        "client_name": "TestClient",
        "overall_similarity": 0.995,
        "video_similarity": 0.995,
        "video_differences_count": 0,
        "is_arpp_slate": False,
        "duration_difference": 0.0,
        "audio_similarity": 0.998,
        "audio_mismatch": False,
        "no_audio_tracks": False,
        "is_binary_duplicate": False,
        "acc_has_audio": True,
        "emi_has_audio": True,
        "audio_loudness": {
            "lufs_difference": 0.1,
            "acceptance_lufs": -24.0,
            "emission_lufs": -24.1,
            "has_loudness_issue": False,
        },
        "audio_transcription": {
            "status": "completed",
            "text_similarity": 1.0,
            "is_text_match": True,
            "acceptance_text": "Hello world",
            "emission_text": "Hello world",
            "is_uncertain": False,
            "word_differences_count": 0,
        },
        "audio_analysis_data": {
            "speech_to_text": {
                "comparison": {
                    "word_count_a": 2,
                    "word_count_b": 2,
                }
            }
        },
    }

    canonical = adapt_comparison_metrics(metrics_snapshot)
    assert canonical["video_similarity"] == 0.995
    assert canonical["audio_transcription"]["word_count_a"] == 2
    assert canonical["audio_transcription"]["word_count_b"] == 2
    assert canonical["audio_loudness"]["lufs_difference"] == 0.1

    decision = engine.evaluate(canonical)
    assert decision["verdict"] == "approve"


# 9. Contract test: canonical output of adapter gives the exact same verdict as direct canonical fixture
def test_adapter_output_matches_direct_canonical_fixture(engine):
    direct_canonical = {
        "video_similarity": 0.99,
        "duration_difference": 0.0,
        "is_arpp_slate": False,
        "is_binary_duplicate": False,
        "audio_mismatch": False,
        "no_audio_tracks": False,
        "acc_has_audio": True,
        "emi_has_audio": True,
        "audio_similarity": 0.98,
        "audio_loudness": {"lufs_difference": 0.3},
        "audio_transcription": {
            "status": "completed",
            "is_uncertain": False,
            "is_text_match": True,
            "text_similarity": 1.0,
            "word_count_a": 5,
            "word_count_b": 5,
        },
    }

    # Equivalent raw results representation
    raw_results = {
        "video_result": {
            "overall_similarity": 0.99,
            "duration_difference": 0.0,
            "is_arpp_slate": False,
        },
        "audio_result": {
            "is_binary_duplicate": False,
            "audio_mismatch": False,
            "no_audio_tracks": False,
            "acc_has_audio": True,
            "emi_has_audio": True,
            "similarity_score": 0.98,
            "loudness": {"lufs_difference": 0.3},
            "speech_to_text": {
                "status": "completed",
                "is_uncertain": False,
                "is_text_match": True,
                "text_similarity": 1.0,
                "word_count_a": 5,
                "word_count_b": 5,
            },
        },
    }

    adapted_canonical = adapt_comparison_metrics(raw_results)

    direct_decision = engine.evaluate(direct_canonical)
    adapted_decision = engine.evaluate(adapted_canonical)

    assert adapted_decision["verdict"] == direct_decision["verdict"]
    assert adapted_decision["confidence"] == direct_decision["confidence"]
    assert (
        adapted_decision["rule_evaluation"]["fired_rule"]
        == direct_decision["rule_evaluation"]["fired_rule"]
    )
