"""
Unit tests for DeterministicDecisionEngineV1.
Pure unit tests: ZERO DB calls, ZERO Ollama calls, ZERO network dependencies.
"""

import pytest
import sys
from pathlib import Path

# Ensure services directory is in sys.path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(backend_dir / "services"))

from services.deterministic_decision_engine import (
    DeterministicDecisionEngineV1,
    get_deterministic_engine,
    CANONICAL_FAST_PATH_IDENTICAL_AUDIO,
    CANONICAL_FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH,
    CANONICAL_DUPLICATE_INPUT,
    CANONICAL_NO_AUDIO_STREAMS,
)


@pytest.fixture
def engine():
    return DeterministicDecisionEngineV1()


@pytest.fixture
def base_approved_metrics():
    """Standard baseline metrics that pass all checks for APPROVE."""
    return {
        "video_similarity": 0.9950,
        "video_differences_count": 0,
        "duration_difference": 0.0,
        "is_arpp_slate": False,
        "is_binary_duplicate": False,
        "audio_mismatch": False,
        "no_audio_tracks": False,
        "acc_has_audio": True,
        "emi_has_audio": True,
        "audio_similarity": 0.9600,
        "audio_loudness": {
            "lufs_difference": 0.40,
            "has_loudness_issue": False,
        },
        "audio_transcription": {
            "status": "completed",
            "is_text_match": True,
            "text_similarity": 1.0,
            "is_uncertain": False,
            "word_count_a": 15,
            "word_count_b": 15,
        },
    }


# ==============================================================================
# 1. REJECT TESTS
# ==============================================================================

def test_reject_video_similarity_below_threshold(engine, base_approved_metrics):
    metrics = dict(base_approved_metrics)
    metrics["video_similarity"] = 0.9490  # Strictly below 0.95
    res = engine.evaluate(metrics)

    assert res["verdict"] == "reject"
    assert res["confidence"] == 1.0
    assert res["decided_by"] == "deterministic_rules_v1"
    assert res["ai_reasoning"] == res["reasoning"]
    assert "Zgodność wideo (94.90%) jest poniżej bezwzględnego progu 95%" in res["reasoning"]


def test_reject_duration_difference_non_arpp(engine, base_approved_metrics):
    metrics = dict(base_approved_metrics)
    metrics["duration_difference"] = 1.2
    metrics["is_arpp_slate"] = False
    res = engine.evaluate(metrics)

    assert res["verdict"] == "reject"
    assert res["confidence"] == 1.0
    assert "Pliki różnią się długością o 1.20s" in res["reasoning"]


def test_reject_confirmed_vo_mismatch(engine, base_approved_metrics):
    metrics = dict(base_approved_metrics)
    metrics["audio_transcription"] = {
        "status": "completed",
        "is_text_match": False,
        "text_similarity": 0.75,
        "is_uncertain": False,
        "word_count_a": 20,
        "word_count_b": 20,
    }
    res = engine.evaluate(metrics)

    assert res["verdict"] == "reject"
    assert res["confidence"] == 1.0
    assert "Krytyczna niezgodność ścieżki lektorskiej VO" in res["reasoning"]


def test_vo_mismatch_with_uncertain_gives_review_not_reject(engine, base_approved_metrics):
    """
    Regression test: confirmed VO mismatch (< 0.90) MUST NOT trigger REJECT if
    is_uncertain is True, status is missing/failed, or metrics are incomplete.
    It MUST trigger protective REVIEW.
    """
    metrics = dict(base_approved_metrics)
    metrics["audio_transcription"] = {
        "status": "completed",
        "is_text_match": False,
        "text_similarity": 0.70,  # Below 0.90
        "is_uncertain": True,      # Uncertain flag present!
        "word_count_a": 20,
        "word_count_b": 20,
    }
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "is_uncertain=True" in res["reasoning"]


# ==============================================================================
# 2. REVIEW TESTS (STRICT TYPES, GUARDS, AUDIO, LUFS)
# ==============================================================================

def test_review_strict_type_string_false(engine, base_approved_metrics):
    """String 'false' instead of bool False must trigger INVALID_METRIC_TYPE -> REVIEW."""
    metrics = dict(base_approved_metrics)
    metrics["is_binary_duplicate"] = "false"
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "INVALID_METRIC_TYPE: is_binary_duplicate musi być typu bool" in res["reasoning"]


def test_review_strict_type_string_true(engine, base_approved_metrics):
    """String 'true' instead of bool True must trigger INVALID_METRIC_TYPE -> REVIEW."""
    metrics = dict(base_approved_metrics)
    metrics["audio_mismatch"] = "true"
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "INVALID_METRIC_TYPE: audio_mismatch musi być typu bool" in res["reasoning"]


def test_review_strict_type_is_uncertain_number(engine, base_approved_metrics):
    """Integer 1 or 0 instead of bool for is_uncertain must trigger INVALID_METRIC_TYPE."""
    metrics = dict(base_approved_metrics)
    metrics["audio_transcription"]["is_uncertain"] = 1
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "INVALID_METRIC_TYPE: is_uncertain musi być typu bool" in res["reasoning"]


def test_review_duplicate_input(engine, base_approved_metrics):
    metrics = dict(base_approved_metrics)
    metrics["is_binary_duplicate"] = True
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "DUPLICATE_INPUT" in res["reasoning"]


def test_review_audio_mismatch(engine, base_approved_metrics):
    metrics = dict(base_approved_metrics)
    metrics["audio_mismatch"] = True
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "AUDIO_MISMATCH" in res["reasoning"]


def test_review_missing_video_similarity(engine, base_approved_metrics):
    metrics = dict(base_approved_metrics)
    metrics["video_similarity"] = None
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "Brak lub niepoprawna wartość metryki podobieństwa wideo" in res["reasoning"]


def test_review_video_in_border_zone(engine, base_approved_metrics):
    metrics = dict(base_approved_metrics)
    metrics["video_similarity"] = 0.9650  # 0.95 <= x < 0.98
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "strefie granicznej" in res["reasoning"]


def test_review_lufs_diff_exceeds_threshold(engine, base_approved_metrics):
    metrics = dict(base_approved_metrics)
    metrics["audio_loudness"]["lufs_difference"] = 3.5  # > 3.0
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "|LUFS|=3.50 dB przekracza dopuszczalny próg" in res["reasoning"]


def test_review_missing_lufs_when_audio_comparable(engine, base_approved_metrics):
    metrics = dict(base_approved_metrics)
    metrics["audio_loudness"]["lufs_difference"] = None
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "Brakująca, pusta lub nienumeryczna różnica głośności LUFS" in res["reasoning"]


def test_review_stt_failed_or_error(engine, base_approved_metrics):
    metrics = dict(base_approved_metrics)
    metrics["audio_transcription"]["status"] = "error"
    metrics["audio_transcription"]["error"] = "Whisper CUDA out of memory"
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "Błąd potoku Speech-to-Text" in res["reasoning"]


def test_review_stt_is_uncertain(engine, base_approved_metrics):
    metrics = dict(base_approved_metrics)
    metrics["audio_transcription"]["is_uncertain"] = True
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "is_uncertain=True" in res["reasoning"]


def test_review_stt_minor_text_difference(engine, base_approved_metrics):
    metrics = dict(base_approved_metrics)
    metrics["audio_transcription"]["is_text_match"] = False
    metrics["audio_transcription"]["text_similarity"] = 0.94  # 0.90 <= x < 1.0
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "strefa REVIEW" in res["reasoning"]


# ==============================================================================
# 3. FAIL-CLOSED NO-SPEECH RESULT TESTS (SHARED VALIDATION)
# ==============================================================================

def test_approve_completed_no_speech_with_complete_metrics(engine, base_approved_metrics):
    """Canonical completed_no_speech with complete verified metrics leads to APPROVE."""
    metrics = dict(base_approved_metrics)
    metrics["audio_transcription"] = {
        "status": "completed_no_speech",
        "is_text_match": True,
        "is_uncertain": False,
        "word_count_a": 0,
        "word_count_b": 0,
        "acceptance_text": "",
        "emission_text": "",
    }
    metrics["raw_vad_metrics_complete"] = True
    metrics["raw_vad_error"] = None
    metrics["raw_vad_inconclusive"] = False
    metrics["raw_vad_speech"] = False
    metrics["raw_vad_status_acc"] = "no_speech"
    metrics["raw_vad_status_emi"] = "no_speech"
    metrics["raw_vad_speech_acc"] = False
    metrics["raw_vad_speech_emi"] = False
    metrics["music_dominant"] = False

    res = engine.evaluate(metrics)

    assert res["verdict"] == "approve"
    assert res["confidence"] == 1.0
    assert "potwierdzony brak mowy / VO" in res["reasoning"]


def test_review_completed_no_speech_missing_raw_vad_metrics_complete(engine, base_approved_metrics):
    """completed_no_speech missing raw_vad_metrics_complete must trigger REVIEW with UNVERIFIED_NO_SPEECH_RESULT."""
    metrics = dict(base_approved_metrics)
    metrics["audio_transcription"] = {
        "status": "completed_no_speech",
        "is_text_match": True,
        "is_uncertain": False,
        "word_count_a": 0,
        "word_count_b": 0,
        "acceptance_text": "",
        "emission_text": "",
    }
    # No raw_vad_metrics_complete provided!
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "UNVERIFIED_NO_SPEECH_RESULT" in res["reasoning"]


def test_review_completed_no_speech_missing_status_acc_or_emi(engine, base_approved_metrics):
    """completed_no_speech missing raw_vad_status_acc / emi must trigger REVIEW with UNVERIFIED_NO_SPEECH_RESULT."""
    metrics = dict(base_approved_metrics)
    metrics["audio_transcription"] = {
        "status": "completed_no_speech",
        "is_text_match": True,
        "is_uncertain": False,
        "word_count_a": 0,
        "word_count_b": 0,
        "acceptance_text": "",
        "emission_text": "",
    }
    metrics["raw_vad_metrics_complete"] = True
    metrics["raw_vad_error"] = None
    metrics["raw_vad_inconclusive"] = False
    metrics["raw_vad_speech"] = False
    metrics["raw_vad_speech_acc"] = False
    metrics["raw_vad_speech_emi"] = False
    metrics["music_dominant"] = False
    # Missing raw_vad_status_acc and raw_vad_status_emi!

    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "UNVERIFIED_NO_SPEECH_RESULT" in res["reasoning"]


def test_review_completed_legacy_zero_words_without_raw_vad_metrics(engine, base_approved_metrics):
    """completed legacy with zero words but without raw VAD metrics must fail-closed to REVIEW."""
    metrics = dict(base_approved_metrics)
    metrics["audio_transcription"] = {
        "status": "completed",
        "is_text_match": True,
        "is_uncertain": False,
        "word_count_a": 0,
        "word_count_b": 0,
        "acceptance_text": "",
        "emission_text": "",
    }
    # No raw VAD metrics provided!
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "UNVERIFIED_NO_SPEECH_RESULT" in res["reasoning"]


def test_approve_completed_legacy_zero_words_with_complete_verified_metrics(engine, base_approved_metrics):
    """completed legacy with zero words AND complete verified metrics leads to APPROVE."""
    metrics = dict(base_approved_metrics)
    metrics["audio_transcription"] = {
        "status": "completed",
        "is_text_match": True,
        "is_uncertain": False,
        "word_count_a": 0,
        "word_count_b": 0,
        "acceptance_text": "",
        "emission_text": "",
    }
    metrics["raw_vad_metrics_complete"] = True
    metrics["raw_vad_error"] = None
    metrics["raw_vad_inconclusive"] = False
    metrics["raw_vad_speech"] = False
    metrics["raw_vad_status_acc"] = "no_speech"
    metrics["raw_vad_status_emi"] = "no_speech"
    metrics["raw_vad_speech_acc"] = False
    metrics["raw_vad_speech_emi"] = False
    metrics["music_dominant"] = False

    res = engine.evaluate(metrics)

    assert res["verdict"] == "approve"
    assert res["confidence"] == 1.0
    assert "potwierdzony brak mowy / VO" in res["reasoning"]


@pytest.mark.parametrize("flaw_key", [
    "raw_vad_metrics_complete", "raw_vad_inconclusive", "raw_vad_speech",
    "raw_vad_speech_acc", "raw_vad_speech_emi", "music_dominant"
])
def test_review_vad_flag_string_false_fails_closed(engine, base_approved_metrics, flaw_key):
    """String 'false' in any VAD boolean flag fails closed to REVIEW."""
    metrics = dict(base_approved_metrics)
    metrics["audio_transcription"] = {
        "status": "completed_no_speech",
        "is_text_match": True,
        "is_uncertain": False,
        "word_count_a": 0,
        "word_count_b": 0,
        "acceptance_text": "",
        "emission_text": "",
    }
    metrics["raw_vad_metrics_complete"] = True
    metrics["raw_vad_error"] = None
    metrics["raw_vad_inconclusive"] = False
    metrics["raw_vad_speech"] = False
    metrics["raw_vad_status_acc"] = "no_speech"
    metrics["raw_vad_status_emi"] = "no_speech"
    metrics["raw_vad_speech_acc"] = False
    metrics["raw_vad_speech_emi"] = False
    metrics["music_dominant"] = False

    # Inject invalid string type 'false' or 'true'
    metrics[flaw_key] = "false"

    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "UNVERIFIED_NO_SPEECH_RESULT" in res["reasoning"]


# ==============================================================================
# 4. FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH TESTS (AUDITABLE VERIFICATION)
# ==============================================================================

def test_approve_full_mode_no_speech_with_complete_verified_metrics(engine, base_approved_metrics):
    """FULL_MODE... with complete verified raw VAD, LUFS and no speech leads to APPROVE."""
    metrics = dict(base_approved_metrics)
    metrics["audio_transcription"] = {
        "status": "skipped",
        "skipped_reason": CANONICAL_FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH,
        "is_uncertain": False,
    }
    metrics["raw_vad_metrics_complete"] = True
    metrics["raw_vad_error"] = None
    metrics["raw_vad_inconclusive"] = False
    metrics["raw_vad_speech"] = False
    metrics["raw_vad_status_acc"] = "no_speech"
    metrics["raw_vad_status_emi"] = "no_speech"
    metrics["raw_vad_speech_acc"] = False
    metrics["raw_vad_speech_emi"] = False
    metrics["music_dominant"] = False

    res = engine.evaluate(metrics)

    assert res["verdict"] == "approve"
    assert res["confidence"] == 1.0
    assert CANONICAL_FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH in res["reasoning"]


def test_review_full_mode_no_speech_missing_raw_vad_metrics(engine, base_approved_metrics):
    """FULL_MODE... missing raw VAD metrics must trigger REVIEW with UNVERIFIED_FULL_NO_SPEECH_SKIP."""
    metrics = dict(base_approved_metrics)
    metrics["audio_transcription"] = {
        "status": "skipped",
        "skipped_reason": CANONICAL_FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH,
        "is_uncertain": False,
    }
    # No raw_vad_metrics_complete provided
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "UNVERIFIED_FULL_NO_SPEECH_SKIP" in res["reasoning"]


def test_review_full_mode_no_speech_with_music_dominant(engine, base_approved_metrics):
    """FULL_MODE... with music_dominant=True must trigger REVIEW with UNVERIFIED_FULL_NO_SPEECH_SKIP."""
    metrics = dict(base_approved_metrics)
    metrics["audio_transcription"] = {
        "status": "skipped",
        "skipped_reason": CANONICAL_FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH,
        "is_uncertain": False,
    }
    metrics["raw_vad_metrics_complete"] = True
    metrics["raw_vad_error"] = None
    metrics["raw_vad_inconclusive"] = False
    metrics["raw_vad_speech"] = False
    metrics["raw_vad_status_acc"] = "no_speech"
    metrics["raw_vad_status_emi"] = "no_speech"
    metrics["raw_vad_speech_acc"] = False
    metrics["raw_vad_speech_emi"] = False
    metrics["music_dominant"] = True  # Flaw: dominant music!

    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "UNVERIFIED_FULL_NO_SPEECH_SKIP" in res["reasoning"]


def test_review_full_mode_no_speech_with_raw_vad_speech_true(engine, base_approved_metrics):
    """FULL_MODE... with raw_vad_speech=True must trigger REVIEW with UNVERIFIED_FULL_NO_SPEECH_SKIP."""
    metrics = dict(base_approved_metrics)
    metrics["audio_transcription"] = {
        "status": "skipped",
        "skipped_reason": CANONICAL_FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH,
        "is_uncertain": False,
    }
    metrics["raw_vad_metrics_complete"] = True
    metrics["raw_vad_error"] = None
    metrics["raw_vad_inconclusive"] = False
    metrics["raw_vad_speech"] = True  # Flaw: VAD detected speech!
    metrics["raw_vad_status_acc"] = "no_speech"
    metrics["raw_vad_status_emi"] = "no_speech"
    metrics["raw_vad_speech_acc"] = False
    metrics["raw_vad_speech_emi"] = False
    metrics["music_dominant"] = False

    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "UNVERIFIED_FULL_NO_SPEECH_SKIP" in res["reasoning"]


# ==============================================================================
# 5. FAST_PATH_IDENTICAL_AUDIO VERIFICATION TESTS
# ==============================================================================

def test_approve_fast_path_verified(engine, base_approved_metrics):
    metrics = dict(base_approved_metrics)
    metrics["audio_similarity"] = 0.9850  # >= 0.98
    metrics["audio_loudness"]["lufs_difference"] = 0.50
    metrics["audio_transcription"] = {
        "status": "skipped",
        "skipped_reason": CANONICAL_FAST_PATH_IDENTICAL_AUDIO,
        "is_uncertain": False,
    }
    res = engine.evaluate(metrics)

    assert res["verdict"] == "approve"
    assert res["confidence"] == 1.0
    assert CANONICAL_FAST_PATH_IDENTICAL_AUDIO in res["reasoning"]


def test_review_fast_path_audio_similarity_below_threshold(engine, base_approved_metrics):
    """FAST_PATH with audio_similarity < 0.98 must trigger REVIEW."""
    metrics = dict(base_approved_metrics)
    metrics["audio_similarity"] = 0.9700  # Below 0.98!
    metrics["audio_transcription"] = {
        "status": "skipped",
        "skipped_reason": CANONICAL_FAST_PATH_IDENTICAL_AUDIO,
        "is_uncertain": False,
    }
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "UNVERIFIED_FAST_PATH_AUDIO_SKIP" in res["reasoning"]


def test_review_fast_path_lufs_exceeds_threshold(engine, base_approved_metrics):
    """FAST_PATH with LUFS > 3.0 must trigger REVIEW."""
    metrics = dict(base_approved_metrics)
    metrics["audio_similarity"] = 0.9900
    metrics["audio_loudness"]["lufs_difference"] = 3.5  # > 3.0!
    metrics["audio_transcription"] = {
        "status": "skipped",
        "skipped_reason": CANONICAL_FAST_PATH_IDENTICAL_AUDIO,
        "is_uncertain": False,
    }
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "|LUFS|=3.50 dB przekracza" in res["reasoning"] or "UNVERIFIED_FAST_PATH_AUDIO_SKIP" in res["reasoning"]


def test_review_fast_path_with_duplicate_input(engine, base_approved_metrics):
    """FAST_PATH with is_binary_duplicate=True must trigger REVIEW."""
    metrics = dict(base_approved_metrics)
    metrics["is_binary_duplicate"] = True  # Duplicate!
    metrics["audio_similarity"] = 0.9900
    metrics["audio_transcription"] = {
        "status": "skipped",
        "skipped_reason": CANONICAL_FAST_PATH_IDENTICAL_AUDIO,
        "is_uncertain": False,
    }
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "DUPLICATE_INPUT" in res["reasoning"]


# ==============================================================================
# 6. GENERAL ALLOWLIST & SKIP REASONS
# ==============================================================================

def test_review_stt_skipped_reason_duplicate_input_never_approves(engine, base_approved_metrics):
    """DUPLICATE_INPUT is a skipped reason code that must NEVER approve."""
    metrics = dict(base_approved_metrics)
    metrics["audio_transcription"] = {
        "status": "skipped",
        "skipped_reason": CANONICAL_DUPLICATE_INPUT,
        "is_uncertain": False,
    }
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "spoza allowlisty" in res["reasoning"]


def test_review_stt_skipped_reason_no_audio_streams_not_arbitrary_skip(engine, base_approved_metrics):
    """NO_AUDIO_STREAMS as arbitrary STT skipped reason on comparable audio gives REVIEW."""
    metrics = dict(base_approved_metrics)
    metrics["audio_transcription"] = {
        "status": "skipped",
        "skipped_reason": CANONICAL_NO_AUDIO_STREAMS,
        "is_uncertain": False,
    }
    res = engine.evaluate(metrics)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "spoza allowlisty" in res["reasoning"]


def test_approve_dooh_both_silent_no_audio(engine, base_approved_metrics):
    metrics = dict(base_approved_metrics)
    metrics["no_audio_tracks"] = True
    metrics["acc_has_audio"] = False
    metrics["emi_has_audio"] = False
    metrics["audio_similarity"] = None
    metrics["audio_loudness"] = None
    metrics["audio_transcription"] = None
    res = engine.evaluate(metrics)

    assert res["verdict"] == "approve"
    assert res["confidence"] == 1.0
    assert "DOOH/plik niemy" in res["reasoning"]


# ==============================================================================
# 7. PREVALENCE & DETERMINISM TESTS
# ==============================================================================

def test_hard_reject_has_prevalence_over_review(engine, base_approved_metrics):
    """
    If file has duplicate input or STT failure (normally REVIEW),
    BUT video similarity is < 0.95 (HARD REJECT),
    the verdict MUST be REJECT.
    """
    metrics = dict(base_approved_metrics)
    metrics["video_similarity"] = 0.8200
    metrics["is_binary_duplicate"] = True
    metrics["audio_mismatch"] = True
    metrics["audio_transcription"]["status"] = "error"

    res = engine.evaluate(metrics)

    assert res["verdict"] == "reject"
    assert res["confidence"] == 1.0
    assert "Zgodność wideo (82.00%) jest poniżej bezwzględnego progu 95%" in res["reasoning"]


def test_identical_metrics_produce_identical_verdicts(engine, base_approved_metrics):
    """Determinism check: 50 runs with identical inputs must produce identical outputs."""
    results = [engine.evaluate(base_approved_metrics) for _ in range(50)]
    first_res = results[0]

    for r in results[1:]:
        assert r == first_res


# ==============================================================================
# 8. NEW CLIENT REVIEW POLICY TESTS
# ==============================================================================

def test_new_client_policy_disabled_by_default(base_approved_metrics):
    engine = DeterministicDecisionEngineV1()
    res = engine.evaluate(base_approved_metrics, client_history_count=2)

    assert res["verdict"] == "approve"
    assert res["rule_evaluation"]["checks"]["client_history"]["policy_enabled"] is False


def test_new_client_policy_enabled_triggers_review_when_below_threshold(base_approved_metrics):
    cfg = {
        "new_client_review_policy": {
            "enabled": True,
            "minimum_decisions_before_auto_approve": 10,
        }
    }
    engine = DeterministicDecisionEngineV1(config=cfg)
    res = engine.evaluate(base_approved_metrics, client_history_count=4)

    assert res["verdict"] == "review"
    assert res["confidence"] == 0.0
    assert "Nowy klient (4 historycznych decyzji" in res["reasoning"]


def test_new_client_policy_enabled_passes_when_at_or_above_threshold(base_approved_metrics):
    cfg = {
        "new_client_review_policy": {
            "enabled": True,
            "minimum_decisions_before_auto_approve": 10,
        }
    }
    engine = DeterministicDecisionEngineV1(config=cfg)
    res = engine.evaluate(base_approved_metrics, client_history_count=12)

    assert res["verdict"] == "approve"
    assert res["confidence"] == 1.0
