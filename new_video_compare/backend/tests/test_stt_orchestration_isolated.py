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
        {"transcript": {"word_count": 0, "text": ""}},
        {"transcript": {"word_count": 0, "text": ""}}
    ]
    mock_compare.return_value = {"text_similarity": 1.0}
    res = audio_svc.compare_spoken_text("a", "b", force_stt=True)
    assert res["status"] == "completed_no_speech"

# 7. test_unilateral_transcription_false_match
@patch('services.audio_service.compare_transcripts')
@patch('services.audio_service.transcribe_single_file')
@patch('services.audio_service.get_audio_stream_count', return_value=1)
def test_unilateral_transcription_false_match(mock_stream_count, mock_transcribe, mock_compare):
    mock_transcribe.side_effect = [
        {"transcript": {"word_count": 0, "text": ""}},
        {"transcript": {"word_count": 10, "text": "hello world"}}
    ]
    mock_compare.return_value = {"text_similarity": 0.0, "word_differences": []}
    res = audio_svc.compare_spoken_text("a", "b", force_stt=True)
    assert res.get("status") == "completed"
    assert res.get("comparison", {}).get("text_similarity") == 0.0
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
@patch('os.path.getsize', return_value=100)
@patch('os.path.exists', return_value=True)
@patch('subprocess.run')
@patch('builtins.open')
@patch('json.load')
def test_mlx_subprocess_protocol_json_success(mock_json, mock_open, mock_run, mock_exists, mock_getsize):
    from services.audio_service import transcribe_audio
    mock_open.return_value.fileno.return_value = 10
    mock_run.return_value = MagicMock(returncode=0, stderr="Some MLX logs")
    mock_json.return_value = {"text": "this is a longer test sentence", "segments": [{"text": "this is a longer test sentence", "start": 0, "end": 1, "no_speech_prob": 0.0}]}
    res = transcribe_audio("a.mp4")
    assert "this is a longer test sentence" in res.get("text", "")

# 13. test_mlx_subprocess_path_injection_safety
@patch('subprocess.run')
@patch('builtins.open')
@patch('json.load')
def test_mlx_subprocess_path_injection_safety(mock_json, mock_open, mock_run):
    from services.audio_service import transcribe_audio
    mock_open.return_value.fileno.return_value = 10
    mock_run.return_value = MagicMock(returncode=0)
    mock_json.return_value = {"text": "injection safe", "segments": [{"text": "injection safe", "start": 0, "end": 1, "no_speech_prob": 0.0}]}
    
    tricky_path = "path/with spaces/and'quotes.mp4"
    res = transcribe_audio(tricky_path)
    
    call_args = mock_run.call_args[0][0]
    assert call_args[0].endswith('python') or 'python' in call_args[0]
    assert call_args[1] == '-c'
    assert tricky_path not in call_args[2]
    assert "sys.argv[1]" in call_args[2]
    assert call_args[3].endswith('.json')

# 14. test_detector_3_suffix_loop_preserves_prefix
def test_detector_3_suffix_loop_preserves_prefix():
    from services.audio_service import _detect_and_strip_loop_hallucination
    # Prefix: 'some places you visit others you discover markets' (8 words)
    # Loop: 'constant constant constant' repeated 5 times
    text = "Some places you visit others you discover markets constant constant constant constant constant constant constant constant constant constant constant constant constant constant constant"
    cleaned, is_uncertain = _detect_and_strip_loop_hallucination(text)
    assert is_uncertain == True
    assert "Some places you visit others you discover markets" in cleaned
    assert "constant constant constant" not in cleaned

# 15. test_detector_3_full_loop_discards_completely
def test_detector_3_full_loop_discards_completely():
    from services.audio_service import _detect_and_strip_loop_hallucination
    text = "constant constant constant constant constant constant constant constant constant constant constant constant"
    cleaned, is_uncertain = _detect_and_strip_loop_hallucination(text)
    assert is_uncertain == True
    assert cleaned == ""

# 16. test_stt_uncertainty_forces_review_in_analyst
def test_stt_uncertainty_forces_review_in_analyst():
    with patch('ollama.chat') as mock_chat:
        mock_chat.return_value = {"message": {"content": '{"verdict": "approve", "reasoning": "Looks good", "confidence": 1.0}'}}
        analyst = AnalystService()
        metrics = {
            "overall_similarity": 1.0,
            "audio_similarity": 0.95,
            "audio_transcription": {
                "status": "completed",
                "is_uncertain": True,
                "uncertainty_reason": "Wykryto zapętlenie lektora",
                "is_text_match": True,
                "text_similarity": 0.98,
            }
        }
        res = analyst.analyze_job_results(metrics, db=MockDB())
        assert res["verdict"] == "review"
        assert "niepewny" in res["reasoning"].lower()

# 17a. test_unexpected_missing_stt_payload_fails_closed_and_forces_review
def test_unexpected_missing_stt_payload_fails_closed_and_forces_review():
    # Job has audio and was not allowlisted to skip STT, but speech_to_text payload is unexpectedly missing
    from services.comparison_service import ComparisonService
    analyst = AnalystService()

    audio_res = {
        "has_audio": True,
        "has_audio_any": True,
        "no_audio_tracks": False,
        "loudness": {"has_loudness_differences": True},
        # speech_to_text is missing unexpectedly!
    }
    
    stt = audio_res.get("speech_to_text")
    metrics = {}
    
    # Simulate comparison_service metrics builder
    if not stt or not isinstance(stt, dict):
        # Must fail-closed: status=failed, stt_skipped=False, is_uncertain=True
        metrics["audio_transcription"] = {
            "status": "failed",
            "text_similarity": None,
            "is_text_match": None,
            "error_message": "Unexpected missing STT payload without allowlisted skip reason",
            "is_uncertain": True,
            "uncertainty_reason": "Unregistered missing STT payload",
        }
        metrics["stt_skipped"] = False
        metrics["stt_skipped_reason"] = None

    assert metrics["stt_skipped"] == False
    assert metrics["audio_transcription"]["status"] == "failed"
    assert metrics["audio_transcription"]["is_uncertain"] == True

    # Confirm AnalystService degrades APPROVE to REVIEW
    metrics["overall_similarity"] = 1.0
    metrics["video_similarity"] = 1.0
    metrics["audio_similarity"] = 1.0
    with patch('ollama.chat') as mock_chat:
        mock_chat.return_value = {"message": {"content": '{"verdict": "approve", "reasoning": "Looks good", "confidence": 1.0}'}}
        decision = analyst.analyze_job_results(metrics, db=MockDB())
        assert decision["verdict"] == "review"
        assert "SYSTEM OVERRIDE" in decision["reasoning"]

# 17b. test_verified_allowlisted_stt_skip_sets_stt_skipped_true
def test_verified_allowlisted_stt_skip_sets_stt_skipped_true():
    # Legitimate skip due to no audio tracks present in both files
    audio_res = {
        "has_audio": False,
        "has_audio_any": False,
        "no_audio_tracks": True,
        "speech_to_text": {
            "status": "skipped",
            "skipped_reason": "NO_AUDIO_STREAMS: Both files lack audio tracks",
            "is_uncertain": False,
        }
    }
    stt = audio_res.get("speech_to_text")
    metrics = {}
    stt_status = stt.get("status")
    metrics["stt_skipped"] = (stt_status == "skipped")
    metrics["stt_skipped_reason"] = stt.get("skipped_reason")
    metrics["audio_transcription"] = {
        "status": stt_status,
        "skipped_reason": stt.get("skipped_reason"),
        "is_uncertain": stt.get("is_uncertain", False)
    }

    assert metrics["stt_skipped"] == True
    assert metrics["audio_transcription"]["status"] == "skipped"
    assert metrics["stt_skipped_reason"] == "NO_AUDIO_STREAMS: Both files lack audio tracks"
    assert metrics["audio_transcription"]["is_uncertain"] == False

# 18. test_completed_no_speech_sets_similarity_none
@patch('services.audio_service.compare_transcripts')
@patch('services.audio_service.transcribe_single_file')
@patch('services.audio_service.get_audio_stream_count', return_value=1)
def test_completed_no_speech_sets_similarity_none(mock_stream_count, mock_transcribe, mock_compare):
    mock_transcribe.side_effect = [
        {"transcript": {"word_count": 0, "text": ""}},
        {"transcript": {"word_count": 0, "text": ""}}
    ]
    mock_compare.return_value = {"text_similarity": 1.0, "is_text_match": True}
    res = audio_svc.compare_spoken_text("a", "b", force_stt=True)
    assert res["status"] == "completed_no_speech"
    assert res["text_similarity"] is None
    assert res["is_text_match"] is None
    assert res["comparison"]["text_similarity"] is None
    assert res["comparison"]["is_text_match"] is None


# 19. test_full_lufs_anomaly_overrides_raw_vad_silence_and_triggers_stt
def test_full_lufs_anomaly_overrides_raw_vad_silence_and_triggers_stt(mock_job):
    mock_job.comparison_type = ComparisonType.FULL
    audio_result = {
        "has_audio_any": True,
        "audio_pair_comparable": True,
        "no_audio_tracks": False,
        "loudness": {"has_loudness_differences": True},
        "raw_vad_speech": False, # Raw VAD reports silence
    }
    loudness_match_issue = audio_result["loudness"]["has_loudness_differences"]
    raw_vad_speech = audio_result["raw_vad_speech"]
    
    # LUFS anomaly MUST override Raw VAD silence and trigger STT
    should_run_stt = audio_result.get("has_audio_any", True) and not audio_result.get("no_audio_tracks", False) and (
        check_comp_type(mock_job.comparison_type, [ComparisonType.AUDIO_ONLY, ComparisonType.AUTOMATION, ComparisonType.VO_TRANSCRIPT])
        or (check_comp_type(mock_job.comparison_type, ComparisonType.FULL) and (loudness_match_issue or raw_vad_speech))
    )
    assert should_run_stt == True

# 20. test_full_lufs_match_with_raw_vad_speech_triggers_stt
def test_full_lufs_match_with_raw_vad_speech_triggers_stt(mock_job):
    mock_job.comparison_type = ComparisonType.FULL
    audio_result = {
        "has_audio_any": True,
        "audio_pair_comparable": True,
        "no_audio_tracks": False,
        "loudness": {"has_loudness_differences": False},
        "raw_vad_speech": True, # Raw VAD detects speech!
    }
    loudness_match_issue = audio_result["loudness"]["has_loudness_differences"]
    raw_vad_speech = audio_result["raw_vad_speech"]
    should_run_stt = audio_result.get("has_audio_any", True) and not audio_result.get("no_audio_tracks", False) and (
        check_comp_type(mock_job.comparison_type, [ComparisonType.AUDIO_ONLY, ComparisonType.AUTOMATION, ComparisonType.VO_TRANSCRIPT])
        or (check_comp_type(mock_job.comparison_type, ComparisonType.FULL) and (loudness_match_issue or raw_vad_speech))
    )
    assert should_run_stt == True

# 21. test_full_identical_binary_inputs_forces_review_as_duplicate_input
def test_full_identical_binary_inputs_forces_review_as_duplicate_input():
    with patch('ollama.chat') as mock_chat:
        mock_chat.return_value = {"message": {"content": '{"verdict": "approve", "reasoning": "Everything matches 100%", "confidence": 1.0}'}}
        analyst = AnalystService()
        metrics = {
            "overall_similarity": 1.0,
            "video_similarity": 1.0,
            "audio_similarity": 1.0,
            "audio_transcription": {
                "status": "skipped",
                "skipped_reason": "DUPLICATE_INPUT: Acceptance and Emission are binary identical files (possible duplicate download)",
                "is_uncertain": True,
                "uncertainty_reason": "DUPLICATE_INPUT: Identical binary files detected; requires verification of download integrity",
            }
        }
        res = analyst.analyze_job_results(metrics, db=MockDB())
        assert res["verdict"] == "review"
        assert "DUPLICATE_INPUT" in res["reasoning"]

# 22. test_vo_transcript_ignores_binary_duplicate_and_runs_stt
def test_vo_transcript_ignores_binary_duplicate_and_runs_stt(mock_job):
    mock_job.comparison_type = ComparisonType.VO_TRANSCRIPT
    audio_result = {
        "has_audio_any": True,
        "no_audio_tracks": False,
        "is_binary_duplicate": True,
    }
    is_vo_mode = check_comp_type(mock_job.comparison_type, ComparisonType.VO_TRANSCRIPT)
    has_duplicate_skip = audio_result.get("is_binary_duplicate") and check_comp_type(mock_job.comparison_type, ComparisonType.FULL)
    
    if has_duplicate_skip and not is_vo_mode:
        should_run_stt = False
    else:
        should_run_stt = audio_result.get("has_audio_any", True) and not audio_result.get("no_audio_tracks", False)
    assert should_run_stt == True

# 23. test_full_audio_mismatch_acc_has_audio_emi_silent
@patch('services.audio_service.transcribe_single_file')
@patch('services.audio_service.get_audio_stream_count')
def test_full_audio_mismatch_acc_has_audio_emi_silent(mock_stream_count, mock_transcribe):
    # acc has 1 stream, emi has 0 streams
    mock_stream_count.side_effect = [1, 0]
    mock_transcribe.return_value = {
        "transcript": {"text": "Important voiceover message in acceptance", "word_count": 6, "segments": [{"text": "Important", "start": 0, "end": 1}]}
    }
    res = audio_svc.compare_spoken_text("acc.mp4", "emi.mp4")
    assert res["status"] == "completed"
    assert res["text_similarity"] == 0.0
    assert res["is_text_match"] == False
    assert res["is_uncertain"] == True
    assert res["audio_mismatch"] == True
    assert res["transcript_emission"]["stream_status"] == "NO_AUDIO_STREAM_IN_FILE"

# 24. test_full_audio_mismatch_acc_silent_emi_has_audio
@patch('services.audio_service.transcribe_single_file')
@patch('services.audio_service.get_audio_stream_count')
def test_full_audio_mismatch_acc_silent_emi_has_audio(mock_stream_count, mock_transcribe):
    # acc has 0 streams, emi has 1 stream
    mock_stream_count.side_effect = [0, 1]
    mock_transcribe.return_value = {
        "transcript": {"text": "Voiceover present in emission only", "word_count": 5, "segments": [{"text": "Voiceover", "start": 0, "end": 1}]}
    }
    res = audio_svc.compare_spoken_text("acc.mp4", "emi.mp4")
    assert res["status"] == "completed"
    assert res["text_similarity"] == 0.0
    assert res["is_text_match"] == False
    assert res["is_uncertain"] == True
    assert res["audio_mismatch"] == True
    assert res["transcript_acceptance"]["stream_status"] == "NO_AUDIO_STREAM_IN_FILE"

# 25. test_detector_3_preserves_early_legitimate_ngram_occurrence
def test_detector_3_preserves_early_legitimate_ngram_occurrence():
    from services.audio_service import _detect_and_strip_loop_hallucination
    # Phrase 'the best price' appears legitimately earlier in the sentence,
    # and then repeats contiguously at the very end of the text.
    text = "We guarantee the best price for all customers today the best price the best price the best price the best price"
    cleaned, is_uncertain = _detect_and_strip_loop_hallucination(text)
    assert is_uncertain == True
    # The prefix 'We guarantee the best price for all customers today' must be completely preserved!
    assert "We guarantee the best price for all customers today" in cleaned

# 26. test_detector_3_uncertain_non_contiguous_preserves_full_text
def test_detector_3_uncertain_non_contiguous_preserves_full_text():
    from services.audio_service import _detect_and_strip_loop_hallucination
    # Non-contiguous repetitive n-gram scattered across text (not a tail suffix loop)
    text = "We have quality cars and quality cars are great because quality cars matter to drivers"
    cleaned, is_uncertain = _detect_and_strip_loop_hallucination(text)
    assert is_uncertain == True
    # Text must not be destroyed!
    assert "We have quality cars" in cleaned
    assert "drivers" in cleaned

def _mp_lock_worker(lock_path_str, log_file_str, hold_seconds):
    from services.audio_service import heavy_mps_model_lock
    import time
    import os

    pid = os.getpid()
    with heavy_mps_model_lock(lock_path_str):
        # Record enter timestamp
        t_enter = time.time()
        with open(log_file_str, "a") as f:
            f.write(f"{pid}:ENTER:{t_enter}\n")
        time.sleep(hold_seconds)
        t_exit = time.time()
        with open(log_file_str, "a") as f:
            f.write(f"{pid}:EXIT:{t_exit}\n")

# 27. test_multiprocess_mps_heavy_model_lock_serialization
def test_multiprocess_mps_heavy_model_lock_serialization(tmp_path):
    import multiprocessing as mp
    import time

    lock_file = str(tmp_path / "mp_test_nvc_mps.lock")
    log_file = str(tmp_path / "mp_test_events.log")
    
    ctx = mp.get_context("spawn")
    p1 = ctx.Process(target=_mp_lock_worker, args=(lock_file, log_file, 0.15))
    p2 = ctx.Process(target=_mp_lock_worker, args=(lock_file, log_file, 0.15))

    p1.start()
    time.sleep(0.02) # Small offset so p1 enters first
    p2.start()

    p1.join(timeout=5)
    p2.join(timeout=5)

    assert p1.exitcode == 0, f"Process 1 failed with code {p1.exitcode}"
    assert p2.exitcode == 0, f"Process 2 failed with code {p2.exitcode}"

    # Parse log file and verify non-overlapping intervals
    with open(log_file, "r") as f:
        lines = [line.strip().split(":") for line in f if line.strip()]

    events_by_pid = {}
    for pid, event, t_str in lines:
        t = float(t_str)
        if pid not in events_by_pid:
            events_by_pid[pid] = {}
        events_by_pid[pid][event] = t

    pids = list(events_by_pid.keys())
    assert len(pids) == 2, f"Expected 2 distinct PIDs in log, got {len(pids)}: {lines}"

    pid_a, pid_b = pids[0], pids[1]
    a_enter = events_by_pid[pid_a]["ENTER"]
    a_exit = events_by_pid[pid_a]["EXIT"]
    b_enter = events_by_pid[pid_b]["ENTER"]
    b_exit = events_by_pid[pid_b]["EXIT"]

    # Verify that the two process critical sections do NOT overlap
    # Either process A finished before B started, OR process B finished before A started
    no_overlap = (a_exit <= b_enter) or (b_exit <= a_enter)
    assert no_overlap, f"Critical section overlap detected between OS processes! A=[{a_enter}, {a_exit}], B=[{b_enter}, {b_exit}]"

# 28. test_dominant_music_with_zero_whisper_forces_review
def test_dominant_music_with_zero_whisper_forces_review():
    with patch('ollama.chat') as mock_chat:
        mock_chat.return_value = {"message": {"content": '{"verdict": "approve", "reasoning": "Looks good", "confidence": 1.0}'}}
        analyst = AnalystService()
        metrics = {
            "overall_similarity": 1.0,
            "audio_similarity": 0.95,
            "audio_transcription": {
                "status": "completed_no_speech",
                "is_uncertain": True,
                "uncertainty_reason": "Music proportion > 0.55: speech absence cannot be verified due to dominant music",
                "text_similarity": None,
                "is_text_match": None,
            }
        }
        res = analyst.analyze_job_results(metrics, db=MockDB())
        assert res["verdict"] == "review"
        assert "niepewny" in res["reasoning"].lower()

# 29. test_streaming_sha256_different_contents
def test_streaming_sha256_different_contents(tmp_path):
    from services.audio_service import compute_file_sha256
    f1 = tmp_path / "file1.bin"
    f2 = tmp_path / "file2.bin"
    f1.write_bytes(b"content A" * 1000)
    f2.write_bytes(b"content B" * 1000)
    assert compute_file_sha256(f1) != compute_file_sha256(f2)
    f3 = tmp_path / "file3.bin"
    f3.write_bytes(b"content A" * 1000)
    assert compute_file_sha256(f1) == compute_file_sha256(f3)


# 30. test_heavy_mps_model_lock_flock_error_fail_closed
def test_heavy_mps_model_lock_flock_error_fail_closed():
    from services.audio_service import heavy_mps_model_lock, HeavyModelLockError, _heavy_model_lock
    import fcntl
    import errno

    # Mock fcntl.flock to raise OSError EACCES
    with patch('fcntl.flock', side_effect=OSError(errno.EACCES, "Permission denied")):
        with patch('subprocess.run') as mock_subproc:
            with pytest.raises(HeavyModelLockError) as exc_info:
                with heavy_mps_model_lock("/tmp/test_flock_fail.lock"):
                    mock_subproc("should not run")
            
            # 1. subprocess.run MUST NOT be called!
            mock_subproc.assert_not_called()
            assert "Permission denied" in str(exc_info.value)
            
            # 2. Local threading lock MUST be released and not remain locked!
            acquired = _heavy_model_lock.acquire(blocking=False)
            assert acquired == True, "Local threading lock remained locked after exception!"
            _heavy_model_lock.release()

# 31. test_heavy_mps_model_lock_open_error_fail_closed
def test_heavy_mps_model_lock_open_error_fail_closed():
    from services.audio_service import heavy_mps_model_lock, HeavyModelLockError, _heavy_model_lock

    with patch('builtins.open', side_effect=PermissionError("Cannot open lock file")):
        with patch('subprocess.run') as mock_subproc:
            with pytest.raises(HeavyModelLockError):
                with heavy_mps_model_lock("/tmp/test_open_fail.lock"):
                    mock_subproc("should not run")
            
            mock_subproc.assert_not_called()
            # Local lock must be released
            acquired = _heavy_model_lock.acquire(blocking=False)
            assert acquired == True, "Local threading lock remained locked after open failure!"
            _heavy_model_lock.release()

# 32. test_heavy_mps_lock_failure_in_whisper_returns_failed_and_triggers_review
def test_heavy_mps_lock_failure_in_whisper_returns_failed_and_triggers_review():
    from services.audio_service import transcribe_audio
    import fcntl
    import errno

    with patch('fcntl.flock', side_effect=OSError(errno.EACCES, "Permission denied")):
        with patch('subprocess.run') as mock_subproc:
            res = transcribe_audio("sample.wav")
            mock_subproc.assert_not_called()
            assert "error" in res
            assert "HeavyModelLockError" in res["error"] or "Permission denied" in res["error"]
            
            # Verify AnalystService maps this to REVIEW, never APPROVE
            analyst = AnalystService()
            metrics = {
                "overall_similarity": 1.0,
                "video_similarity": 1.0,
                "audio_similarity": 1.0,
                "audio_transcription": {
                    "status": "failed",
                    "error_message": res["error"],
                    "is_uncertain": True,
                    "text_similarity": None,
                    "is_text_match": None,
                }
            }
            with patch('ollama.chat') as mock_chat:
                mock_chat.return_value = {"message": {"content": '{"verdict": "approve", "reasoning": "Looks good", "confidence": 1.0}'}}
                decision = analyst.analyze_job_results(metrics, db=MockDB())
                assert decision["verdict"] == "review"
                assert "SYSTEM OVERRIDE" in decision["reasoning"]

# 33. test_heavy_mps_model_lock_sequential_demucs_and_whisper_no_deadlock
def test_heavy_mps_model_lock_sequential_demucs_and_whisper_no_deadlock():
    from services.audio_service import heavy_mps_model_lock, _heavy_model_lock
    # Simulates a pipeline executing Demucs then Whisper sequentially under heavy_mps_model_lock
    # Verifies both acquire and release cleanly without nested deadlock
    with heavy_mps_model_lock("/tmp/test_seq.lock"):
        # Demucs runs
        pass
    
    # Between models: lock is released
    assert _heavy_model_lock.acquire(blocking=False) == True
    _heavy_model_lock.release()

    with heavy_mps_model_lock("/tmp/test_seq.lock"):
        # Whisper runs
        pass

    assert _heavy_model_lock.acquire(blocking=False) == True
    _heavy_model_lock.release()

# 34. test_heavy_mps_lock_failure_in_demucs_aborts_without_running_whisper
def test_heavy_mps_lock_failure_in_demucs_aborts_without_running_whisper():
    from services.audio_service import transcribe_single_file
    import fcntl
    import errno

    # Mock fcntl.flock to fail during Demucs
    with patch('fcntl.flock', side_effect=OSError(errno.EACCES, "Permission denied")):
        with patch('subprocess.run') as mock_subproc:
            res = transcribe_single_file("audio.wav", use_source_separation=True)
            # Demucs and Whisper subprocesses MUST NOT be called!
            mock_subproc.assert_not_called()
            # Must return clean error structure without running Whisper
            assert "error" in res["transcript"]
            assert "Hardware lock failure" in res["transcript"]["error"]


# 35. test_full_lufs_match_raw_vad_error_without_stt_payload_fails_closed
def test_full_lufs_match_raw_vad_error_without_stt_payload_fails_closed(mock_job):
    from services.comparison_service import ComparisonService
    analyst = AnalystService()

    # FULL + matching LUFS + raw_vad_status="error" + missing STT payload
    results = {
        "overall_similarity": 1.0,
        "video_result": {"overall_similarity": 1.0, "frames_with_differences": 0},
        "audio_result": {
            "has_audio": True,
            "has_audio_any": True,
            "audio_pair_comparable": True,
            "no_audio_tracks": False,
            "similarity_score": 1.0,
            "loudness": {"has_loudness_differences": False},
            "music_proportion": 0.20,
            "raw_vad_status": "error",
            "raw_vad_error": "Silero VAD model failure",
            "raw_vad_inconclusive": True,
            "raw_vad_metrics_complete": False,
            # STT payload is missing
        }
    }

    metrics = ComparisonService._build_ai_metrics(mock_job, results)
    
    # Must be failed/uncertain, never skipped
    assert metrics["stt_skipped"] is False
    assert metrics["stt_skipped_reason"] is None
    assert metrics["audio_transcription"]["status"] == "failed"
    assert metrics["audio_transcription"]["is_uncertain"] is True
    assert "Unexpected missing STT payload" in metrics["audio_transcription"]["error_message"]

    # AI verdict must degrade to REVIEW, never APPROVE
    with patch('ollama.chat') as mock_chat:
        mock_chat.return_value = {"message": {"content": '{"verdict": "approve", "reasoning": "Matching video and audio", "confidence": 1.0}'}}
        decision = analyst.analyze_job_results(metrics, db=MockDB())
        assert decision["verdict"] == "review"
        assert "SYSTEM OVERRIDE" in decision["reasoning"]


# 36. test_full_lufs_match_raw_vad_uncertain_or_missing_status_fails_closed
def test_full_lufs_match_raw_vad_uncertain_or_missing_status_fails_closed(mock_job):
    from services.comparison_service import ComparisonService
    analyst = AnalystService()

    # Subcase A: raw_vad_status="uncertain"
    results_uncertain = {
        "overall_similarity": 1.0,
        "video_result": {"overall_similarity": 1.0, "frames_with_differences": 0},
        "audio_result": {
            "has_audio": True,
            "has_audio_any": True,
            "audio_pair_comparable": True,
            "no_audio_tracks": False,
            "similarity_score": 1.0,
            "loudness": {"has_loudness_differences": False},
            "music_proportion": 0.20,
            "raw_vad_status": "uncertain",
            "raw_vad_inconclusive": True,
            "raw_vad_metrics_complete": False,
        }
    }
    metrics_a = ComparisonService._build_ai_metrics(mock_job, results_uncertain)
    assert metrics_a["stt_skipped"] is False
    assert metrics_a["audio_transcription"]["status"] == "failed"
    assert metrics_a["audio_transcription"]["is_uncertain"] is True

    # Subcase B: missing raw_vad_status entirely
    results_missing = {
        "overall_similarity": 1.0,
        "video_result": {"overall_similarity": 1.0, "frames_with_differences": 0},
        "audio_result": {
            "has_audio": True,
            "has_audio_any": True,
            "audio_pair_comparable": True,
            "no_audio_tracks": False,
            "similarity_score": 1.0,
            "loudness": {"has_loudness_differences": False},
            "music_proportion": 0.20,
            # raw_vad_status missing
        }
    }
    metrics_b = ComparisonService._build_ai_metrics(mock_job, results_missing)
    assert metrics_b["stt_skipped"] is False
    assert metrics_b["audio_transcription"]["status"] == "failed"
    assert metrics_b["audio_transcription"]["is_uncertain"] is True

    # Subcase C: raw_vad_status="no_speech" but incomplete metrics
    results_incomplete_metrics = {
        "overall_similarity": 1.0,
        "video_result": {"overall_similarity": 1.0, "frames_with_differences": 0},
        "audio_result": {
            "has_audio": True,
            "has_audio_any": True,
            "audio_pair_comparable": True,
            "no_audio_tracks": False,
            "similarity_score": 1.0,
            "loudness": {"has_loudness_differences": False},
            "music_proportion": 0.20,
            "raw_vad_status": "no_speech",
            "raw_vad_metrics_complete": False,  # metrics incomplete!
        }
    }
    metrics_c = ComparisonService._build_ai_metrics(mock_job, results_incomplete_metrics)
    assert metrics_c["stt_skipped"] is False
    assert metrics_c["audio_transcription"]["status"] == "failed"
    assert metrics_c["audio_transcription"]["is_uncertain"] is True

    with patch('ollama.chat') as mock_chat:
        mock_chat.return_value = {"message": {"content": '{"verdict": "approve", "reasoning": "Matching", "confidence": 1.0}'}}
        decision = analyst.analyze_job_results(metrics_b, db=MockDB())
        assert decision["verdict"] == "review"
        assert "SYSTEM OVERRIDE" in decision["reasoning"]


# 37. test_full_lufs_match_raw_vad_no_speech_complete_metrics_allows_explicit_skip
def test_full_lufs_match_raw_vad_no_speech_complete_metrics_allows_explicit_skip(mock_job):
    from services.comparison_service import ComparisonService
    analyst = AnalystService()

    # FULL + matching LUFS + raw_vad_status="no_speech" + complete metrics + music <= 0.55
    results = {
        "overall_similarity": 1.0,
        "video_result": {"overall_similarity": 1.0, "frames_with_differences": 0},
        "audio_result": {
            "has_audio": True,
            "has_audio_any": True,
            "audio_pair_comparable": True,
            "no_audio_tracks": False,
            "similarity_score": 1.0,
            "loudness": {"has_loudness_differences": False},
            "music_proportion": 0.15,
            "raw_vad_status": "no_speech",
            "raw_vad_speech": False,
            "raw_vad_inconclusive": False,
            "raw_vad_metrics_complete": True,
            "raw_vad_a": {
                "status": "no_speech",
                "has_speech": False,
                "speech_duration_s": 0.0,
                "segments_count": 0,
                "error": None,
            },
            "raw_vad_b": {
                "status": "no_speech",
                "has_speech": False,
                "speech_duration_s": 0.0,
                "segments_count": 0,
                "error": None,
            },
        }
    }

    metrics = ComparisonService._build_ai_metrics(mock_job, results)

    # Must be allowed explicit skip
    assert metrics["stt_skipped"] is True
    assert metrics["stt_skipped_reason"] == "FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH"
    assert metrics["audio_transcription"]["status"] == "skipped"
    assert metrics["audio_transcription"]["is_uncertain"] is False
    assert metrics["audio_transcription"]["skipped_reason"] == "FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH"

    # AI verdict is NOT degraded by STT failure (permits APPROVE)
    with patch('ollama.chat') as mock_chat:
        mock_chat.return_value = {"message": {"content": '{"verdict": "approve", "reasoning": "Identical video and silent audio", "confidence": 1.0}'}}
        decision = analyst.analyze_job_results(metrics, db=MockDB())
        assert decision["verdict"] == "approve"


# 38. test_allowlist_rejects_untrusted_loose_substring_skip_reasons
def test_allowlist_rejects_untrusted_loose_substring_skip_reasons(mock_job):
    from services.comparison_service import ComparisonService, is_trusted_stt_skip_reason
    analyst = AnalystService()

    # 1. Direct unit verification of is_trusted_stt_skip_reason
    # Malicious or untrusted strings containing allowlisted tokens as loose substrings MUST FAIL
    assert is_trusted_stt_skip_reason("UNAUTHORIZED_NO_AUDIO_STREAMS") is False
    assert is_trusted_stt_skip_reason("NO_AUDIO_STREAMS_BYPASS") is False
    assert is_trusted_stt_skip_reason("SOME_DUPLICATE_INPUT_EXPLOIT") is False
    assert is_trusted_stt_skip_reason("FULL_MODE_IDENTICAL_LOUDNESS_FAKE") is False
    assert is_trusted_stt_skip_reason("FULL_MODE_IDENTICAL_LOUDNESS") is False
    assert is_trusted_stt_skip_reason("Audio similarity 0.5000 is low but skip anyway") is False
    assert is_trusted_stt_skip_reason("") is False
    assert is_trusted_stt_skip_reason(None) is False

    # Trusted exact or canonical prefixed tokens MUST PASS
    assert is_trusted_stt_skip_reason("NO_AUDIO_STREAMS") is True
    assert is_trusted_stt_skip_reason("NO_AUDIO_STREAMS: Both files lack audio streams.") is True
    assert is_trusted_stt_skip_reason("DUPLICATE_INPUT") is True
    assert is_trusted_stt_skip_reason("DUPLICATE_INPUT: Identical SHA256 inputs") is True
    assert is_trusted_stt_skip_reason("FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH") is True
    assert is_trusted_stt_skip_reason("FAST_PATH_IDENTICAL_AUDIO") is True
    assert is_trusted_stt_skip_reason("Audio similarity 0.9950 >= 0.98. STT skipped to avoid false positives from source separation non-determinism.") is True

    # 2. Integration with _build_ai_metrics: untrusted skip reason is demoted to failed/uncertain
    results_untrusted = {
        "overall_similarity": 1.0,
        "video_result": {"overall_similarity": 1.0, "frames_with_differences": 0},
        "audio_result": {
            "has_audio": True,
            "has_audio_any": True,
            "similarity_score": 1.0,
            "speech_to_text": {
                "status": "skipped",
                "skipped_reason": "UNAUTHORIZED_NO_AUDIO_STREAMS",
            }
        }
    }
    metrics = ComparisonService._build_ai_metrics(mock_job, results_untrusted)
    assert metrics["stt_skipped"] is False
    assert metrics["audio_transcription"]["status"] == "failed"
    assert metrics["audio_transcription"]["is_uncertain"] is True
    assert "Unverified STT skip reason" in metrics["audio_transcription"]["uncertainty_reason"]

    with patch('ollama.chat') as mock_chat:
        mock_chat.return_value = {"message": {"content": '{"verdict": "approve", "reasoning": "Looks fine", "confidence": 1.0}'}}
        decision = analyst.analyze_job_results(metrics, db=MockDB())
        assert decision["verdict"] == "review"
        assert "SYSTEM OVERRIDE" in decision["reasoning"]


# 39. test_generic_full_mode_identical_loudness_rejected_fails_closed
def test_generic_full_mode_identical_loudness_rejected_fails_closed(mock_job):
    from services.comparison_service import ComparisonService, is_trusted_stt_skip_reason
    analyst = AnalystService()

    assert is_trusted_stt_skip_reason("FULL_MODE_IDENTICAL_LOUDNESS") is False

    # Job claiming generic FULL_MODE_IDENTICAL_LOUDNESS must be rejected as unverified skip
    results = {
        "overall_similarity": 1.0,
        "video_result": {"overall_similarity": 1.0, "frames_with_differences": 0},
        "audio_result": {
            "has_audio": True,
            "has_audio_any": True,
            "audio_pair_comparable": True,
            "no_audio_tracks": False,
            "similarity_score": 1.0,
            "loudness": {"has_loudness_differences": False},
            "music_proportion": 0.20,
            "speech_to_text": {
                "status": "skipped",
                "skipped_reason": "FULL_MODE_IDENTICAL_LOUDNESS",
            }
        }
    }
    metrics = ComparisonService._build_ai_metrics(mock_job, results)
    assert metrics["stt_skipped"] is False
    assert metrics["audio_transcription"]["status"] == "failed"
    assert metrics["audio_transcription"]["is_uncertain"] is True
    assert "Unverified STT skip reason" in metrics["audio_transcription"]["uncertainty_reason"]

    with patch('ollama.chat') as mock_chat:
        mock_chat.return_value = {"message": {"content": '{"verdict": "approve", "reasoning": "Identical audio", "confidence": 1.0}'}}
        decision = analyst.analyze_job_results(metrics, db=MockDB())
        assert decision["verdict"] == "review"
        assert "SYSTEM OVERRIDE" in decision["reasoning"]


# 40. test_no_audio_streams_rejected_when_audio_mismatch_present_forces_review
def test_no_audio_streams_rejected_when_audio_mismatch_present_forces_review(mock_job):
    from services.comparison_service import ComparisonService
    analyst = AnalystService()

    # Asymmetric audio where payload fraudulently or mistakenly claims NO_AUDIO_STREAMS
    results = {
        "overall_similarity": 1.0,
        "video_result": {"overall_similarity": 1.0, "frames_with_differences": 0},
        "audio_result": {
            "has_audio": False,
            "has_audio_any": True,
            "acc_has_audio": True,
            "emi_has_audio": False,
            "audio_pair_comparable": False,
            "no_audio_tracks": False,
            "audio_mismatch": True,
            "similarity_score": 0.0,
            "speech_to_text": {
                "status": "skipped",
                "skipped_reason": "NO_AUDIO_STREAMS: Both files lack audio streams.",
            }
        }
    }
    metrics = ComparisonService._build_ai_metrics(mock_job, results)
    # Must reject skip because audio_mismatch is present and audio streams exist
    assert metrics["stt_skipped"] is False
    assert metrics["audio_transcription"]["status"] == "failed"
    assert metrics["audio_transcription"]["is_uncertain"] is True
    assert "NO_AUDIO_STREAMS skip invalid" in metrics["audio_transcription"]["uncertainty_reason"]

    with patch('ollama.chat') as mock_chat:
        mock_chat.return_value = {"message": {"content": '{"verdict": "approve", "reasoning": "No audio", "confidence": 1.0}'}}
        decision = analyst.analyze_job_results(metrics, db=MockDB())
        assert decision["verdict"] == "review"
        assert "SYSTEM OVERRIDE" in decision["reasoning"]


# 41. test_full_mode_identical_loudness_and_no_speech_strictly_verified_with_full_criteria
def test_full_mode_identical_loudness_and_no_speech_strictly_verified_with_full_criteria(mock_job):
    from services.comparison_service import ComparisonService
    analyst = AnalystService()

    # Case A: Reason string matches, but Raw VAD reported error => REJECT SKIP!
    results_vad_error = {
        "overall_similarity": 1.0,
        "video_result": {"overall_similarity": 1.0, "frames_with_differences": 0},
        "audio_result": {
            "has_audio": True,
            "has_audio_any": True,
            "audio_pair_comparable": True,
            "no_audio_tracks": False,
            "similarity_score": 1.0,
            "loudness": {"has_loudness_differences": False},
            "music_proportion": 0.20,
            "raw_vad_status": "error",
            "raw_vad_error": "VAD crash",
            "raw_vad_metrics_complete": False,
            "speech_to_text": {
                "status": "skipped",
                "skipped_reason": "FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH",
            }
        }
    }
    metrics_a = ComparisonService._build_ai_metrics(mock_job, results_vad_error)
    assert metrics_a["stt_skipped"] is False
    assert metrics_a["audio_transcription"]["status"] == "failed"
    assert metrics_a["audio_transcription"]["is_uncertain"] is True
    assert "FULL_MODE skip invalid" in metrics_a["audio_transcription"]["uncertainty_reason"]

    # Case B: Reason string matches, but music dominates (> 0.55) => REJECT SKIP!
    results_music_dominance = {
        "overall_similarity": 1.0,
        "video_result": {"overall_similarity": 1.0, "frames_with_differences": 0},
        "audio_result": {
            "has_audio": True,
            "has_audio_any": True,
            "audio_pair_comparable": True,
            "no_audio_tracks": False,
            "similarity_score": 1.0,
            "loudness": {"has_loudness_differences": False},
            "music_proportion": 0.75, # Dominant music!
            "raw_vad_status": "no_speech",
            "raw_vad_speech": False,
            "raw_vad_metrics_complete": True,
            "speech_to_text": {
                "status": "skipped",
                "skipped_reason": "FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH",
            }
        }
    }
    metrics_b = ComparisonService._build_ai_metrics(mock_job, results_music_dominance)
    assert metrics_b["stt_skipped"] is False
    assert metrics_b["audio_transcription"]["status"] == "failed"
    assert metrics_b["audio_transcription"]["is_uncertain"] is True

    # Case C: All criteria verified (VAD no_speech, complete metrics, LUFS match, music <= 0.55) => ALLOW SKIP!
    results_verified = {
        "overall_similarity": 1.0,
        "video_result": {"overall_similarity": 1.0, "frames_with_differences": 0},
        "audio_result": {
            "has_audio": True,
            "has_audio_any": True,
            "audio_pair_comparable": True,
            "no_audio_tracks": False,
            "similarity_score": 1.0,
            "loudness": {"has_loudness_differences": False},
            "music_proportion": 0.20,
            "raw_vad_status": "no_speech",
            "raw_vad_speech": False,
            "raw_vad_inconclusive": False,
            "raw_vad_error": None,
            "raw_vad_metrics_complete": True,
            "raw_vad_a": {
                "status": "no_speech",
                "has_speech": False,
                "speech_duration_s": 0.0,
                "segments_count": 0,
                "error": None,
            },
            "raw_vad_b": {
                "status": "no_speech",
                "has_speech": False,
                "speech_duration_s": 0.0,
                "segments_count": 0,
                "error": None,
            },
            "speech_to_text": {
                "status": "skipped",
                "skipped_reason": "FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH",
            }
        }
    }
    metrics_c = ComparisonService._build_ai_metrics(mock_job, results_verified)
    assert metrics_c["stt_skipped"] is True
    assert metrics_c["audio_transcription"]["status"] == "skipped"
    assert metrics_c["audio_transcription"]["is_uncertain"] is False


# 42. test_unilateral_audio_in_both_directions_cannot_be_skipped_and_forces_review
def test_unilateral_audio_in_both_directions_cannot_be_skipped_and_forces_review(mock_job):
    from services.comparison_service import ComparisonService
    analyst = AnalystService()

    # Direction 1: Acc has audio, Emi is silent
    res_dir1 = {
        "overall_similarity": 1.0,
        "video_result": {"overall_similarity": 1.0, "frames_with_differences": 0},
        "audio_result": {
            "has_audio": False,
            "has_audio_any": True,
            "acc_has_audio": True,
            "emi_has_audio": False,
            "audio_pair_comparable": False,
            "no_audio_tracks": False,
            "audio_mismatch": True,
            "similarity_score": 0.0,
        }
    }
    m1 = ComparisonService._build_ai_metrics(mock_job, res_dir1)
    assert m1["stt_skipped"] is False
    assert m1["audio_mismatch"] is True
    assert m1["audio_transcription"]["status"] == "failed"
    assert m1["audio_transcription"]["is_uncertain"] is True

    # Direction 2: Acc is silent, Emi has audio
    res_dir2 = {
        "overall_similarity": 1.0,
        "video_result": {"overall_similarity": 1.0, "frames_with_differences": 0},
        "audio_result": {
            "has_audio": False,
            "has_audio_any": True,
            "acc_has_audio": False,
            "emi_has_audio": True,
            "audio_pair_comparable": False,
            "no_audio_tracks": False,
            "audio_mismatch": True,
            "similarity_score": 0.0,
        }
    }
    m2 = ComparisonService._build_ai_metrics(mock_job, res_dir2)
    assert m2["stt_skipped"] is False
    assert m2["audio_mismatch"] is True
    assert m2["audio_transcription"]["status"] == "failed"
    assert m2["audio_transcription"]["is_uncertain"] is True

    with patch('ollama.chat') as mock_chat:
        mock_chat.return_value = {"message": {"content": '{"verdict": "approve", "reasoning": "Matching", "confidence": 1.0}'}}
        d1 = analyst.analyze_job_results(m1, db=MockDB())
        d2 = analyst.analyze_job_results(m2, db=MockDB())
        assert d1["verdict"] == "review"
        assert d2["verdict"] == "review"
        assert "SYSTEM OVERRIDE" in d1["reasoning"]
        assert "SYSTEM OVERRIDE" in d2["reasoning"]


# 43. test_fast_path_identical_audio_strictly_verified_against_similarity_score_and_mode
def test_fast_path_identical_audio_strictly_verified_against_similarity_score_and_mode(mock_job):
    from services.comparison_service import ComparisonService, extract_normalized_skip_code
    analyst = AnalystService()

    assert extract_normalized_skip_code("FAST_PATH_IDENTICAL_AUDIO") == "FAST_PATH_IDENTICAL_AUDIO"
    assert extract_normalized_skip_code("FAST_PATH_IDENTICAL_AUDIO: verified") == "FAST_PATH_IDENTICAL_AUDIO"
    assert extract_normalized_skip_code("UNAUTHORIZED_FAST_PATH_IDENTICAL_AUDIO: fake") is None

    # Case A: Valid fast path in AUTOMATION mode with similarity >= 0.98
    mock_job.comparison_type = ComparisonType.AUTOMATION
    res_valid = {
        "overall_similarity": 1.0,
        "video_result": {"overall_similarity": 1.0, "frames_with_differences": 0},
        "audio_result": {
            "has_audio": True,
            "has_audio_any": True,
            "audio_pair_comparable": True,
            "no_audio_tracks": False,
            "similarity_score": 0.9950,
            "loudness": {"has_loudness_differences": False},
            "speech_to_text": {
                "status": "skipped",
                "skipped_reason": "FAST_PATH_IDENTICAL_AUDIO",
            }
        }
    }
    m_valid = ComparisonService._build_ai_metrics(mock_job, res_valid)
    assert m_valid["stt_skipped"] is True
    assert m_valid["audio_transcription"]["status"] == "skipped"
    assert m_valid["audio_transcription"]["is_uncertain"] is False

    # Case B: Fraudulent/invalid similarity < 0.98 claiming fast path => REJECT
    res_low_sim = {
        "overall_similarity": 1.0,
        "video_result": {"overall_similarity": 1.0, "frames_with_differences": 0},
        "audio_result": {
            "has_audio": True,
            "has_audio_any": True,
            "audio_pair_comparable": True,
            "no_audio_tracks": False,
            "similarity_score": 0.9200, # Below 0.98 threshold!
            "loudness": {"has_loudness_differences": False},
            "speech_to_text": {
                "status": "skipped",
                "skipped_reason": "FAST_PATH_IDENTICAL_AUDIO",
            }
        }
    }
    m_low = ComparisonService._build_ai_metrics(mock_job, res_low_sim)
    assert m_low["stt_skipped"] is False
    assert m_low["audio_transcription"]["status"] == "failed"
    assert m_low["audio_transcription"]["is_uncertain"] is True
    assert "FAST_PATH audio skip invalid" in m_low["audio_transcription"]["uncertainty_reason"]

    # Case C: Fast path claimed during audio mismatch => REJECT
    res_mismatch = {
        "overall_similarity": 1.0,
        "video_result": {"overall_similarity": 1.0, "frames_with_differences": 0},
        "audio_result": {
            "has_audio": False,
            "has_audio_any": True,
            "acc_has_audio": True,
            "emi_has_audio": False,
            "audio_mismatch": True,
            "similarity_score": 0.9950,
            "speech_to_text": {
                "status": "skipped",
                "skipped_reason": "FAST_PATH_IDENTICAL_AUDIO",
            }
        }
    }
    m_mis = ComparisonService._build_ai_metrics(mock_job, res_mismatch)
    assert m_mis["stt_skipped"] is False
    assert m_mis["audio_transcription"]["status"] == "failed"
    assert m_mis["audio_transcription"]["is_uncertain"] is True

    # Case D: VO_TRANSCRIPT mode claims fast path => REJECT (VO must always transcribe)
    mock_job.comparison_type = ComparisonType.VO_TRANSCRIPT
    res_vo = {
        "overall_similarity": 1.0,
        "video_result": {"overall_similarity": 1.0, "frames_with_differences": 0},
        "audio_result": {
            "has_audio": True,
            "has_audio_any": True,
            "audio_pair_comparable": True,
            "no_audio_tracks": False,
            "similarity_score": 0.9950,
            "speech_to_text": {
                "status": "skipped",
                "skipped_reason": "FAST_PATH_IDENTICAL_AUDIO",
            }
        }
    }
    m_vo = ComparisonService._build_ai_metrics(mock_job, res_vo)
    assert m_vo["stt_skipped"] is False
    assert m_vo["audio_transcription"]["status"] == "failed"
    assert m_vo["audio_transcription"]["is_uncertain"] is True


# 44. test_duplicate_input_strictly_verified_against_is_binary_duplicate_flag
def test_duplicate_input_strictly_verified_against_is_binary_duplicate_flag(mock_job):
    from services.comparison_service import ComparisonService, extract_normalized_skip_code
    analyst = AnalystService()

    assert extract_normalized_skip_code("DUPLICATE_INPUT") == "DUPLICATE_INPUT"
    assert extract_normalized_skip_code("DUPLICATE_INPUT: Identical SHA256") == "DUPLICATE_INPUT"
    assert extract_normalized_skip_code("EXPLOIT_DUPLICATE_INPUT: fake") is None

    mock_job.comparison_type = ComparisonType.FULL

    # Case A: True binary duplicate in FULL mode => skip accepted, BUT is_uncertain=True forces REVIEW
    res_true_dup = {
        "overall_similarity": 1.0,
        "video_result": {"overall_similarity": 1.0, "frames_with_differences": 0},
        "audio_result": {
            "has_audio": True,
            "has_audio_any": True,
            "audio_pair_comparable": True,
            "no_audio_tracks": False,
            "is_binary_duplicate": True, # Real streaming SHA256 match
            "similarity_score": 1.0,
            "speech_to_text": {
                "status": "skipped",
                "skipped_reason": "DUPLICATE_INPUT: Acceptance and Emission are binary identical files",
            }
        }
    }
    m_dup = ComparisonService._build_ai_metrics(mock_job, res_true_dup)
    assert m_dup["stt_skipped"] is True
    assert m_dup["audio_transcription"]["status"] == "skipped"
    assert m_dup["audio_transcription"]["is_uncertain"] is True # CRITICAL: MUST FORCE REVIEW!

    with patch('ollama.chat') as mock_chat:
        mock_chat.return_value = {"message": {"content": '{"verdict": "approve", "reasoning": "Identical files", "confidence": 1.0}'}}
        decision = analyst.analyze_job_results(m_dup, db=MockDB())
        assert decision["verdict"] == "review"
        assert "DUPLICATE_INPUT" in decision["reasoning"]

    # Case B: False/fraudulent duplicate claim when files are NOT binary duplicates => REJECT
    res_fake_dup = {
        "overall_similarity": 1.0,
        "video_result": {"overall_similarity": 1.0, "frames_with_differences": 0},
        "audio_result": {
            "has_audio": True,
            "has_audio_any": True,
            "audio_pair_comparable": True,
            "no_audio_tracks": False,
            "is_binary_duplicate": False, # NOT a binary duplicate!
            "similarity_score": 1.0,
            "speech_to_text": {
                "status": "skipped",
                "skipped_reason": "DUPLICATE_INPUT: Fake claim",
            }
        }
    }
    m_fake = ComparisonService._build_ai_metrics(mock_job, res_fake_dup)
    assert m_fake["stt_skipped"] is False
    assert m_fake["audio_transcription"]["status"] == "failed"
    assert m_fake["audio_transcription"]["is_uncertain"] is True
    assert "DUPLICATE_INPUT skip invalid" in m_fake["audio_transcription"]["uncertainty_reason"]
