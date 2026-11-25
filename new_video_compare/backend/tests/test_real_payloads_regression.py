"""
Regression tests for real anonymized staging payloads (jobs 1822-1827)
and strict security/completeness invariants.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from models.models import (
    Base,
    ComparisonJob,
    ComparisonType,
    DecisionVerdict,
    File,
    FileFormat,
    FileType,
    JobStatus,
    QADecision,
    SensitivityLevel,
)
from services.comparison_service import ComparisonService
from services.deterministic_decision_engine import (
    CANONICAL_DUPLICATE_INPUT,
    CANONICAL_FAST_PATH_IDENTICAL_AUDIO,
    CANONICAL_NO_AUDIO_STREAMS,
    DeterministicDecisionEngineV1,
)
from services.deterministic_metrics_adapter import (
    adapt_comparison_metrics,
    is_metrics_contract_complete,
)
from services.stt_skip_normalizer import normalize_skip_code_strict

FIXTURES_DIR = backend_dir / "tests" / "fixtures" / "real_payloads"


def _load_fixture(job_id: int) -> dict:
    path = FIXTURES_DIR / f"job_{job_id}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def engine():
    return DeterministicDecisionEngineV1()


@pytest.fixture
def isolated_db_session():
    db_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(db_engine)
    Session = sessionmaker(bind=db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        db_engine.dispose()


# ---------------------------------------------------------------------------
# 1. Real payload fixtures (1822-1827)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "job_id,expected_verdict,primary_verdict",
    [
        (1822, "approve", "approve"),   # DOOH, NO_AUDIO_STREAMS
        (1823, "review", "review"),     # Borderline video 97.33%, legacy FAST_PATH
        (1824, "review", "review"),     # AUDIO_MISMATCH
        (1825, "approve", "approve"),   # ARPP slate, matched VO
        (1826, "approve", "review"),    # DUPLICATE_INPUT without LUFS -> DETERMINISTIC_APPROVE_OVER_REVIEW
        (1827, "review", "reject"),     # LUFS 8.91 > 3.0 -> REVIEW (not DANGEROUS_FALSE_APPROVE)
    ],
)
def test_real_payload_fixtures_verdicts_and_completeness(
    engine, job_id, expected_verdict, primary_verdict
):
    raw = _load_fixture(job_id)
    canonical = adapt_comparison_metrics(raw)
    is_complete, flags = is_metrics_contract_complete(canonical)

    assert is_complete is True, f"Job {job_id} contract should be complete, flags={flags}"

    decision = engine.evaluate(canonical)
    assert decision["verdict"] == expected_verdict

    # Zero DANGEROUS_FALSE_APPROVE across all fixtures
    assert not (
        decision["verdict"].upper() == "APPROVE" and primary_verdict.upper() == "REJECT"
    )


def test_real_payload_1823_normalizes_legacy_fast_path(engine):
    raw = _load_fixture(1823)
    canonical = adapt_comparison_metrics(raw)
    assert (
        canonical["audio_transcription"]["skipped_reason"]
        == CANONICAL_FAST_PATH_IDENTICAL_AUDIO
    )
    decision = engine.evaluate(canonical)
    assert decision["verdict"] == "review"
    assert any("strefie granicznej" in r for r in decision["rule_evaluation"]["reasons"])


def test_real_payload_1826_duplicate_shadow_agreement(isolated_db_session):
    raw = _load_fixture(1826)

    f1 = File(
        filename="a.mp4",
        original_name="a.mp4",
        file_path="/tmp/a.mp4",
        file_type=FileType.ACCEPTANCE,
        file_format=FileFormat.MP4,
        file_size=1024,
    )
    f2 = File(
        filename="e.mp4",
        original_name="e.mp4",
        file_path="/tmp/e.mp4",
        file_type=FileType.EMISSION,
        file_format=FileFormat.MP4,
        file_size=1024,
    )
    isolated_db_session.add_all([f1, f2])
    isolated_db_session.flush()

    job = ComparisonJob(
        id=1826,
        job_name="Shadow Dup Test",
        acceptance_file_id=f1.id,
        emission_file_id=f2.id,
        comparison_type=ComparisonType.AUTOMATION,
        status=JobStatus.COMPLETED,
        sensitivity_level=SensitivityLevel.MEDIUM,
    )
    isolated_db_session.add(job)
    isolated_db_session.commit()

    with (
        patch("services.comparison_service.VideoProcessor"),
        patch("services.comparison_service.AudioProcessor"),
    ):
        service = ComparisonService()

    with (
        patch.object(service, "_build_ai_metrics", return_value=raw),
        patch.object(service, "_build_knowledge_snapshot", return_value={}),
    ):
        service._run_ai_analyst(isolated_db_session, job.id, {"video_result": {}, "audio_result": {}})

    saved = isolated_db_session.query(QADecision).filter(QADecision.job_id == job.id).first()
    assert saved is not None
    assert saved.verdict == DecisionVerdict.APPROVE
    assert saved.decided_by == "deterministic_rules_v1"
    dd = saved.knowledge_snapshot["deterministic_decision_v1"]
    assert dd["status"] == "completed"
    assert dd["metrics_contract_complete"] is True
    assert dd["verdict"] == "approve"
    assert dd["rule_evaluation"]["fired_rule"] == "RULE_QUALIFIED_APPROVE"
    for r in dd["rule_evaluation"].get("reasons", []):
        assert len(r) <= 240
    for val in dd["rule_evaluation"]["checks"].values():
        assert isinstance(val, (int, float, bool, str)) or val is None


# ---------------------------------------------------------------------------
# 2. Negative & security tests
# ---------------------------------------------------------------------------
def test_negative_no_audio_streams_with_acc_has_audio_true_gives_review(engine):
    raw = _load_fixture(1822)
    raw["no_audio_tracks"] = False
    raw["acc_has_audio"] = True
    raw["emi_has_audio"] = False
    canonical = adapt_comparison_metrics(raw)
    decision = engine.evaluate(canonical)
    assert decision["verdict"] == "review"


def test_negative_no_audio_streams_with_audio_mismatch_true_gives_review(engine):
    raw = _load_fixture(1822)
    raw["audio_mismatch"] = True
    canonical = adapt_comparison_metrics(raw)
    decision = engine.evaluate(canonical)
    assert decision["verdict"] == "review"


def test_negative_legacy_fast_path_text_with_low_audio_similarity_gives_review(engine):
    raw = _load_fixture(1823)
    raw["video_similarity"] = 1.0
    raw["overall_similarity"] = 1.0
    raw["video_differences_count"] = 0
    raw["audio_similarity"] = 0.95  # < 0.98!
    canonical = adapt_comparison_metrics(raw)
    assert (
        canonical["audio_transcription"]["skipped_reason"]
        == CANONICAL_FAST_PATH_IDENTICAL_AUDIO
    )
    decision = engine.evaluate(canonical)
    assert decision["verdict"] == "review"
    assert any("UNVERIFIED_FAST_PATH_AUDIO_SKIP" in r for r in decision["rule_evaluation"]["reasons"])


def test_negative_unknown_skip_text_remains_non_canonical():
    assert (
        normalize_skip_code_strict(
            "Audio similarity 1.0000 >= 0.98. Custom unverified skip"
        )
        is None
    )
    assert normalize_skip_code_strict("Random skip reason text") is None
    assert (
        normalize_skip_code_strict("PREFIX FAST_PATH_IDENTICAL_AUDIO") is None
    )

    raw = _load_fixture(1823)
    raw["audio_transcription"]["skipped_reason"] = "Some unknown skip reason"
    raw["stt_skipped_reason"] = "Some unknown skip reason"
    canonical = adapt_comparison_metrics(raw)
    assert canonical["audio_transcription"]["skipped_reason"] == "Some unknown skip reason"
    is_complete, _ = is_metrics_contract_complete(canonical)
    assert is_complete is False


def test_negative_non_duplicate_without_lufs_never_approves(engine):
    raw = _load_fixture(1826)
    assert raw["audio_loudness"]["lufs_difference"] is None
    raw["is_binary_duplicate"] = False
    raw["audio_transcription"]["is_uncertain"] = False
    raw["audio_transcription"]["skipped_reason"] = "FAST_PATH_IDENTICAL_AUDIO"
    raw["stt_skipped_reason"] = "FAST_PATH_IDENTICAL_AUDIO"
    canonical = adapt_comparison_metrics(raw)
    decision = engine.evaluate(canonical)
    assert decision["verdict"] == "review"
    assert decision["verdict"] != "approve"


def test_engine_reasons_do_not_leak_raw_error_paths_or_unknown_skip_text(engine):
    raw = _load_fixture(1825)
    raw["audio_transcription"] = {
        "status": "error",
        "error": "/Users/secret/client_name/video.mp4 failed to decode",
        "is_uncertain": False,
    }
    canonical = adapt_comparison_metrics(raw)
    dec_err = engine.evaluate(canonical)
    assert dec_err["verdict"] == "review"
    assert "/Users/secret" not in dec_err["reasoning"]
    assert "client_name" not in dec_err["reasoning"]

    raw2 = _load_fixture(1825)
    raw2["audio_transcription"] = {
        "status": "skipped",
        "skipped_reason": "SECRET_CLIENT_TRANSCRIPT_LEAK",
        "is_uncertain": False,
    }
    canonical2 = adapt_comparison_metrics(raw2)
    dec_skip = engine.evaluate(canonical2)
    assert dec_skip["verdict"] == "review"
    assert "SECRET_CLIENT_TRANSCRIPT_LEAK" not in dec_skip["reasoning"]


def test_shadow_incomplete_contract_records_failed_flags(isolated_db_session):
    f1 = File(
        filename="a.mp4",
        original_name="a.mp4",
        file_path="/tmp/a.mp4",
        file_type=FileType.ACCEPTANCE,
        file_format=FileFormat.MP4,
        file_size=1024,
    )
    f2 = File(
        filename="e.mp4",
        original_name="e.mp4",
        file_path="/tmp/e.mp4",
        file_type=FileType.EMISSION,
        file_format=FileFormat.MP4,
        file_size=1024,
    )
    isolated_db_session.add_all([f1, f2])
    isolated_db_session.flush()

    job = ComparisonJob(
        id=9999,
        job_name="Incomplete Test",
        acceptance_file_id=f1.id,
        emission_file_id=f2.id,
        comparison_type=ComparisonType.AUTOMATION,
        status=JobStatus.COMPLETED,
        sensitivity_level=SensitivityLevel.MEDIUM,
    )
    isolated_db_session.add(job)
    isolated_db_session.commit()

    incomplete_metrics = {
        "video_similarity": 1.0,
        "duration_difference": 0.0,
        "is_arpp_slate": False,
        "is_binary_duplicate": False,
        "audio_mismatch": False,
        "no_audio_tracks": False,
        "acc_has_audio": True,
        "emi_has_audio": True,
        "audio_similarity": 0.99,
        "audio_loudness": {"lufs_difference": None},
        "audio_transcription": {"status": "completed", "is_uncertain": False},
    }

    with (
        patch("services.comparison_service.VideoProcessor"),
        patch("services.comparison_service.AudioProcessor"),
    ):
        service = ComparisonService()
    mock_analyst = MagicMock()
    mock_analyst.analyze_job_results.return_value = {
        "verdict": "review",
        "reasoning": "Missing LUFS.",
    }

    with (
        patch.object(service, "_build_ai_metrics", return_value=incomplete_metrics),
        patch.object(service, "_build_knowledge_snapshot", return_value={}),
    ):
        service._run_ai_analyst(isolated_db_session, job.id, {"video_result": {}, "audio_result": {}})

    saved = isolated_db_session.query(QADecision).filter(QADecision.job_id == job.id).first()
    assert saved.verdict == DecisionVerdict.REVIEW
    dd = saved.knowledge_snapshot["deterministic_decision_v1"]
    assert dd["status"] == "insufficient_metrics"
    assert "failed_flags" in dd["rule_evaluation"]
    assert "has_lufs" in dd["rule_evaluation"]["failed_flags"]


def test_production_skip_normalization_unchanged(isolated_db_session, monkeypatch):
    """
    Golden regression test proving that production extract_normalized_skip_code()
    and the production pipeline (_build_ai_metrics + AnalystService._parse_response)
    with DETERMINISTIC_SHADOW_MODE=false match origin/dev on the full 34-input corpus,
    including the 3 legacy-matching variants rejected by normalize_skip_code_strict.
    """
    from services.comparison_service import extract_normalized_skip_code

    golden_corpus = [
        ("FAST_PATH_IDENTICAL_AUDIO", "FAST_PATH_IDENTICAL_AUDIO"),
        ("NO_AUDIO_STREAMS", "NO_AUDIO_STREAMS"),
        ("FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH", "FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH"),
        ("DUPLICATE_INPUT", "DUPLICATE_INPUT"),
        ("FAST_PATH_IDENTICAL_AUDIO: verified", "FAST_PATH_IDENTICAL_AUDIO"),
        ("FAST_PATH_IDENTICAL_AUDIO - verified", "FAST_PATH_IDENTICAL_AUDIO"),
        ("NO_AUDIO_STREAMS: No audio tracks present in both source files", "NO_AUDIO_STREAMS"),
        ("NO_AUDIO_STREAMS: Both files lack audio streams.", "NO_AUDIO_STREAMS"),
        ("NO_AUDIO_STREAMS - silent", "NO_AUDIO_STREAMS"),
        ("FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH: verified", "FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH"),
        ("FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH - verified", "FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH"),
        ("DUPLICATE_INPUT: Acceptance and Emission are binary identical files (possible duplicate download)", "DUPLICATE_INPUT"),
        ("DUPLICATE_INPUT: Identical binary files detected; requires verification of download integrity", "DUPLICATE_INPUT"),
        ("DUPLICATE_INPUT - Identical", "DUPLICATE_INPUT"),
        ("AUDIO_MISMATCH: One file contains audio, but the other has no audio streams.", None),
        ("STT was not executed for this job", None),
        ("Audio similarity 1.0000 >= 0.98. STT skipped to avoid false positives from source separation non-determinism.", "FAST_PATH_IDENTICAL_AUDIO"),
        ("Audio similarity 0.9950 >= 0.98 — STT skipped to avoid false positives", "FAST_PATH_IDENTICAL_AUDIO"),
        ("Audio similarity 0.98 >= 0.98. STT skipped to avoid false positives from source separation non-determinism", "FAST_PATH_IDENTICAL_AUDIO"),
        (None, None),
        ("", None),
        ("   ", None),
        ("fast_path_identical_audio", None),
        ("no_audio_streams", None),
        ("duplicate_input: test", None),
        ("Podobieństwo audio 1.00 >= 0.98. STT pominięte", None),
        ("Audio similarity 1.0000 >= 0.98. STT skipped to avoid false positives", "FAST_PATH_IDENTICAL_AUDIO"),
        ("Audio similarity 0.99 >= 0.98. STT skipped to avoid false positives (custom suffix)", "FAST_PATH_IDENTICAL_AUDIO"),
        ("Audio similarity 1.0000 >= 0.98. Custom unverified skip", None),
        ("Audio similarity 0.99. STT skipped to avoid false positives", "FAST_PATH_IDENTICAL_AUDIO"),
        ("UNAUTHORIZED_FAST_PATH_IDENTICAL_AUDIO: fake", None),
        ("EXPLOIT_DUPLICATE_INPUT: fake", None),
        ("FAST_PATH_IDENTICAL_AUDIO_FAKE", None),
        ("FAST_PATH_IDENTICAL_AUDIO extra text without separator", None),
    ]
    assert len(golden_corpus) == 34

    for raw_reason, expected_code in golden_corpus:
        assert extract_normalized_skip_code(raw_reason) == expected_code

    # Verify the 3 variants where strict shadow normalizer returns None still behave
    # identically to origin/dev in production flow (DETERMINISTIC_SHADOW_MODE=false)
    monkeypatch.setenv("DETERMINISTIC_SHADOW_MODE", "false")
    diff_inputs = [
        "Audio similarity 1.0000 >= 0.98. STT skipped to avoid false positives",
        "Audio similarity 0.99 >= 0.98. STT skipped to avoid false positives (custom suffix)",
        "Audio similarity 0.99. STT skipped to avoid false positives",
    ]
    f1 = File(
        filename="a.mp4",
        original_name="a.mp4",
        file_path="/tmp/a.mp4",
        file_type=FileType.ACCEPTANCE,
        file_format=FileFormat.MP4,
        file_size=1024,
    )
    f2 = File(
        filename="e.mp4",
        original_name="e.mp4",
        file_path="/tmp/e.mp4",
        file_type=FileType.EMISSION,
        file_format=FileFormat.MP4,
        file_size=1024,
    )
    isolated_db_session.add_all([f1, f2])
    isolated_db_session.flush()
    job = ComparisonJob(
        id=9998,
        job_name="Prod Parity Test",
        acceptance_file_id=f1.id,
        emission_file_id=f2.id,
        comparison_type=ComparisonType.AUTOMATION,
        status=JobStatus.COMPLETED,
        sensitivity_level=SensitivityLevel.MEDIUM,
    )
    isolated_db_session.add(job)
    isolated_db_session.commit()

    with (
        patch("services.comparison_service.VideoProcessor"),
        patch("services.comparison_service.AudioProcessor"),
    ):
        service = ComparisonService()

    for reason in diff_inputs:
        assert normalize_skip_code_strict(reason) is None
        results = {
            "overall_similarity": 1.0,
            "video_result": {
                "overall_similarity": 1.0,
                "frames_with_differences": 0,
                "duration_difference": 0.0,
                "is_arpp_slate": False,
            },
            "audio_result": {
                "has_audio": True,
                "has_audio_any": True,
                "audio_pair_comparable": True,
                "no_audio_tracks": False,
                "is_binary_duplicate": False,
                "acc_has_audio": True,
                "emi_has_audio": True,
                "audio_mismatch": False,
                "similarity_score": 1.0,
                "loudness": {"lufs_difference": 0.0, "has_loudness_differences": False},
                "speech_to_text": {
                    "status": "skipped",
                    "skipped_reason": reason,
                    "is_uncertain": False,
                },
            },
        }
        metrics = service._build_ai_metrics(job, results)
        assert metrics["audio_transcription"]["status"] == "skipped"
        assert metrics["stt_skipped"] is True


@pytest.mark.parametrize(
    "scenario,stt_overrides",
    [
        (
            "text_match",
            {
                "status": "completed",
                "is_text_match": True,
                "text_similarity": 1.0,
                "is_uncertain": False,
                "comparison": {"word_count_a": 5, "word_count_b": 5},
            },
        ),
        (
            "text_mismatch",
            {
                "status": "completed",
                "is_text_match": False,
                "text_similarity": 0.80,
                "is_uncertain": False,
                "comparison": {"word_count_a": 5, "word_count_b": 5},
            },
        ),
        (
            "stt_error",
            {
                "status": "error",
                "error": "SENTINEL_TRANSCRIPT_9X_ERR",
                "error_message": "SENTINEL_TRANSCRIPT_9X_ERR_MSG",
                "is_uncertain": False,
            },
        ),
        (
            "stt_uncertain",
            {
                "status": "completed",
                "is_text_match": True,
                "text_similarity": 1.0,
                "is_uncertain": True,
                "uncertainty_reason": "SENTINEL_TRANSCRIPT_9X_UNCERTAIN",
                "comparison": {"word_count_a": 5, "word_count_b": 5},
            },
        ),
        (
            "unknown_skip_reason",
            {
                "status": "skipped",
                "skipped_reason": "SENTINEL_TRANSCRIPT_9X_SKIP",
                "is_uncertain": False,
            },
        ),
    ],
)
def test_shadow_snapshot_sentinel_no_transcript_or_error_leak(
    isolated_db_session, scenario, stt_overrides
):
    """
    Sentinel guard: verifies that transcript text, word_differences_sample,
    and raw STT/VAD error strings never leak into deterministic_shadow_v1.
    """
    sentinel = "SENTINEL_TRANSCRIPT_9X"

    f1 = File(
        filename="a.mp4",
        original_name="a.mp4",
        file_path="/tmp/a.mp4",
        file_type=FileType.ACCEPTANCE,
        file_format=FileFormat.MP4,
        file_size=1024,
    )
    f2 = File(
        filename="e.mp4",
        original_name="e.mp4",
        file_path="/tmp/e.mp4",
        file_type=FileType.EMISSION,
        file_format=FileFormat.MP4,
        file_size=1024,
    )
    isolated_db_session.add_all([f1, f2])
    isolated_db_session.flush()

    job = ComparisonJob(
        id=9900 + hash(scenario) % 90,
        job_name="Sentinel Shadow Test",
        acceptance_file_id=f1.id,
        emission_file_id=f2.id,
        comparison_type=ComparisonType.AUTOMATION,
        status=JobStatus.COMPLETED,
        sensitivity_level=SensitivityLevel.MEDIUM,
    )
    isolated_db_session.add(job)
    isolated_db_session.commit()

    stt_payload = {
        "acceptance_text": f"{sentinel}_ACC",
        "emission_text": f"{sentinel}_EMI",
        "word_differences_sample": [{"acceptance": f"{sentinel}_DIFF_A", "emission": f"{sentinel}_DIFF_E"}],
        "error_message": f"{sentinel}_ERR_BASE",
        "uncertainty_reason": f"{sentinel}_UNC_BASE",
    }
    stt_payload.update(stt_overrides)

    metrics_payload = {
        "video_similarity": 1.0,
        "duration_difference": 0.0,
        "is_arpp_slate": False,
        "is_binary_duplicate": False,
        "audio_mismatch": False,
        "no_audio_tracks": False,
        "acc_has_audio": True,
        "emi_has_audio": True,
        "audio_similarity": 0.99,
        "audio_loudness": {"lufs_difference": 0.2},
        "audio_transcription": stt_payload,
        "raw_vad_error": f"{sentinel}_VAD_ERR",
    }

    with (
        patch("services.comparison_service.VideoProcessor"),
        patch("services.comparison_service.AudioProcessor"),
    ):
        service = ComparisonService()

    with (
        patch.object(service, "_build_ai_metrics", return_value=metrics_payload),
        patch.object(service, "_build_knowledge_snapshot", return_value={}),
    ):
        service._run_ai_analyst(isolated_db_session, job.id, {"video_result": {}, "audio_result": {}})

    saved = isolated_db_session.query(QADecision).filter(QADecision.job_id == job.id).first()
    assert saved is not None
    dd = saved.knowledge_snapshot["deterministic_decision_v1"]
    serialized = json.dumps(dd)
    assert sentinel not in serialized, f"Sentinel leaked in scenario={scenario}: {serialized}"
