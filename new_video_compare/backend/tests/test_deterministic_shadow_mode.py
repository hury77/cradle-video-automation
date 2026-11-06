"""
Test suite for Deterministic Shadow Mode in Cradle Video QA Automation.

Verifies:
1. Feature flag OFF:
   - Zero shadow adapter/engine calls
   - No 'deterministic_shadow_v1' key in knowledge_snapshot
   - Primary QA decision/verdict completely unchanged
2. Feature flag ON + complete metrics:
   - Knowledge snapshot contains deterministic_shadow_v1 with complete metadata
   - shadow_status = "completed"
   - Correct divergence category (AGREEMENT, DETERMINISTIC_REVIEW, etc.)
   - Valid rule_evaluation and strict types
3. Feature flag ON + incomplete metrics:
   - Category divergence is INSUFFICIENT_HISTORICAL_METRICS
   - metrics_contract_complete is False
   - Does NOT alter primary verdict
4. Shadow exception handling:
   - Primary decision still saved without disruption
   - shadow_status = "error"
   - Redacted error message without file paths
5. System override propagation:
   - When STT triggers system override, primary_verdict in shadow record reflects the override verdict
6. Strict SQLite persistence on isolated in-memory DB:
   - Verifies QADecision saves and re-reads JSON correctly
7. Strict JSON serialization:
   - Confirms no non-serializable objects (sets, paths, NaNs) exist in the snapshot
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup import paths
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from config import settings
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
from services.deterministic_decision_engine import DeterministicDecisionEngineV1
from services.deterministic_metrics_adapter import adapt_comparison_metrics, is_metrics_contract_complete


@pytest.fixture
def isolated_db_session():
    """Provides a totally isolated in-memory SQLite database session."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def dummy_job(isolated_db_session):
    """Creates a sample ComparisonJob in the isolated database."""
    file_a = File(
        filename="acc.mp4",
        original_name="acc.mp4",
        file_path="/tmp/acc.mp4",
        file_type=FileType.ACCEPTANCE,
        file_format=FileFormat.MP4,
        file_size=1024,
    )
    file_b = File(
        filename="emi.mp4",
        original_name="emi.mp4",
        file_path="/tmp/emi.mp4",
        file_type=FileType.EMISSION,
        file_format=FileFormat.MP4,
        file_size=1024,
    )
    isolated_db_session.add_all([file_a, file_b])
    isolated_db_session.commit()

    job = ComparisonJob(
        job_name="Test_Shadow_Job",
        client_name="TestClient",
        cradle_id="1234567",
        acceptance_file_id=file_a.id,
        emission_file_id=file_b.id,
        status=JobStatus.COMPLETED,
        comparison_type=ComparisonType.FULL,
        sensitivity_level=SensitivityLevel.MEDIUM,
    )
    isolated_db_session.add(job)
    isolated_db_session.commit()
    isolated_db_session.refresh(job)
    return job


def _build_dummy_results(complete: bool = True, sim: float = 0.99, mismatch: bool = False):
    """Builds synthetic results dictionary."""
    results = {
        "overall_similarity": sim,
        "video_result": {
            "overall_similarity": sim,
            "duration_difference": 0.0,
            "frames_with_differences": 0,
            "is_arpp_slate": False,
        },
        "audio_result": {
            "similarity_score": 0.99,
            "audio_mismatch": mismatch,
            "no_audio_tracks": False,
            "acc_has_audio": True,
            "emi_has_audio": True,
            "is_binary_duplicate": False,
            "loudness": {
                "acceptance": {"integrated_lufs": -24.0},
                "emission": {"integrated_lufs": -24.0},
                "comparison": {"lufs_difference": 0.0, "peak_difference_db": 0.0},
                "has_loudness_differences": False,
            },
            "speech_to_text": {
                "status": "completed",
                "text_similarity": 1.0,
                "is_text_match": True,
                "acceptance_text": "Hello world",
                "emission_text": "Hello world",
                "is_uncertain": False,
                "comparison": {"word_count_a": 2, "word_count_b": 2, "word_differences": []},
            },
            "raw_vad_metrics_complete": True,
            "raw_vad_inconclusive": False,
            "raw_vad_speech": True,
            "raw_vad_error": None,
            "music_proportion": 0.1,
        },
    }
    if not complete:
        # Keep speech_to_text completed (so primary flow is not overridden to REVIEW),
        # but omit loudness difference so shadow metrics contract completeness fails.
        results["audio_result"]["loudness"] = {"comparison": {}}
    return results


@pytest.fixture
def comparison_service_instance():
    """Provides a ComparisonService instance with mocked heavy processors."""
    with patch("services.comparison_service.VideoProcessor"), \
         patch("services.comparison_service.AudioProcessor"):
        svc = ComparisonService()
    return svc

class TestDeterministicShadowMode:

    def test_flag_off_produces_no_shadow_snapshot(self, isolated_db_session, dummy_job, comparison_service_instance, monkeypatch):
        """When flag is OFF, shadow evaluation never runs and knowledge_snapshot has no shadow key."""
        monkeypatch.setattr(settings, "deterministic_shadow_mode", False)
        monkeypatch.setenv("DETERMINISTIC_SHADOW_MODE", "false")

        service = comparison_service_instance
        results = _build_dummy_results(complete=True)

        mock_analyst = MagicMock()
        mock_analyst.analyze_job_results.return_value = {
            "verdict": "approve",
            "confidence": 0.95,
            "reasoning": "Standard AI approve reasoning",
        }

        with patch("services.analyst_service.get_analyst", return_value=mock_analyst), \
             patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}):
            service._run_ai_analyst(isolated_db_session, dummy_job.id, results)

        decision = isolated_db_session.query(QADecision).filter(QADecision.job_id == dummy_job.id).first()
        assert decision is not None
        assert decision.verdict == DecisionVerdict.APPROVE
        assert decision.decided_by == "agent"
        assert "deterministic_shadow_v1" not in decision.knowledge_snapshot

    def test_flag_on_complete_metrics_creates_shadow_record(self, isolated_db_session, dummy_job, comparison_service_instance, monkeypatch):
        """When flag is ON and metrics are complete, creates a complete shadow record in knowledge_snapshot."""
        monkeypatch.setattr(settings, "deterministic_shadow_mode", True)
        monkeypatch.setenv("DETERMINISTIC_SHADOW_MODE", "true")

        service = comparison_service_instance
        results = _build_dummy_results(complete=True, sim=0.99)

        mock_analyst = MagicMock()
        mock_analyst.analyze_job_results.return_value = {
            "verdict": "approve",
            "confidence": 0.95,
            "reasoning": "Ollama approves",
        }

        with patch("services.analyst_service.get_analyst", return_value=mock_analyst), \
             patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}):
            service._run_ai_analyst(isolated_db_session, dummy_job.id, results)

        decision = isolated_db_session.query(QADecision).filter(QADecision.job_id == dummy_job.id).first()
        assert decision is not None
        assert decision.verdict == DecisionVerdict.APPROVE
        assert "deterministic_shadow_v1" in decision.knowledge_snapshot

        shadow = decision.knowledge_snapshot["deterministic_shadow_v1"]
        assert shadow["engine"] == "DeterministicDecisionEngineV1"
        assert shadow["engine_version"] == "1.0.0"
        assert shadow["shadow_status"] == "completed"
        assert shadow["shadow_verdict"] == "approve"
        assert shadow["shadow_confidence"] == 1.0
        assert shadow["metrics_contract_complete"] is True
        assert shadow["primary_verdict"] == "approve"
        assert shadow["primary_decided_by"] == "agent"
        assert shadow["category_divergence"] == "AGREEMENT"
        assert shadow["shadow_error"] is None
        assert "rule_evaluation" in shadow
        assert shadow["rule_evaluation"]["engine_version"] == "1.0.0"

    def test_flag_on_incomplete_metrics_categorized_as_insufficient(self, isolated_db_session, dummy_job, comparison_service_instance, monkeypatch):
        """When flag is ON but metrics are incomplete, categorizes as INSUFFICIENT_HISTORICAL_METRICS without calling engine."""
        monkeypatch.setattr(settings, "deterministic_shadow_mode", True)
        monkeypatch.setenv("DETERMINISTIC_SHADOW_MODE", "true")

        service = comparison_service_instance
        results = _build_dummy_results(complete=False, sim=0.99)

        mock_analyst = MagicMock()
        mock_analyst.analyze_job_results.return_value = {
            "verdict": "approve",
            "confidence": 0.90,
            "reasoning": "AI approve with missing audio",
        }

        with patch("services.analyst_service.get_analyst", return_value=mock_analyst), \
             patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}), \
             patch("services.deterministic_decision_engine.DeterministicDecisionEngineV1.evaluate") as mock_engine_eval:
            service._run_ai_analyst(isolated_db_session, dummy_job.id, results)

        mock_engine_eval.assert_not_called()

        decision = isolated_db_session.query(QADecision).filter(QADecision.job_id == dummy_job.id).first()
        assert decision is not None
        assert decision.verdict == DecisionVerdict.APPROVE  # Primary verdict remains approve!
        assert "deterministic_shadow_v1" in decision.knowledge_snapshot

        shadow = decision.knowledge_snapshot["deterministic_shadow_v1"]
        assert shadow["shadow_status"] == "insufficient_metrics"
        assert shadow["shadow_verdict"] is None
        assert shadow["shadow_confidence"] == 0.0
        assert shadow["metrics_contract_complete"] is False
        assert shadow["category_divergence"] == "INSUFFICIENT_HISTORICAL_METRICS"
        assert shadow["primary_verdict"] == "approve"
        assert shadow["rule_evaluation"]["fired_rule"] == "INSUFFICIENT_METRICS_CONTRACT"

    def test_missing_probe_flags_remain_none_and_trigger_insufficient(self, isolated_db_session, dummy_job, comparison_service_instance, monkeypatch):
        """Missing or non-bool audio probe flags are preserved as None, not cast to False."""
        monkeypatch.setattr(settings, "deterministic_shadow_mode", True)
        monkeypatch.setenv("DETERMINISTIC_SHADOW_MODE", "true")

        service = comparison_service_instance
        results = _build_dummy_results(complete=True)
        # Omit acc_has_audio and put string into audio_mismatch
        del results["audio_result"]["acc_has_audio"]
        results["audio_result"]["audio_mismatch"] = "false"  # not exact bool!

        mock_analyst = MagicMock()
        mock_analyst.analyze_job_results.return_value = {
            "verdict": "approve",
            "confidence": 0.95,
            "reasoning": "AI approves",
        }

        with patch("services.analyst_service.get_analyst", return_value=mock_analyst), \
             patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}), \
             patch("services.deterministic_decision_engine.DeterministicDecisionEngineV1.evaluate") as mock_engine_eval:
            service._run_ai_analyst(isolated_db_session, dummy_job.id, results)

        mock_engine_eval.assert_not_called()
        decision = isolated_db_session.query(QADecision).filter(QADecision.job_id == dummy_job.id).first()
        shadow = decision.knowledge_snapshot["deterministic_shadow_v1"]
        assert shadow["shadow_status"] == "insufficient_metrics"
        assert shadow["metrics_contract_complete"] is False
        assert decision.metrics_snapshot["acc_has_audio"] is None
        assert decision.metrics_snapshot["audio_mismatch"] is None

    def test_shadow_exception_redacts_paths(self, isolated_db_session, dummy_job, comparison_service_instance, monkeypatch):
        """If engine or adapter raises unexpected exception with disk paths or details, error is strictly redacted to fixed format."""
        monkeypatch.setattr(settings, "deterministic_shadow_mode", True)
        monkeypatch.setenv("DETERMINISTIC_SHADOW_MODE", "true")

        service = comparison_service_instance
        results = _build_dummy_results(complete=True)

        mock_analyst = MagicMock()
        mock_analyst.analyze_job_results.return_value = {
            "verdict": "approve",
            "confidence": 0.90,
            "reasoning": "Normal AI decision",
        }

        home_secret = f"{Path.home()}/secret/vault/file.py"
        with patch("services.analyst_service.get_analyst", return_value=mock_analyst), \
             patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}), \
             patch("services.deterministic_decision_engine.DeterministicDecisionEngineV1.evaluate", side_effect=RuntimeError(f"Engine crash at {home_secret} and /var/log/private.log with json {{'foo': 'bar'}} and transcript 'hello'")):
            service._run_ai_analyst(isolated_db_session, dummy_job.id, results)

        decision = isolated_db_session.query(QADecision).filter(QADecision.job_id == dummy_job.id).first()
        shadow = decision.knowledge_snapshot["deterministic_shadow_v1"]
        assert shadow["shadow_status"] == "error"
        assert shadow["shadow_error"] == "RuntimeError: shadow evaluation failed"
        assert str(Path.home()) not in shadow["shadow_error"]
        assert "/var/log" not in shadow["shadow_error"]
        assert "transcript" not in shadow["shadow_error"]
        assert "secret" not in shadow["shadow_error"]
        assert len(shadow["shadow_error"]) <= 120

    def test_redact_shadow_error_function_directly(self):
        """Unit test for redact_shadow_error: strict fixed format, no leak of path, JSON, text, or message."""
        from services.deterministic_metrics_adapter import redact_shadow_error

        # None returns empty string
        assert redact_shadow_error(None) == ""

        # Different exception types preserve exception class name and fixed suffix
        val_err = ValueError("Sensitive /Users/hubert/vault data with JSON {'key': 'val'} and transcript 'Sample speech' Cradle ID 1147007")
        assert redact_shadow_error(val_err) == "ValueError: shadow evaluation failed"

        key_err = KeyError("some_internal_metric_key")
        assert redact_shadow_error(key_err) == "KeyError: shadow evaluation failed"

        type_err = TypeError("Unexpected /tmp/scratch/cache.json")
        assert redact_shadow_error(type_err) == "TypeError: shadow evaluation failed"

        # Ensure no parts of message leak
        res = redact_shadow_error(val_err)
        assert "/Users" not in res
        assert "Sensitive" not in res
        assert "vault" not in res
        assert "JSON" not in res
        assert "transcript" not in res
        assert "1147007" not in res
        assert "Sample speech" not in res

    def test_flag_off_metrics_snapshot_and_knowledge_identical(self, isolated_db_session, dummy_job, comparison_service_instance, monkeypatch):
        """When flag is OFF, metrics_snapshot and knowledge_snapshot are identical to pre-shadow mode, no shadow key, engine/adapter not imported."""
        monkeypatch.setattr(settings, "deterministic_shadow_mode", False)
        monkeypatch.setenv("DETERMINISTIC_SHADOW_MODE", "false")

        service = comparison_service_instance
        results = _build_dummy_results(complete=True)

        mock_analyst = MagicMock()
        mock_analyst.analyze_job_results.return_value = {
            "verdict": "approve",
            "confidence": 0.95,
            "reasoning": "AI approves cleanly",
        }

        # Assert adapter and engine are never called when flag is OFF
        with patch("services.analyst_service.get_analyst", return_value=mock_analyst), \
             patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {"cradle_id": "1234567"}}), \
             patch("services.deterministic_decision_engine.DeterministicDecisionEngineV1.evaluate") as mock_engine, \
             patch("services.deterministic_metrics_adapter.adapt_comparison_metrics") as mock_adapter:
            service._run_ai_analyst(isolated_db_session, dummy_job.id, results)

        mock_engine.assert_not_called()
        mock_adapter.assert_not_called()

        decision = isolated_db_session.query(QADecision).filter(QADecision.job_id == dummy_job.id).first()
        assert decision is not None
        assert decision.verdict == DecisionVerdict.APPROVE
        assert decision.reasoning == "AI approves cleanly"
        assert decision.ai_reasoning == "AI approves cleanly"
        assert decision.decided_by == "agent"
        assert "deterministic_shadow_v1" not in decision.knowledge_snapshot
        # Probe flags must NOT exist in metrics_snapshot when flag is OFF
        assert "is_binary_duplicate" not in decision.metrics_snapshot
        assert "acc_has_audio" not in decision.metrics_snapshot
        assert "emi_has_audio" not in decision.metrics_snapshot
        assert "raw_vad_metrics_complete" not in decision.metrics_snapshot
        # Existing audio_loudness format is exactly preserved
        assert decision.metrics_snapshot["audio_loudness"]["has_loudness_issue"] is False

    def test_shadow_exception_does_not_break_primary_flow(self, isolated_db_session, dummy_job, comparison_service_instance, monkeypatch):
        """If engine or adapter raises unexpected exception, primary flow succeeds and redacted error is saved."""
        monkeypatch.setattr(settings, "deterministic_shadow_mode", True)
        monkeypatch.setenv("DETERMINISTIC_SHADOW_MODE", "true")

        service = comparison_service_instance
        results = _build_dummy_results(complete=True)

        mock_analyst = MagicMock()
        mock_analyst.analyze_job_results.return_value = {
            "verdict": "approve",
            "confidence": 0.90,
            "reasoning": "Normal AI decision",
        }

        with patch("services.analyst_service.get_analyst", return_value=mock_analyst), \
             patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}), \
             patch("services.deterministic_decision_engine.DeterministicDecisionEngineV1.evaluate", side_effect=RuntimeError("Simulated engine internal fault at /Users/hubert/secret/code.py")):
            service._run_ai_analyst(isolated_db_session, dummy_job.id, results)

        decision = isolated_db_session.query(QADecision).filter(QADecision.job_id == dummy_job.id).first()
        assert decision is not None
        assert decision.verdict == DecisionVerdict.APPROVE
        assert "deterministic_shadow_v1" in decision.knowledge_snapshot

        shadow = decision.knowledge_snapshot["deterministic_shadow_v1"]
        assert shadow["shadow_status"] == "error"
        assert shadow["shadow_verdict"] is None
        assert shadow["shadow_confidence"] == 0.0
        assert "RuntimeError" in shadow["shadow_error"]
        assert shadow["primary_verdict"] == "approve"

    def test_system_override_propagation(self, isolated_db_session, dummy_job, comparison_service_instance, monkeypatch):
        """When STT failure overrides AI APPROVE to REVIEW, primary_verdict in shadow record reflects the override."""
        monkeypatch.setattr(settings, "deterministic_shadow_mode", True)
        monkeypatch.setenv("DETERMINISTIC_SHADOW_MODE", "true")

        service = comparison_service_instance
        results = _build_dummy_results(complete=True)
        # Mark STT as failed
        results["audio_result"]["speech_to_text"]["status"] = "failed"
        results["audio_result"]["speech_to_text"]["error_message"] = "Whisper OOM error"

        mock_analyst = MagicMock()
        mock_analyst.analyze_job_results.return_value = {
            "verdict": "approve",  # AI attempts to approve
            "confidence": 0.95,
            "reasoning": "AI says approve",
        }

        with patch("services.analyst_service.get_analyst", return_value=mock_analyst), \
             patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}):
            service._run_ai_analyst(isolated_db_session, dummy_job.id, results)

        decision = isolated_db_session.query(QADecision).filter(QADecision.job_id == dummy_job.id).first()
        assert decision.verdict == DecisionVerdict.REVIEW
        assert "[SYSTEM OVERRIDE]" in decision.reasoning

        shadow = decision.knowledge_snapshot["deterministic_shadow_v1"]
        assert shadow["primary_verdict"] == "review"
        assert shadow["primary_decided_by"] == "system"

    def test_strict_json_serialization(self, isolated_db_session, dummy_job, comparison_service_instance, monkeypatch):
        """Ensures that entire knowledge_snapshot with shadow data is strictly serializable to standard JSON."""
        monkeypatch.setattr(settings, "deterministic_shadow_mode", True)
        monkeypatch.setenv("DETERMINISTIC_SHADOW_MODE", "true")

        service = comparison_service_instance
        results = _build_dummy_results(complete=True)

        mock_analyst = MagicMock()
        mock_analyst.analyze_job_results.return_value = {
            "verdict": "approve",
            "confidence": 0.95,
            "reasoning": "AI approves",
        }

        with patch("services.analyst_service.get_analyst", return_value=mock_analyst), \
             patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}):
            service._run_ai_analyst(isolated_db_session, dummy_job.id, results)

        decision = isolated_db_session.query(QADecision).filter(QADecision.job_id == dummy_job.id).first()
        raw_json = json.dumps(decision.knowledge_snapshot)
        assert isinstance(raw_json, str)
        parsed = json.loads(raw_json)
        assert parsed["deterministic_shadow_v1"]["shadow_status"] == "completed"
