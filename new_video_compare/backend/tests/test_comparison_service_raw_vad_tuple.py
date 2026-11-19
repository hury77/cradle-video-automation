"""
Regression tests for ComparisonService Raw VAD check (Tuple import fix)
and static undefined-name check on services/.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
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
    File,
    FileFormat,
    FileType,
    JobStatus,
    SensitivityLevel,
)
from services.comparison_service import ComparisonService


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


@pytest.mark.parametrize(
    "vad_payload,expected_complete,expected_inconclusive,expected_speech,expected_status",
    [
        (
            {"status": "speech_detected", "has_speech": True, "speech_duration_s": 5.0, "segments_count": 2, "error": None},
            True,
            False,
            True,
            "speech_detected",
        ),
        (
            {"status": "no_speech", "has_speech": False, "speech_duration_s": 0.0, "segments_count": 0, "error": None},
            True,
            False,
            False,
            "no_speech",
        ),
        (
            {"status": "error", "has_speech": False, "speech_duration_s": 0.0, "segments_count": 0, "error": "vad_failed"},
            False,
            True,
            False,
            "error",
        ),
        (
            None,
            False,
            True,
            False,
            "uncertain",
        ),
    ],
)
def test_raw_vad_block_full_mode_no_tuple_name_error(
    isolated_db_session,
    tmp_path,
    vad_payload,
    expected_complete,
    expected_inconclusive,
    expected_speech,
    expected_status,
):
    acc_file = tmp_path / "acc.mp4"
    emi_file = tmp_path / "emi.mp4"
    acc_file.write_bytes(b"acc")
    emi_file.write_bytes(b"emi")

    f1 = File(
        filename="acc.mp4",
        original_name="acc.mp4",
        file_path=str(acc_file),
        file_type=FileType.ACCEPTANCE,
        file_format=FileFormat.MP4,
        file_size=3,
    )
    f2 = File(
        filename="emi.mp4",
        original_name="emi.mp4",
        file_path=str(emi_file),
        file_type=FileType.EMISSION,
        file_format=FileFormat.MP4,
        file_size=3,
    )
    isolated_db_session.add_all([f1, f2])
    isolated_db_session.flush()

    job = ComparisonJob(
        id=4201,
        job_name="Raw VAD Tuple Regression",
        acceptance_file_id=f1.id,
        emission_file_id=f2.id,
        comparison_type=ComparisonType.FULL,
        status=JobStatus.PENDING,
        sensitivity_level=SensitivityLevel.MEDIUM,
    )
    isolated_db_session.add(job)
    isolated_db_session.commit()

    captured_results = {}

    def _capture_save(db, job_id, results):
        captured_results["results"] = results

    fake_video_res = SimpleNamespace(
        error_message=None,
        overall_similarity=1.0,
        frames_with_differences=0,
        acceptance_metadata=SimpleNamespace(duration=15.0),
        emission_metadata=SimpleNamespace(duration=15.0),
    )

    with (
        patch("services.comparison_service.SessionLocal", return_value=isolated_db_session),
        patch.object(isolated_db_session, "close"),
        patch("services.comparison_service.VideoProcessor") as mock_vp_cls,
        patch("services.comparison_service.AudioProcessor") as mock_ap_cls,
        patch("services.comparison_service.log_automation_event"),
        patch("services.comparison_service.compare_loudness", return_value={"lufs_difference": 0.1, "has_loudness_differences": False}),
        patch("services.comparison_service.compare_audio_similarity", return_value={"overall_audio_similarity": 0.90}),
        patch("services.comparison_service.compare_spoken_text", return_value={"status": "completed", "text_similarity": 1.0, "is_text_match": True, "comparison": {"word_count_a": 5, "word_count_b": 5}}),
        patch("services.audio_service.get_audio_stream_count", return_value=1),
        patch("services.audio_service.compute_file_sha256", side_effect=["sha_acc", "sha_emi"]),
        patch("services.audio_service.detect_raw_audio_speech", return_value=vad_payload),
    ):
        mock_vp_cls.return_value.process_comparison.return_value = fake_video_res
        mock_ap_cls.return_value.compare_audio_files.return_value = {"similarity_score": 0.90}

        service = ComparisonService()
        with (
            patch.object(service, "_save_results", side_effect=_capture_save),
            patch.object(service, "_run_ai_analyst"),
        ):
            service.process_job(job.id)

    audio_res = captured_results["results"]["audio_result"]
    assert audio_res.get("raw_vad_error") is None
    assert audio_res["raw_vad_metrics_complete"] is expected_complete
    assert audio_res["raw_vad_inconclusive"] is expected_inconclusive
    assert audio_res["raw_vad_speech"] is expected_speech
    assert audio_res["raw_vad_status"] == expected_status


def test_pyflakes_no_undefined_names_in_services():
    if importlib.util.find_spec("pyflakes") is None:
        pytest.skip("pyflakes is not installed in this environment")

    proc = subprocess.run(
        [sys.executable, "-m", "pyflakes", str(backend_dir / "services")],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    undefined = [line for line in output.splitlines() if "undefined name" in line]
    assert undefined == [], f"Undefined names found by pyflakes: {undefined}"
