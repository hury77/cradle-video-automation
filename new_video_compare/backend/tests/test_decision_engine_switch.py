"""
Tests for deterministic-only engine, removed Ollama/agent, DecisionAdvisor seam,
GET /api/v1/system/info, and static no-Ollama policy.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from config import Settings
from models.models import (
    Base,
    ComparisonJob,
    ComparisonResult,
    ComparisonType,
    DecisionVerdict,
    File,
    FileFormat,
    FileType,
    JobStatus,
    QADecision,
    SensitivityLevel,
    VideoComparisonResult,
)
from services.comparison_service import ComparisonService
from services.decision_advisor import NullAdvisor, get_decision_advisor, run_advisor_advisory


@pytest.fixture
def isolated_db():
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
def sample_job(isolated_db):
    fa = File(
        filename="acc.mp4",
        original_name="acc.mp4",
        file_path="/tmp/acc.mp4",
        file_type=FileType.ACCEPTANCE,
        file_format=FileFormat.MP4,
        file_size=1024,
    )
    fb = File(
        filename="emi.mp4",
        original_name="emi.mp4",
        file_path="/tmp/emi.mp4",
        file_type=FileType.EMISSION,
        file_format=FileFormat.MP4,
        file_size=1024,
    )
    isolated_db.add_all([fa, fb])
    isolated_db.commit()

    job = ComparisonJob(
        job_name="Switch_Test_Job",
        client_name="TestClient",
        cradle_id="9999999",
        acceptance_file_id=fa.id,
        emission_file_id=fb.id,
        status=JobStatus.COMPLETED,
        comparison_type=ComparisonType.FULL,
        sensitivity_level=SensitivityLevel.AUTOMATION,
    )
    isolated_db.add(job)
    isolated_db.commit()
    isolated_db.refresh(job)
    return job


@pytest.fixture
def comp_service():
    with patch("services.comparison_service.VideoProcessor"), \
         patch("services.comparison_service.AudioProcessor"):
        return ComparisonService()


def _complete_results(
    video_sim=0.995,
    text_sim=1.0,
    words_a=6,
    words_b=6,
    transcript_a="Hello world one two three four",
    transcript_b="Hello world one two three four",
):
    return {
        "overall_similarity": video_sim,
        "video_result": {
            "overall_similarity": video_sim,
            "duration_difference": 0.0,
            "frames_with_differences": 0,
            "is_arpp_slate": False,
        },
        "audio_result": {
            "similarity_score": 0.99,
            "audio_mismatch": False,
            "no_audio_tracks": False,
            "acc_has_audio": True,
            "emi_has_audio": True,
            "is_binary_duplicate": False,
            "loudness": {
                "acceptance": {"integrated_lufs": -23.0},
                "emission": {"integrated_lufs": -23.0},
                "comparison": {"lufs_difference": 0.0, "peak_difference_db": 0.0},
                "has_loudness_differences": False,
            },
            "speech_to_text": {
                "status": "completed",
                "text_similarity": text_sim,
                "is_text_match": text_sim == 1.0,
                "acceptance_text": transcript_a,
                "emission_text": transcript_b,
                "is_uncertain": False,
                "comparison": {"word_count_a": words_a, "word_count_b": words_b, "word_differences": []},
            },
            "raw_vad_metrics_complete": True,
            "raw_vad_inconclusive": False,
            "raw_vad_speech": True,
            "raw_vad_error": None,
            "music_dominant": False,
            "music_proportion": 0.1,
        },
    }


class TestConfigAndPolicy:
    def test_default_is_deterministic_and_advisor_none(self, monkeypatch):
        monkeypatch.delenv("DECISION_ENGINE", raising=False)
        monkeypatch.delenv("ADVISOR_PROVIDER", raising=False)
        s = Settings(_env_file=None)
        assert s.decision_engine == "deterministic_rules_v1"
        assert s.advisor_provider == "none"

    def test_deprecated_agent_env_logs_agent_removed(self, monkeypatch, caplog):
        monkeypatch.setenv("DECISION_ENGINE", "agent")
        with caplog.at_level(logging.WARNING):
            s = Settings(_env_file=None)
        assert s.decision_engine == "deterministic_rules_v1"
        assert any("agent removed" in rec.message for rec in caplog.records)

    def test_invalid_advisor_provider_falls_back_to_none(self, monkeypatch, caplog):
        monkeypatch.setenv("ADVISOR_PROVIDER", "some_llm")
        with caplog.at_level(logging.WARNING):
            s = Settings(_env_file=None)
        assert s.advisor_provider == "none"
        assert any("ADVISOR_PROVIDER" in rec.message for rec in caplog.records)

    def test_static_policy_no_ollama_or_analyst_in_backend(self):
        import ast

        skip_dirs = {"venv", "test_venv", "__pycache__", "backups", "uploads", "uploads_dev", "docs", "legacy"}
        this_file = Path(__file__).resolve()
        violations = []
        for py_file in backend_dir.rglob("*.py"):
            if py_file.resolve() == this_file:
                continue
            if any(part in skip_dirs for part in py_file.parts):
                continue
            text = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(text, filename=str(py_file))
            rel = py_file.relative_to(backend_dir)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "ollama" in alias.name or "analyst_service" in alias.name:
                            violations.append(f"{rel}: import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    if "ollama" in mod or "analyst_service" in mod:
                        violations.append(f"{rel}: from {mod} import ...")
                elif isinstance(node, ast.Name) and node.id in ("AnalystService", "get_analyst"):
                    violations.append(f"{rel}: name {node.id}")
                elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "ollama":
                    violations.append(f"{rel}: ollama.{node.attr}")
        assert violations == [], f"Forbidden Ollama/AnalystService references found: {violations}"


class TestDeterministicPrimaryAndBlockedOllama:
    @pytest.mark.parametrize("video_sim,text_sim,expected_verdict,expected_rule", [
        (0.995, 1.0, DecisionVerdict.APPROVE, "RULE_QUALIFIED_APPROVE"),
        (0.965, 1.0, DecisionVerdict.REVIEW, "RULE_PROTECTIVE_REVIEW"),
        (0.90, 1.0, DecisionVerdict.REJECT, "RULE_HARD_REJECT"),
    ])
    def test_verdicts_and_blocked_ollama_module(
        self, isolated_db, sample_job, comp_service, monkeypatch,
        video_sim, text_sim, expected_verdict, expected_rule
    ):
        monkeypatch.setitem(sys.modules, "ollama", None)

        sentinel = "SECRET_TRANSCRIPT_SENTINEL_12345"
        results = _complete_results(
            video_sim=video_sim,
            text_sim=text_sim,
            transcript_a=f"{sentinel} alpha beta gamma delta epsilon",
            transcript_b=f"{sentinel} alpha beta gamma delta epsilon",
        )

        with patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}):
            comp_service._run_ai_analyst(isolated_db, sample_job.id, results)

        dec = isolated_db.query(QADecision).filter(QADecision.job_id == sample_job.id).first()
        assert dec is not None
        assert dec.decided_by == "deterministic_rules_v1"
        assert dec.verdict == expected_verdict
        assert "deterministic_shadow_v1" not in dec.knowledge_snapshot
        assert "deterministic_decision_v1" in dec.knowledge_snapshot

        dd = dec.knowledge_snapshot["deterministic_decision_v1"]
        assert dd["status"] == "completed"
        assert dd["rule_evaluation"]["fired_rule"] == expected_rule
        assert sentinel not in json.dumps(dd)

    def test_incomplete_contract_returns_review(self, isolated_db, sample_job, comp_service):
        results = _complete_results()
        results["audio_result"]["loudness"] = {"comparison": {}}

        with patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}):
            comp_service._run_ai_analyst(isolated_db, sample_job.id, results)

        dec = isolated_db.query(QADecision).filter(QADecision.job_id == sample_job.id).first()
        assert dec.decided_by == "deterministic_rules_v1"
        assert dec.verdict == DecisionVerdict.REVIEW
        dd = dec.knowledge_snapshot["deterministic_decision_v1"]
        assert dd["status"] == "insufficient_metrics"
        assert "has_lufs" in dd["rule_evaluation"]["failed_flags"]

    def test_engine_exception_returns_redacted_review(self, isolated_db, sample_job, comp_service):
        results = _complete_results()

        with patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}), \
             patch(
                 "services.deterministic_decision_engine.DeterministicDecisionEngineV1.evaluate",
                 side_effect=RuntimeError("boom at /Users/secret/path/file.mp4"),
             ):
            comp_service._run_ai_analyst(isolated_db, sample_job.id, results)

        dec = isolated_db.query(QADecision).filter(QADecision.job_id == sample_job.id).first()
        assert dec.decided_by == "deterministic_rules_v1"
        assert dec.verdict == DecisionVerdict.REVIEW
        dd = dec.knowledge_snapshot["deterministic_decision_v1"]
        assert dd["status"] == "error"
        assert "/Users/secret" not in (dd["error"] or "")


class TestAdvisorSeam:
    def test_null_advisor_adds_nothing(self, isolated_db, sample_job, comp_service):
        assert isinstance(get_decision_advisor("none"), NullAdvisor)
        with patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}):
            comp_service._run_ai_analyst(isolated_db, sample_job.id, _complete_results())

        dec = isolated_db.query(QADecision).filter(QADecision.job_id == sample_job.id).first()
        assert dec.verdict == DecisionVerdict.APPROVE
        assert dec.decided_by == "deterministic_rules_v1"
        assert "advisor_v1" not in dec.knowledge_snapshot

    def test_raising_advisor_does_not_change_verdict(self, isolated_db, sample_job, comp_service):
        class BrokenAdvisor:
            def annotate(self, canonical_metrics, decision):
                raise RuntimeError("advisor exploded")

        with patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}), \
             patch("services.decision_advisor.get_decision_advisor", return_value=BrokenAdvisor()):
            comp_service._run_ai_analyst(isolated_db, sample_job.id, _complete_results())

        dec = isolated_db.query(QADecision).filter(QADecision.job_id == sample_job.id).first()
        assert dec.verdict == DecisionVerdict.APPROVE
        assert dec.decided_by == "deterministic_rules_v1"
        assert "advisor_v1" not in dec.knowledge_snapshot

    def test_advisor_returning_verdict_is_advisory_only(self, isolated_db, sample_job, comp_service):
        class OverrideAttemptAdvisor:
            def annotate(self, canonical_metrics, decision):
                return {"verdict": "reject", "note": "advisory comment only"}

        with patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}), \
             patch("services.decision_advisor.get_decision_advisor", return_value=OverrideAttemptAdvisor()):
            comp_service._run_ai_analyst(isolated_db, sample_job.id, _complete_results())

        dec = isolated_db.query(QADecision).filter(QADecision.job_id == sample_job.id).first()
        assert dec.verdict == DecisionVerdict.APPROVE
        assert dec.decided_by == "deterministic_rules_v1"
        assert dec.knowledge_snapshot["advisor_v1"] == {"verdict": "reject", "note": "advisory comment only"}

    def test_run_advisor_advisory_handles_timeout(self):
        import time

        class SlowAdvisor:
            def annotate(self, canonical_metrics, decision):
                time.sleep(5.0)
                return {"note": "late"}

        start = time.monotonic()
        res = run_advisor_advisory(SlowAdvisor(), {}, {}, timeout_seconds=0.3)
        elapsed = time.monotonic() - start
        assert res is None
        assert elapsed < 1.0


class TestLifespanAndSystemInfo:
    def test_lifespan_never_touches_11434_or_ollama(self):
        import main

        async def _run():
            async def _noop_cleaner():
                return None

            with patch("main.verify_git_hooks"), \
                 patch("main.recover_interrupted_jobs", return_value=0), \
                 patch("main.subprocess.Popen") as mock_popen, \
                 patch("main.dev_cleanup_loop", side_effect=_noop_cleaner), \
                 patch("urllib.request.urlopen") as mock_urlopen:
                async with main.lifespan(main.app):
                    pass
                mock_popen.assert_not_called()
                mock_urlopen.assert_not_called()

        asyncio.run(_run())

    def test_system_info_endpoint(self):
        import main

        with patch("main.verify_git_hooks"), \
             patch("main.recover_interrupted_jobs", return_value=0):
            client = TestClient(main.app)
            resp = client.get("/api/v1/system/info")

        assert resp.status_code == 200
        data = resp.json()
        assert data["decision_engine"] == "deterministic_rules_v1"
        assert data["advisor_provider"] == "none"
        assert data["engine_version"] == "1.0.0"
        assert data["git_sha"] is None or (isinstance(data["git_sha"], str) and len(data["git_sha"]) > 0)
        assert "/" not in json.dumps(data)

    def test_system_info_handles_missing_git_returns_none(self):
        import main

        with patch("main.verify_git_hooks"), \
             patch("main.recover_interrupted_jobs", return_value=0), \
             patch("api.v1.system.subprocess.check_output", side_effect=FileNotFoundError("git not found")):
            client = TestClient(main.app)
            resp = client.get("/api/v1/system/info")

        assert resp.status_code == 200
        data = resp.json()
        assert data["decision_engine"] == "deterministic_rules_v1"
        assert data["advisor_provider"] == "none"
        assert data["git_sha"] is None

    def test_settings_loads_temp_dotenv_file_without_validation_error(self, tmp_path, monkeypatch, caplog):
        monkeypatch.delenv("DECISION_ENGINE", raising=False)
        monkeypatch.delenv("DETERMINISTIC_SHADOW_MODE", raising=False)
        monkeypatch.delenv("ADVISOR_PROVIDER", raising=False)

        env_det = tmp_path / ".env.det"
        env_det.write_text(
            "DECISION_ENGINE=deterministic_rules_v1\n"
            "DETERMINISTIC_SHADOW_MODE=true\n"
            "ADVISOR_PROVIDER=none\n",
            encoding="utf-8",
        )
        s1 = Settings(_env_file=str(env_det))
        assert s1.decision_engine == "deterministic_rules_v1"
        assert s1.advisor_provider == "none"

        env_agent = tmp_path / ".env.agent"
        env_agent.write_text(
            "DECISION_ENGINE=agent\n"
            "DETERMINISTIC_SHADOW_MODE=true\n"
            "ADVISOR_PROVIDER=none\n",
            encoding="utf-8",
        )
        with caplog.at_level(logging.WARNING):
            s2 = Settings(_env_file=str(env_agent))
        assert s2.decision_engine == "deterministic_rules_v1"
        assert any("agent removed" in rec.message for rec in caplog.records)


class TestShadowMigrationEquivalents:
    def test_automation_no_speech_music_dominant_none_approves_via_run_ai_analyst(
        self, isolated_db, sample_job, comp_service
    ):
        sample_job.comparison_type = ComparisonType.AUTOMATION
        isolated_db.commit()

        results = _complete_results(words_a=0, words_b=0, transcript_a="", transcript_b="")
        results["audio_result"]["speech_to_text"] = {
            "status": "completed_no_speech",
            "text_similarity": 1.0,
            "is_text_match": True,
            "acceptance_text": "",
            "emission_text": "",
            "is_uncertain": False,
            "comparison": {"word_count_a": 0, "word_count_b": 0, "word_differences": []},
        }
        results["audio_result"]["raw_vad_speech"] = False
        results["audio_result"]["raw_vad_a"] = {"status": "no_speech", "has_speech": False}
        results["audio_result"]["raw_vad_b"] = {"status": "no_speech", "has_speech": False}
        results["audio_result"]["music_dominant"] = None
        results["audio_result"]["music_proportion"] = None

        with patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}):
            comp_service._run_ai_analyst(isolated_db, sample_job.id, results)

        dec = isolated_db.query(QADecision).filter(QADecision.job_id == sample_job.id).first()
        assert dec.verdict == DecisionVerdict.APPROVE
        dd = dec.knowledge_snapshot["deterministic_decision_v1"]
        assert dd["status"] == "completed"
        assert dd["metrics_contract_complete"] is True
        assert dd["rule_evaluation"]["fired_rule"] == "RULE_QUALIFIED_APPROVE"

    def test_full_no_speech_music_dominant_none_insufficient_via_run_ai_analyst(
        self, isolated_db, sample_job, comp_service
    ):
        sample_job.comparison_type = ComparisonType.FULL
        isolated_db.commit()

        results = _complete_results(words_a=0, words_b=0, transcript_a="", transcript_b="")
        results["audio_result"]["speech_to_text"] = {
            "status": "completed_no_speech",
            "text_similarity": 1.0,
            "is_text_match": True,
            "acceptance_text": "",
            "emission_text": "",
            "is_uncertain": False,
            "comparison": {"word_count_a": 0, "word_count_b": 0, "word_differences": []},
        }
        results["audio_result"]["raw_vad_speech"] = False
        results["audio_result"]["raw_vad_a"] = {"status": "no_speech", "has_speech": False}
        results["audio_result"]["raw_vad_b"] = {"status": "no_speech", "has_speech": False}
        results["audio_result"]["music_dominant"] = None
        results["audio_result"]["music_proportion"] = None

        with patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}):
            comp_service._run_ai_analyst(isolated_db, sample_job.id, results)

        dec = isolated_db.query(QADecision).filter(QADecision.job_id == sample_job.id).first()
        assert dec.verdict == DecisionVerdict.REVIEW
        dd = dec.knowledge_snapshot["deterministic_decision_v1"]
        assert dd["status"] == "insufficient_metrics"
        assert dd["metrics_contract_complete"] is False
        assert "has_raw_vad_complete" in dd["rule_evaluation"]["failed_flags"]

    def test_duplicate_input_approves_via_run_ai_analyst(self, isolated_db, sample_job, comp_service):
        sample_job.comparison_type = ComparisonType.AUTOMATION
        isolated_db.commit()

        results = _complete_results()
        results["audio_result"]["is_binary_duplicate"] = True
        results["audio_result"]["similarity_score"] = 1.0
        results["audio_result"]["speech_to_text"] = {
            "status": "skipped",
            "skipped_reason": "DUPLICATE_INPUT: Acceptance and Emission are binary identical files",
            "is_uncertain": False,
        }

        with patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}):
            comp_service._run_ai_analyst(isolated_db, sample_job.id, results)

        dec = isolated_db.query(QADecision).filter(QADecision.job_id == sample_job.id).first()
        assert dec.verdict == DecisionVerdict.APPROVE
        assert dec.knowledge_snapshot["deterministic_decision_v1"]["rule_evaluation"]["fired_rule"] == "RULE_QUALIFIED_APPROVE"

    def test_missing_probe_flags_trigger_insufficient_via_run_ai_analyst(self, isolated_db, sample_job, comp_service):
        results = _complete_results()
        del results["audio_result"]["acc_has_audio"]
        results["audio_result"]["audio_mismatch"] = "false"

        with patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}):
            comp_service._run_ai_analyst(isolated_db, sample_job.id, results)

        dec = isolated_db.query(QADecision).filter(QADecision.job_id == sample_job.id).first()
        assert dec.verdict == DecisionVerdict.REVIEW
        dd = dec.knowledge_snapshot["deterministic_decision_v1"]
        assert dd["status"] == "insufficient_metrics"
        assert dd["metrics_contract_complete"] is False
        assert dec.metrics_snapshot["acc_has_audio"] is None
        assert dec.metrics_snapshot["audio_mismatch"] is None

    def test_strict_json_serialization_in_deterministic_decision_v1(self, isolated_db, sample_job, comp_service):
        with patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}):
            comp_service._run_ai_analyst(isolated_db, sample_job.id, _complete_results())

        dec = isolated_db.query(QADecision).filter(QADecision.job_id == sample_job.id).first()
        dumped = json.dumps(dec.knowledge_snapshot["deterministic_decision_v1"], allow_nan=False)
        assert isinstance(json.loads(dumped), dict)


class TestPersistenceAndE2EFailClosed:
    def test_process_job_deterministic_snapshot_crash_preserves_results_and_saves_review(self, tmp_path):
        db_path = tmp_path / "e2e_process_job.db"
        acc_file = tmp_path / "acc.mp4"
        emi_file = tmp_path / "emi.mp4"
        acc_file.write_bytes(b"fake-acc")
        emi_file.write_bytes(b"fake-emi")

        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(engine)
        E2ESession = sessionmaker(bind=engine)
        setup_db = E2ESession()
        fa = File(
            filename="acc.mp4",
            original_name="acc.mp4",
            file_path=str(acc_file),
            file_type=FileType.ACCEPTANCE,
            file_format=FileFormat.MP4,
            file_size=8,
        )
        fb = File(
            filename="emi.mp4",
            original_name="emi.mp4",
            file_path=str(emi_file),
            file_type=FileType.EMISSION,
            file_format=FileFormat.MP4,
            file_size=8,
        )
        setup_db.add_all([fa, fb])
        setup_db.commit()
        job = ComparisonJob(
            job_name="E2E_ProcessJob_FailClosed",
            client_name="TestClient",
            cradle_id="7777777",
            acceptance_file_id=fa.id,
            emission_file_id=fb.id,
            status=JobStatus.PENDING,
            comparison_type=ComparisonType.VIDEO_ONLY,
            sensitivity_level=SensitivityLevel.AUTOMATION,
        )
        setup_db.add(job)
        setup_db.commit()
        job_id = job.id
        setup_db.close()

        from types import SimpleNamespace

        class _VideoResObj(SimpleNamespace):
            def get(self, key, default=None):
                return getattr(self, key, default)

        mock_vp = MagicMock()
        mock_vp.process_comparison.return_value = _VideoResObj(
            error_message=None,
            overall_similarity=0.996,
            frames_with_differences=0,
            total_frames=100,
            fps=25.0,
            duration_seconds=4.0,
            duration_difference=0.0,
            is_arpp_slate=False,
            difference_timestamps=[],
            differences=[],
            frame_differences=[],
            ssim_score=0.996,
            pixel_diff_percentage=0.0,
            resolution="1920x1080",
            acceptance_resolution="1920x1080",
            emission_resolution="1920x1080",
            motion_score=0.0,
            alignment_offset=0.0,
            acc_slate_offset=0.0,
            emi_slate_offset=0.0,
            processing_time=0.5,
            is_match=True,
            cradle_report={},
            cradle_verdict="approve",
            metadata={},
        )

        with patch("services.comparison_service.SessionLocal", side_effect=lambda: E2ESession()), \
             patch("services.comparison_service.VideoProcessor", return_value=mock_vp), \
             patch("services.comparison_service.AudioProcessor"), \
             patch(
                 "services.comparison_service.ComparisonService._build_knowledge_snapshot",
                 side_effect=RuntimeError("e2e snapshot crash /Users/secret/e2e.mp4"),
             ):
            ComparisonService().process_job(job_id)

        verify_engine = create_engine(f"sqlite:///{db_path}", echo=False)
        VerifySession = sessionmaker(bind=verify_engine)
        verify_db = VerifySession()
        try:
            saved_job = verify_db.query(ComparisonJob).filter(ComparisonJob.id == job_id).first()
            assert saved_job.status == JobStatus.COMPLETED
            assert saved_job.progress == 100.0
            assert verify_db.query(ComparisonResult).filter(ComparisonResult.job_id == job_id).first() is not None
            assert verify_db.query(VideoComparisonResult).filter(VideoComparisonResult.job_id == job_id).first() is not None
            dec = verify_db.query(QADecision).filter(QADecision.job_id == job_id).first()
            assert dec.verdict == DecisionVerdict.REVIEW
            assert dec.decided_by == "deterministic_rules_v1"
            assert "/Users/secret/e2e.mp4" not in (dec.reasoning or "")
            assert dec.knowledge_snapshot["deterministic_decision_v1"]["status"] == "error"
        finally:
            verify_db.close()
            verify_engine.dispose()
            engine.dispose()
