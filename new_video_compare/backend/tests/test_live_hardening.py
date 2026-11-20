"""
Regression tests for live hardening:
1. Global max_concurrent_jobs limit (default=1, non-blocking waiting, release on error).
2. Startup recovery of interrupted PROCESSING/PENDING jobs on isolated SQLite.
"""

import asyncio
import sys
import threading
import time
from datetime import datetime, timezone
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
    ComparisonType,
    File,
    FileFormat,
    FileType,
    JobStatus,
    SensitivityLevel,
)
import services.comparison_service as comparison_service
from main import app, lifespan, recover_interrupted_jobs


@pytest.fixture
def isolated_db_session_factory():
    db_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(db_engine)
    Session = sessionmaker(bind=db_engine)
    try:
        yield Session
    finally:
        db_engine.dispose()


def test_default_max_concurrent_jobs_is_one(monkeypatch):
    monkeypatch.delenv("MAX_CONCURRENT_JOBS", raising=False)
    fresh = Settings(_env_file=None)
    assert fresh.max_concurrent_jobs == 1


def test_job_concurrency_limit_serializes_two_jobs():
    comparison_service.reset_job_concurrency_limiter()
    guard = threading.Lock()
    active = 0
    max_active = 0
    started_order = []

    def _fake_process_job(self, job_id: int):
        nonlocal active, max_active
        with guard:
            active += 1
            if active > max_active:
                max_active = active
            started_order.append(job_id)
        try:
            time.sleep(0.05)
            return {"job_id": job_id, "status": "completed"}
        finally:
            with guard:
                active -= 1

    with (
        patch.object(settings, "max_concurrent_jobs", 1),
        patch.object(comparison_service, "VideoProcessor"),
        patch.object(comparison_service, "AudioProcessor"),
        patch.object(comparison_service.ComparisonService, "process_job", _fake_process_job),
    ):
        async def _run_two():
            return await asyncio.gather(
                comparison_service.process_comparison_job(101),
                comparison_service.process_comparison_job(102),
            )

        res = asyncio.run(_run_two())

    assert max_active == 1
    assert len(started_order) == 2
    assert {r["job_id"] for r in res} == {101, 102}


def test_job_concurrency_limit_releases_on_exception_and_cancellation():
    comparison_service.reset_job_concurrency_limiter()

    def _failing_then_succeeding(self, job_id: int):
        if job_id == 201:
            raise RuntimeError("simulated job failure")
        if job_id == 202:
            raise asyncio.CancelledError("simulated cancellation")
        return {"job_id": job_id, "status": "completed"}

    with (
        patch.object(settings, "max_concurrent_jobs", 1),
        patch.object(comparison_service, "VideoProcessor"),
        patch.object(comparison_service, "AudioProcessor"),
        patch.object(comparison_service.ComparisonService, "process_job", _failing_then_succeeding),
    ):
        with pytest.raises(RuntimeError, match="simulated job failure"):
            asyncio.run(comparison_service.process_comparison_job(201))

        # Slot must be released after exception; subsequent job succeeds
        res = asyncio.run(comparison_service.process_comparison_job(203))
        assert res["status"] == "completed"

        # Slot must also be released after CancelledError / BaseException
        with pytest.raises(BaseException):
            asyncio.run(comparison_service.process_comparison_job(202))

        res2 = asyncio.run(comparison_service.process_comparison_job(204))
        assert res2["status"] == "completed"


def test_recover_interrupted_jobs_on_isolated_sqlite(isolated_db_session_factory):
    session = isolated_db_session_factory()
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
    session.add_all([f1, f2])
    session.flush()

    now = datetime.now(timezone.utc)
    jobs = [
        ComparisonJob(id=1, job_name="J1", acceptance_file_id=f1.id, emission_file_id=f2.id, comparison_type=ComparisonType.FULL, status=JobStatus.PROCESSING, sensitivity_level=SensitivityLevel.MEDIUM),
        ComparisonJob(id=2, job_name="J2", acceptance_file_id=f1.id, emission_file_id=f2.id, comparison_type=ComparisonType.FULL, status=JobStatus.PENDING, sensitivity_level=SensitivityLevel.MEDIUM),
        ComparisonJob(id=3, job_name="J3", acceptance_file_id=f1.id, emission_file_id=f2.id, comparison_type=ComparisonType.FULL, status=JobStatus.COMPLETED, sensitivity_level=SensitivityLevel.MEDIUM, completed_at=now),
        ComparisonJob(id=4, job_name="J4", acceptance_file_id=f1.id, emission_file_id=f2.id, comparison_type=ComparisonType.FULL, status=JobStatus.FAILED, error_message="Original error", sensitivity_level=SensitivityLevel.MEDIUM, completed_at=now),
        ComparisonJob(id=5, job_name="J5", acceptance_file_id=f1.id, emission_file_id=f2.id, comparison_type=ComparisonType.FULL, status=JobStatus.CANCELLED, sensitivity_level=SensitivityLevel.MEDIUM, completed_at=now),
    ]
    session.add_all(jobs)
    session.commit()
    session.close()

    recovered = recover_interrupted_jobs(db_session_factory=isolated_db_session_factory)
    assert recovered == 2

    check_session = isolated_db_session_factory()
    by_id = {j.id: j for j in check_session.query(ComparisonJob).all()}
    assert by_id[1].status == JobStatus.FAILED
    assert by_id[1].error_message == "Interrupted by backend restart"
    assert by_id[1].completed_at is not None

    assert by_id[2].status == JobStatus.FAILED
    assert by_id[2].error_message == "Interrupted by backend restart"
    assert by_id[2].completed_at is not None

    assert by_id[3].status == JobStatus.COMPLETED
    assert by_id[4].status == JobStatus.FAILED
    assert by_id[4].error_message == "Original error"
    assert by_id[5].status == JobStatus.CANCELLED
    check_session.close()

    # Second run should recover 0
    assert recover_interrupted_jobs(db_session_factory=isolated_db_session_factory) == 0


def test_lifespan_continues_when_recovery_fails():
    async def _noop_cleaner():
        return

    with (
        patch("main.verify_git_hooks"),
        patch("main.check_ollama_running", return_value=True),
        patch("main.dev_cleanup_loop", side_effect=_noop_cleaner),
        patch("main.recover_interrupted_jobs", side_effect=RuntimeError("database is locked")),
    ):
        async def _enter_lifespan():
            async with lifespan(app):
                return "started"

        result = asyncio.run(_enter_lifespan())
    assert result == "started"


def test_cancelled_job_while_waiting_in_pending_is_skipped(tmp_path):
    comparison_service.reset_job_concurrency_limiter()
    db_path = tmp_path / "test_cancel.db"
    db_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    Base.metadata.create_all(db_engine)
    SessionLocalTemp = sessionmaker(bind=db_engine)

    session = SessionLocalTemp()
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
    session.add_all([f1, f2])
    session.flush()

    j1 = ComparisonJob(
        id=301,
        job_name="J301",
        acceptance_file_id=f1.id,
        emission_file_id=f2.id,
        comparison_type=ComparisonType.FULL,
        status=JobStatus.PENDING,
        sensitivity_level=SensitivityLevel.MEDIUM,
    )
    j2 = ComparisonJob(
        id=302,
        job_name="J302",
        acceptance_file_id=f1.id,
        emission_file_id=f2.id,
        comparison_type=ComparisonType.FULL,
        status=JobStatus.PENDING,
        sensitivity_level=SensitivityLevel.MEDIUM,
    )
    session.add_all([j1, j2])
    session.commit()
    session.close()

    with (
        patch.object(settings, "max_concurrent_jobs", 1),
        patch.object(comparison_service, "SessionLocal", SessionLocalTemp),
        patch.object(comparison_service, "VideoProcessor") as mock_vp_cls,
        patch.object(comparison_service, "AudioProcessor"),
    ):
        # Job 301 runs and cancels job 302 while 302 is waiting on the semaphore
        def _run_j1_and_cancel_j2(*args, **kwargs):
            s = SessionLocalTemp()
            target = s.query(ComparisonJob).filter(ComparisonJob.id == 302).first()
            target.status = JobStatus.CANCELLED
            s.commit()
            s.close()
            raise RuntimeError("stop_j1_early")

        mock_vp_cls.return_value.process_comparison.side_effect = _run_j1_and_cancel_j2

        # Run 301 (starts first) and 302 (waits, gets cancelled, then acquires semaphore)
        async def _run_both():
            t1 = asyncio.create_task(comparison_service.process_comparison_job(301))
            await asyncio.sleep(0.02)
            t2 = asyncio.create_task(comparison_service.process_comparison_job(302))
            return await asyncio.gather(t1, t2, return_exceptions=True)

        r1, r2 = asyncio.run(_run_both())

    assert isinstance(r1, dict) and r1.get("success") is False
    assert r2 == {"success": False, "job_id": 302, "status": "cancelled", "skipped": True}

    check_s = SessionLocalTemp()
    j2_after = check_s.query(ComparisonJob).filter(ComparisonJob.id == 302).first()
    assert j2_after.status == JobStatus.CANCELLED
    check_s.close()
    db_engine.dispose()
