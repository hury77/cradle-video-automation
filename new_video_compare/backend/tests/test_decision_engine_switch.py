"""
Tests for DECISION_ENGINE switch ('agent' vs 'deterministic_rules_v1'):
1. config.Settings validation (default='agent', valid='deterministic_rules_v1', invalid->'agent'+warning)
2. comparison_service._run_ai_analyst:
   - 'agent' preserves identical behavior (including shadow mode)
   - 'deterministic_rules_v1' never calls get_analyst/Ollama, maps approve/review/reject,
     handles incomplete contract -> REVIEW + failed_flags, handles engine exception -> anonymized REVIEW,
     sets decided_by='deterministic_rules_v1' and knowledge_snapshot['deterministic_decision_v1'] (no shadow),
     never leaks transcript sentinel text into deterministic_decision_v1
3. main.lifespan skips Ollama check/startup when decision_engine='deterministic_rules_v1'
4. AnalystService._load_knowledge_context treats deterministic_rules_v1 like agent
"""

import asyncio
import copy
import json
import logging
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from config import Settings, settings
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
from services.analyst_service import AnalystService
from services.comparison_service import ComparisonService


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


def _complete_results(video_sim=0.995, text_sim=1.0, words_a=6, words_b=6, transcript_a="Hello world one two three four", transcript_b="Hello world one two three four"):
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


class TestConfigDecisionEngine:
    def test_default_is_agent(self, monkeypatch):
        monkeypatch.delenv("DECISION_ENGINE", raising=False)
        s = Settings(_env_file=None)
        assert s.decision_engine == "agent"

    def test_valid_deterministic_rules_v1(self, monkeypatch):
        monkeypatch.setenv("DECISION_ENGINE", "deterministic_rules_v1")
        s = Settings(_env_file=None)
        assert s.decision_engine == "deterministic_rules_v1"

    def test_invalid_falls_back_to_agent_with_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("DECISION_ENGINE", "unknown_engine_xyz")
        with caplog.at_level(logging.WARNING):
            s = Settings(_env_file=None)
        assert s.decision_engine == "agent"
        assert any("Invalid DECISION_ENGINE" in rec.message for rec in caplog.records)


class TestPrimarySwitchComparisonService:
    def test_agent_mode_preserves_behavior_and_shadow(self, isolated_db, sample_job, comp_service, monkeypatch):
        monkeypatch.setattr(settings, "decision_engine", "agent")
        monkeypatch.setattr(settings, "deterministic_shadow_mode", True)

        mock_analyst = MagicMock()
        mock_analyst.analyze_job_results.return_value = {
            "verdict": "approve",
            "confidence": 0.94,
            "reasoning": "Agent approves",
        }

        with patch("services.analyst_service.get_analyst", return_value=mock_analyst), \
             patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}):
            comp_service._run_ai_analyst(isolated_db, sample_job.id, _complete_results())

        mock_analyst.analyze_job_results.assert_called_once()
        dec = isolated_db.query(QADecision).filter(QADecision.job_id == sample_job.id).first()
        assert dec.decided_by == "agent"
        assert dec.verdict == DecisionVerdict.APPROVE
        assert "deterministic_shadow_v1" in dec.knowledge_snapshot
        assert "deterministic_decision_v1" not in dec.knowledge_snapshot

    @pytest.mark.parametrize("video_sim,text_sim,expected_verdict,expected_rule", [
        (0.995, 1.0, DecisionVerdict.APPROVE, "RULE_QUALIFIED_APPROVE"),
        (0.965, 1.0, DecisionVerdict.REVIEW, "RULE_PROTECTIVE_REVIEW"),
        (0.90, 1.0, DecisionVerdict.REJECT, "RULE_HARD_REJECT"),
    ])
    def test_deterministic_primary_verdicts_and_no_ollama(
        self, isolated_db, sample_job, comp_service, monkeypatch,
        video_sim, text_sim, expected_verdict, expected_rule
    ):
        monkeypatch.setattr(settings, "decision_engine", "deterministic_rules_v1")
        monkeypatch.setattr(settings, "deterministic_shadow_mode", True)

        sentinel = "SECRET_TRANSCRIPT_SENTINEL_12345"
        results = _complete_results(
            video_sim=video_sim,
            text_sim=text_sim,
            transcript_a=f"{sentinel} alpha beta gamma delta epsilon",
            transcript_b=f"{sentinel} alpha beta gamma delta epsilon",
        )

        mock_analyst = MagicMock()
        with patch("services.analyst_service.get_analyst", return_value=mock_analyst), \
             patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}):
            comp_service._run_ai_analyst(isolated_db, sample_job.id, results)

        mock_analyst.analyze_job_results.assert_not_called()

        dec = isolated_db.query(QADecision).filter(QADecision.job_id == sample_job.id).first()
        assert dec is not None
        assert dec.decided_by == "deterministic_rules_v1"
        assert dec.verdict == expected_verdict
        assert dec.reasoning
        assert dec.ai_reasoning == dec.reasoning
        assert "deterministic_shadow_v1" not in dec.knowledge_snapshot
        assert "deterministic_decision_v1" in dec.knowledge_snapshot

        dd = dec.knowledge_snapshot["deterministic_decision_v1"]
        assert dd["status"] == "completed"
        assert dd["decided_by"] == "deterministic_rules_v1"
        assert dd["metrics_contract_complete"] is True
        assert dd["rule_evaluation"]["fired_rule"] == expected_rule
        assert sentinel not in json.dumps(dd)

    def test_deterministic_incomplete_contract_returns_review(self, isolated_db, sample_job, comp_service, monkeypatch):
        monkeypatch.setattr(settings, "decision_engine", "deterministic_rules_v1")
        results = _complete_results()
        results["audio_result"]["loudness"] = {"comparison": {}}  # missing LUFS -> fail-closed

        mock_analyst = MagicMock()
        with patch("services.analyst_service.get_analyst", return_value=mock_analyst), \
             patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}):
            comp_service._run_ai_analyst(isolated_db, sample_job.id, results)

        mock_analyst.analyze_job_results.assert_not_called()
        dec = isolated_db.query(QADecision).filter(QADecision.job_id == sample_job.id).first()
        assert dec.decided_by == "deterministic_rules_v1"
        assert dec.verdict == DecisionVerdict.REVIEW
        dd = dec.knowledge_snapshot["deterministic_decision_v1"]
        assert dd["status"] == "insufficient_metrics"
        assert dd["metrics_contract_complete"] is False
        assert "has_lufs" in dd["rule_evaluation"]["failed_flags"]

    def test_deterministic_engine_exception_returns_redacted_review(self, isolated_db, sample_job, comp_service, monkeypatch):
        monkeypatch.setattr(settings, "decision_engine", "deterministic_rules_v1")
        results = _complete_results()

        mock_analyst = MagicMock()
        with patch("services.analyst_service.get_analyst", return_value=mock_analyst), \
             patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}), \
             patch(
                 "services.deterministic_decision_engine.DeterministicDecisionEngineV1.evaluate",
                 side_effect=RuntimeError("boom at /Users/secret/path/file.mp4"),
             ):
            comp_service._run_ai_analyst(isolated_db, sample_job.id, results)

        mock_analyst.analyze_job_results.assert_not_called()
        dec = isolated_db.query(QADecision).filter(QADecision.job_id == sample_job.id).first()
        assert dec.decided_by == "deterministic_rules_v1"
        assert dec.verdict == DecisionVerdict.REVIEW
        dd = dec.knowledge_snapshot["deterministic_decision_v1"]
        assert dd["status"] == "error"
        assert "/Users/secret" not in (dd["error"] or "")
        assert "/Users/secret" not in (dec.reasoning or "")


class TestLifespanAndKB:
    def test_lifespan_skips_ollama_in_deterministic_mode(self, monkeypatch):
        import main
        monkeypatch.setattr(settings, "decision_engine", "deterministic_rules_v1")

        async def _run():
            async def _noop_cleaner():
                return None

            with patch("main.verify_git_hooks"), \
                 patch("main.recover_interrupted_jobs", return_value=0), \
                 patch("main.check_ollama_running") as mock_check, \
                 patch("main.subprocess.Popen") as mock_popen, \
                 patch("main.dev_cleanup_loop", side_effect=_noop_cleaner):
                async with main.lifespan(main.app):
                    pass
                mock_check.assert_not_called()
                mock_popen.assert_not_called()

        asyncio.run(_run())

    def test_analyst_kb_loads_deterministic_decisions_with_agent(self, isolated_db, sample_job):
        d1 = QADecision(
            job_id=sample_job.id,
            verdict=DecisionVerdict.APPROVE,
            reasoning="Det approve",
            client_name=sample_job.client_name,
            cradle_id=sample_job.cradle_id,
            metrics_snapshot={"overall_similarity": 0.99},
            decided_by="deterministic_rules_v1",
        )
        isolated_db.add(d1)
        isolated_db.commit()

        ctx = AnalystService()._load_historical_context(
            isolated_db, sample_job.client_name, current_job_id=sample_job.id + 1
        )
        assert len(ctx) == 1
        assert ctx[0]["decided_by"] == "deterministic_rules_v1"


class TestPersistenceFailClosedAndParity:
    def _create_file_db_job(self, db_path: Path):
        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
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
        db.add_all([fa, fb])
        db.commit()
        job = ComparisonJob(
            job_name="Persist_Test_Job",
            client_name="TestClient",
            cradle_id="8888888",
            acceptance_file_id=fa.id,
            emission_file_id=fb.id,
            status=JobStatus.COMPLETED,
            comparison_type=ComparisonType.FULL,
            sensitivity_level=SensitivityLevel.AUTOMATION,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return engine, SessionLocal, db, job

    def test_deterministic_persists_to_new_sqlite_session(self, tmp_path, comp_service, monkeypatch):
        monkeypatch.setattr(settings, "decision_engine", "deterministic_rules_v1")
        db_path = tmp_path / "persist_switch.db"
        engine, SessionLocal, db, job = self._create_file_db_job(db_path)

        job_id = job.id
        try:
            with patch("services.comparison_service.ComparisonService._build_knowledge_snapshot", return_value={"job_meta": {}}):
                comp_service._run_ai_analyst(db, job_id, _complete_results())
        finally:
            db.close()

        # Read back from a brand-new session/engine on the same SQLite file
        verify_engine = create_engine(f"sqlite:///{db_path}", echo=False)
        VerifySession = sessionmaker(bind=verify_engine)
        verify_db = VerifySession()
        try:
            dec = verify_db.query(QADecision).filter(QADecision.job_id == job_id).first()
            assert dec is not None
            assert dec.decided_by == "deterministic_rules_v1"
            assert dec.verdict == DecisionVerdict.APPROVE
            assert "deterministic_decision_v1" in dec.knowledge_snapshot
            assert dec.knowledge_snapshot["deterministic_decision_v1"]["status"] == "completed"
        finally:
            verify_db.close()
            verify_engine.dispose()
            engine.dispose()

    def test_deterministic_outer_exception_persists_review_in_new_session(self, tmp_path, comp_service, monkeypatch):
        monkeypatch.setattr(settings, "decision_engine", "deterministic_rules_v1")
        db_path = tmp_path / "fail_closed_outer.db"
        engine, SessionLocal, db, job = self._create_file_db_job(db_path)

        job_id = job.id
        try:
            with patch(
                "services.comparison_service.ComparisonService._build_knowledge_snapshot",
                side_effect=RuntimeError("snapshot crash /Users/secret/path/file.mp4"),
            ):
                comp_service._run_ai_analyst(db, job_id, _complete_results())
        finally:
            db.close()

        verify_engine = create_engine(f"sqlite:///{db_path}", echo=False)
        VerifySession = sessionmaker(bind=verify_engine)
        verify_db = VerifySession()
        try:
            dec = verify_db.query(QADecision).filter(QADecision.job_id == job_id).first()
            assert dec is not None
            assert dec.decided_by == "deterministic_rules_v1"
            assert dec.verdict == DecisionVerdict.REVIEW
            assert "Błąd systemu decyzyjnego" in (dec.reasoning or "")
            assert "/Users/secret/path" not in (dec.reasoning or "")
            dd = dec.knowledge_snapshot["deterministic_decision_v1"]
            assert dd["status"] == "error"
            assert dd["verdict"] == "review"
            assert dd["error"] is not None
            assert "/Users/secret/path" not in dd["error"]
        finally:
            verify_db.close()
            verify_engine.dispose()
            engine.dispose()

    def test_build_ai_metrics_agent_parity_with_origin_dev(self, monkeypatch):
        repo_root = Path(__file__).resolve().parents[3]
        src_origin = subprocess.check_output(
            ["git", "show", "origin/dev:new_video_compare/backend/services/comparison_service.py"],
            cwd=repo_root,
            text=True,
        )
        # Load origin/dev ComparisonService._build_ai_metrics in an isolated namespace
        ns = {
            "__name__": "services._origin_dev_comparison_service",
            "__package__": "services",
            "__file__": str(Path(__file__).resolve().parents[1] / "services" / "comparison_service.py"),
        }
        exec(compile(src_origin, "<origin_dev_comparison_service>", "exec"), ns)
        origin_build = ns["ComparisonService"]._build_ai_metrics

        dummy_job = MagicMock(
            id=42,
            job_name="ParityJob",
            client_name="TestClient",
            comparison_type=ComparisonType.AUTOMATION,
        )

        # 1. Silent audio
        silent_res = copy.deepcopy(_complete_results())
        silent_res["audio_result"]["loudness"] = {
            "acceptance": {"integrated_lufs": None},
            "emission": {"integrated_lufs": None},
            "comparison": {"lufs_difference": 0.0, "peak_difference_db": 0.0, "both_silent": True, "one_side_silent": False},
            "has_loudness_differences": False,
        }
        # 2. Binary duplicate
        dup_res = copy.deepcopy(_complete_results())
        dup_res["audio_result"]["is_binary_duplicate"] = True
        dup_res["audio_result"]["speech_to_text"] = {
            "status": "skipped",
            "skipped_reason": "DUPLICATE_INPUT: identical",
            "is_uncertain": False,
        }
        # 3. No-speech
        nospeech_res = copy.deepcopy(_complete_results(words_a=0, words_b=0, transcript_a="", transcript_b=""))
        nospeech_res["audio_result"]["speech_to_text"]["status"] = "completed_no_speech"
        nospeech_res["audio_result"]["raw_vad_speech"] = False
        # 4. Normal VO
        vo_res = _complete_results()

        cases = [silent_res, dup_res, nospeech_res, vo_res]

        # Case A: DECISION_ENGINE=agent, DETERMINISTIC_SHADOW_MODE=false -> 100% identical
        monkeypatch.setattr(settings, "decision_engine", "agent")
        monkeypatch.setattr(settings, "deterministic_shadow_mode", False)
        monkeypatch.setenv("DETERMINISTIC_SHADOW_MODE", "false")
        ns["settings"].deterministic_shadow_mode = False

        for res in cases:
            assert ComparisonService._build_ai_metrics(dummy_job, res) == origin_build(dummy_job, res)

        # Case B: DECISION_ENGINE=agent, DETERMINISTIC_SHADOW_MODE=true -> identical except both_silent/one_side_silent
        monkeypatch.setattr(settings, "deterministic_shadow_mode", True)
        monkeypatch.setenv("DETERMINISTIC_SHADOW_MODE", "true")
        ns["settings"].deterministic_shadow_mode = True

        for res in cases:
            cur = ComparisonService._build_ai_metrics(dummy_job, res)
            old = origin_build(dummy_job, res)
            cur_norm = copy.deepcopy(cur)
            if isinstance(cur_norm.get("audio_loudness"), dict):
                cur_norm["audio_loudness"].pop("both_silent", None)
                cur_norm["audio_loudness"].pop("one_side_silent", None)
            assert cur_norm == old

    def test_process_job_deterministic_snapshot_crash_preserves_results_and_saves_review(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(settings, "decision_engine", "deterministic_rules_v1")
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
            svc = ComparisonService()
            svc.process_job(job_id)

        # Verify from a brand-new session/engine that job results survived AND fallback REVIEW was saved
        verify_engine = create_engine(f"sqlite:///{db_path}", echo=False)
        VerifySession = sessionmaker(bind=verify_engine)
        verify_db = VerifySession()
        try:
            saved_job = verify_db.query(ComparisonJob).filter(ComparisonJob.id == job_id).first()
            assert saved_job is not None
            assert saved_job.status == JobStatus.COMPLETED
            assert saved_job.progress == 100.0

            comp_res = verify_db.query(ComparisonResult).filter(ComparisonResult.job_id == job_id).first()
            vid_res = verify_db.query(VideoComparisonResult).filter(VideoComparisonResult.job_id == job_id).first()
            assert comp_res is not None
            assert vid_res is not None

            dec = verify_db.query(QADecision).filter(QADecision.job_id == job_id).first()
            assert dec is not None
            assert dec.verdict == DecisionVerdict.REVIEW
            assert dec.decided_by == "deterministic_rules_v1"
            assert "Błąd systemu decyzyjnego" in (dec.reasoning or "")
            assert "/Users/secret/e2e.mp4" not in (dec.reasoning or "")
            dd = dec.knowledge_snapshot["deterministic_decision_v1"]
            assert dd["status"] == "error"
            assert dd["verdict"] == "review"
        finally:
            verify_db.close()
            verify_engine.dispose()
            engine.dispose()
