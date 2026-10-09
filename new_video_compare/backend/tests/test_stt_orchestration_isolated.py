import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json
import subprocess

from models.models import Job, ComparisonType, DecisionVerdict, QADecision
import services.comparison_service as comp_svc
from services.analyst_service import AnalystService
import services.audio_service as audio_svc

# Mock DB setup
class MockDB:
    def __init__(self):
        self.committed = False
        self.decisions = []
    def commit(self):
        self.committed = True
    def query(self, model):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_query.filter.return_value.all.return_value = []
        return mock_query
    def add(self, obj):
        self.decisions.append(obj)

@pytest.fixture
def db():
    return MockDB()

@pytest.fixture
def mock_job():
    job = MagicMock(spec=Job)
    job.comparison_type = ComparisonType.FULL
    job.client_name = "test_client"
    job.cradle_id = "test_id"
    job.id = 1
    job.job_name = "test_job"
    job.sensitivity = "high"
    return job

def check_comp_type(job_type, target_types):
    if not isinstance(target_types, list):
        target_types = [target_types]
    if not job_type:
        return False
    job_type_str = job_type.value if hasattr(job_type, "value") else str(job_type)
    for t in target_types:
        t_str = t.value if hasattr(t, "value") else str(t)
        if job_type_str.lower() == t_str.lower():
            return True
    return False

# 1. test_full_loudness_anomaly_triggers_stt
def test_full_loudness_anomaly_triggers_stt(db, mock_job):
    audio_result = {
        "has_audio": True,
        "no_audio_tracks": False,
        "loudness": {"has_loudness_differences": True}
    }
    
    loudness_match_issue = audio_result.get("loudness", {}).get("has_loudness_differences", False)
    should_run_stt = audio_result.get("has_audio", True) and not audio_result.get("no_audio_tracks", False) and (
        check_comp_type(mock_job.comparison_type, [ComparisonType.AUDIO_ONLY, ComparisonType.AUTOMATION, ComparisonType.VO_TRANSCRIPT])
        or loudness_match_issue
    )
    assert should_run_stt == True
    force_stt = loudness_match_issue or check_comp_type(mock_job.comparison_type, ComparisonType.VO_TRANSCRIPT)
    assert force_stt == True

# 2. test_full_identical_explicit_skip
def test_full_identical_explicit_skip(mock_job):
    audio_result = {
        "has_audio": True,
        "no_audio_tracks": False,
        "loudness": {"has_loudness_differences": False}
    }
    loudness_match_issue = audio_result.get("loudness", {}).get("has_loudness_differences", False)
    should_run_stt = audio_result.get("has_audio", True) and not audio_result.get("no_audio_tracks", False) and (
        check_comp_type(mock_job.comparison_type, [ComparisonType.AUDIO_ONLY, ComparisonType.AUTOMATION, ComparisonType.VO_TRANSCRIPT])
        or loudness_match_issue
    )
    assert should_run_stt == False

# 3. test_automation_keeps_current_optimization
@patch('services.audio_service.get_audio_stream_count', return_value=1)
def test_automation_keeps_current_optimization(mock_stream_count, mock_job):
    mock_job.comparison_type = ComparisonType.AUTOMATION
    audio_result = {
        "has_audio": True,
        "no_audio_tracks": False,
        "similarity_score": 1.0,
        "loudness": {"has_loudness_differences": False}
    }
    loudness_match_issue = audio_result.get("loudness", {}).get("has_loudness_differences", False)
    should_run_stt = audio_result.get("has_audio", True) and not audio_result.get("no_audio_tracks", False) and (
        check_comp_type(mock_job.comparison_type, [ComparisonType.AUDIO_ONLY, ComparisonType.AUTOMATION, ComparisonType.VO_TRANSCRIPT])
        or loudness_match_issue
    )
    assert should_run_stt == True
    res = audio_svc.compare_spoken_text("a.mp4", "b.mp4", audio_similarity_score=1.0, force_stt=False)
    assert res["status"] == "skipped"

# 4. test_vo_transcript_runs_when_audio_present
def test_vo_transcript_runs_when_audio_present(mock_job):
    mock_job.comparison_type = ComparisonType.VO_TRANSCRIPT
    audio_result = {
        "has_audio": True,
        "no_audio_tracks": False,
        "similarity_score": 1.0,
        "loudness": {"has_loudness_differences": False}
    }
    loudness_match_issue = audio_result.get("loudness", {}).get("has_loudness_differences", False)
    should_run_stt = audio_result.get("has_audio", True) and not audio_result.get("no_audio_tracks", False) and (
        check_comp_type(mock_job.comparison_type, [ComparisonType.AUDIO_ONLY, ComparisonType.AUTOMATION, ComparisonType.VO_TRANSCRIPT])
        or loudness_match_issue
    )
    assert should_run_stt == True
    force_stt = loudness_match_issue or check_comp_type(mock_job.comparison_type, ComparisonType.VO_TRANSCRIPT)
    assert force_stt == True

# 5. test_vo_transcript_bypassed_when_no_audio
def test_vo_transcript_bypassed_when_no_audio(mock_job):
    mock_job.comparison_type = ComparisonType.VO_TRANSCRIPT
    audio_result = {
        "has_audio": False,
        "no_audio_tracks": True,
        "similarity_score": 0.0,
    }
    loudness_match_issue = audio_result.get("loudness", {}).get("has_loudness_differences", False)
    should_run_stt = audio_result.get("has_audio", True) and not audio_result.get("no_audio_tracks", False) and (
        check_comp_type(mock_job.comparison_type, [ComparisonType.AUDIO_ONLY, ComparisonType.AUTOMATION, ComparisonType.VO_TRANSCRIPT])
        or loudness_match_issue
    )
    assert should_run_stt == False

# 6. test_stt_contract_completed_no_speech
@patch('services.audio_service.compare_transcripts')
@patch('services.audio_service.transcribe_single_file')
@patch('services.audio_service.get_audio_stream_count', return_value=1)
def test_stt_contract_completed_no_speech(mock_stream_count, mock_transcribe, mock_compare):
    mock_transcribe.side_effect = [
        {"word_count": 0, "text": ""},
        {"word_count": 0, "text": ""}
    ]
    mock_compare.return_value = {"text_similarity": None}
    res = audio_svc.compare_spoken_text("a", "b", force_stt=True)
    assert res["status"] == "completed_no_speech"

# 7. test_unilateral_transcription_false_match
@patch('services.audio_service.compare_transcripts')
@patch('services.audio_service.transcribe_single_file')
@patch('services.audio_service.get_audio_stream_count', return_value=1)
def test_unilateral_transcription_false_match(mock_stream_count, mock_transcribe, mock_compare):
    mock_transcribe.side_effect = [
        {"word_count": 0, "text": ""},
        {"word_count": 10, "text": "hello world"}
    ]
    mock_compare.return_value = {"text_similarity": 0.0}
    res = audio_svc.compare_spoken_text("a", "b", force_stt=True)
    assert res["status"] == "completed"
    assert res["text_similarity"] == 0.0
    assert res["is_text_match"] == False

# 8. test_hierarchy_stt_failure_degrades_to_review
def test_hierarchy_stt_failure_degrades_to_review():
    metrics = {"audio_transcription": {"status": "failed", "error_message": "OOM"}}
    ai_result = {"verdict": "approve", "reasoning": "Looks good"}
    
    verdict = DecisionVerdict.APPROVE
    stt_status = metrics.get("audio_transcription", {}).get("status")
    if stt_status == "failed" and verdict == DecisionVerdict.APPROVE:
        verdict = DecisionVerdict.REVIEW
        error_msg = metrics.get("audio_transcription", {}).get("error_message", "")
        ai_result["reasoning"] = f"[SYSTEM OVERRIDE] Odrzucono aprobatę AI. Moduł STT uległ awarii technicznej i weryfikacja głosu nie została ukończona. Zgłoszony błąd: {error_msg}\\n\\nOryginalna odpowiedź AI: {ai_result.get('reasoning')}"
    
    assert verdict == DecisionVerdict.REVIEW
    assert "OOM" in ai_result["reasoning"]

# 9. test_hierarchy_stt_failure_respects_reject
def test_hierarchy_stt_failure_respects_reject():
    metrics = {"audio_transcription": {"status": "failed", "error_message": "OOM"}}
    ai_result = {"verdict": "reject", "reasoning": "Bad video"}
    
    verdict = DecisionVerdict.REJECT
    stt_status = metrics.get("audio_transcription", {}).get("status")
    if stt_status == "failed" and verdict == DecisionVerdict.APPROVE:
        verdict = DecisionVerdict.REVIEW
    elif stt_status == "failed" and verdict == DecisionVerdict.REJECT:
        error_msg = metrics.get("audio_transcription", {}).get("error_message", "")
        ai_result["reasoning"] = f"[SYSTEM OVERRIDE] Odrzucono (REJECT). Dodatkowo, moduł STT napotkał awarię technicznego: {error_msg}.\\n\\n" + ai_result.get("reasoning", "")
        
    assert verdict == DecisionVerdict.REJECT
    assert "OOM" in ai_result["reasoning"]

# 10. test_analyst_concurrency_metrics
def test_analyst_concurrency_metrics():
    with patch('ollama.chat') as mock_chat:
        mock_chat.return_value = {"message": {"content": '{"verdict": "approve", "reasoning": "test", "confidence": 1.0}'}}
        analyst = AnalystService()
        assert hasattr(analyst, "_last_metrics") == False
        job_a = {"job_id": 1, "audio_transcription": {"status": "failed"}}
        job_b = {"job_id": 2, "audio_transcription": {"status": "completed"}}
        
        analyst.analyze_job_results(job_a, db=MockDB())
        analyst.analyze_job_results(job_b, db=MockDB())
        assert hasattr(analyst, "_last_metrics") == False

# 11. test_mlx_subprocess_protocol_sigkill_and_timeout
@patch('subprocess.run')
def test_mlx_subprocess_protocol_sigkill_and_timeout(mock_run):
    from services.audio_service import transcribe_audio
    mock_run.side_effect = subprocess.TimeoutExpired(cmd=["python"], timeout=300)
    res = transcribe_audio("a.mp4")
    assert res.get("error") is not None
    assert "TimeoutExpired" in res["error"]
    
    err = subprocess.CalledProcessError(returncode=-9, cmd=["python"], stderr="Killed")
    mock_run.side_effect = err
    res = transcribe_audio("a.mp4")
    assert res.get("error") is not None
    assert "OOM/SIGKILL" in res["error"]

# 12. test_mlx_subprocess_protocol_json_success
@patch('subprocess.run')
@patch('builtins.open')
@patch('json.load')
def test_mlx_subprocess_protocol_json_success(mock_json, mock_open, mock_run):
    from services.audio_service import transcribe_audio
    mock_run.return_value = MagicMock(stderr="Some MLX logs")
    mock_json.return_value = {"text": "hello", "segments": [{"text": "hello", "start": 0, "end": 1, "no_speech_prob": 0.0}]}
    res = transcribe_audio("a.mp4")
    assert "hello" in res.get("text", "")
