"""
Deterministic Metrics Adapter for Cradle Video QA Automation.

KEY ARCHITECTURAL PRINCIPLES:
- Pure data mapping adapter: NO imports of ollama, SQLAlchemy, database models,
  main, or FastAPI.
- Accepts real outputs from current comparison pipeline:
  - raw results dictionary (results containing video_result, audio_result, etc.)
  - OR metrics_snapshot dictionary (as created by _build_ai_metrics())
  - OR job metadata objects / dictionaries
- Transforms nested metrics into the canonical contract strictly required by
  DeterministicDecisionEngineV1.
- Never guesses missing values. For missing or ambiguous fields, leaves them None
  or set to explicit flags so the engine fails closed with REVIEW.
- Pure in-memory extraction: does NOT perform file hashing, disk I/O, or database queries.
"""

from typing import Dict, Any, Optional
import math


def _is_valid_number(val: Any) -> bool:
    """Check if value is a finite float or int (not None, NaN, inf, or bool)."""
    if val is None or isinstance(val, bool):
        return False
    if not isinstance(val, (int, float)):
        return False
    return not (math.isnan(val) or math.isinf(val))


def _extract_exact_bool(val: Any) -> Optional[bool]:
    """Strictly return bool if val is exactly bool, else None."""
    if isinstance(val, bool):
        return val
    return None


def _first_not_none(*values: Any) -> Any:
    """Return the first value that is not None, or None if all are None."""
    for v in values:
        if v is not None:
            return v
    return None


def adapt_comparison_metrics(
    raw_data: Any,
    job_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Transforms arbitrary existing system comparison metrics/results into
    the canonical dictionary contract expected by DeterministicDecisionEngineV1.

    Args:
        raw_data: Can be either:
          - A `results` dictionary containing `video_result`, `audio_result`, etc.
          - A `metrics` or `metrics_snapshot` dictionary built by ComparisonService._build_ai_metrics()
        job_meta: Optional job metadata dictionary (job_name, client_name, comparison_type, etc.)

    Returns:
        Canonical dictionary with keys:
          - video_similarity (Optional[float])
          - duration_difference (Optional[float])
          - is_arpp_slate (Optional[bool])
          - is_binary_duplicate (Optional[bool])
          - audio_mismatch (Optional[bool])
          - no_audio_tracks (Optional[bool])
          - acc_has_audio (Optional[bool])
          - emi_has_audio (Optional[bool])
          - audio_similarity (Optional[float])
          - audio_loudness (Optional[Dict[str, Any]])
          - audio_transcription (Optional[Dict[str, Any]])
          - raw_vad_metrics_complete (Optional[bool])
          - raw_vad_status_acc (Optional[str])
          - raw_vad_status_emi (Optional[str])
          - raw_vad_speech_acc (Optional[bool])
          - raw_vad_speech_emi (Optional[bool])
          - raw_vad_error (Any)
          - raw_vad_inconclusive (Optional[bool])
          - raw_vad_speech (Optional[bool])
          - music_dominant (Optional[bool])
          - job_id, job_name, client_name
    """
    if not isinstance(raw_data, dict):
        return {}

    video_res = raw_data.get("video_result")
    audio_res = raw_data.get("audio_result")
    is_results_dict = isinstance(video_res, dict) or isinstance(audio_res, dict)

    canonical: Dict[str, Any] = {}

    # Metadata extraction
    if job_meta and isinstance(job_meta, dict):
        canonical["job_id"] = job_meta.get("id") or job_meta.get("job_id")
        canonical["job_name"] = job_meta.get("job_name", "")
        canonical["client_name"] = job_meta.get("client_name", "")
    else:
        canonical["job_id"] = raw_data.get("job_id")
        canonical["job_name"] = raw_data.get("job_name", "")
        canonical["client_name"] = raw_data.get("client_name", "")

    # 1. Video metrics
    if is_results_dict and isinstance(video_res, dict):
        raw_vid_sim = video_res.get("overall_similarity")
        raw_dur_diff = video_res.get("duration_difference")
        raw_arpp = video_res.get("is_arpp_slate")
    else:
        raw_vid_sim = raw_data.get("video_similarity")
        if raw_vid_sim is None and "overall_similarity" in raw_data and not is_results_dict:
            raw_vid_sim = raw_data.get("overall_similarity")
        raw_dur_diff = raw_data.get("duration_difference")
        raw_arpp = raw_data.get("is_arpp_slate")

    canonical["video_similarity"] = float(raw_vid_sim) if _is_valid_number(raw_vid_sim) else None
    canonical["duration_difference"] = float(raw_dur_diff) if _is_valid_number(raw_dur_diff) else None
    canonical["is_arpp_slate"] = _extract_exact_bool(raw_arpp)

    # 2. Audio Probe & Status Flags
    audio_source = audio_res if isinstance(audio_res, dict) else raw_data

    canonical["is_binary_duplicate"] = _extract_exact_bool(audio_source.get("is_binary_duplicate"))
    canonical["audio_mismatch"] = _extract_exact_bool(audio_source.get("audio_mismatch"))
    canonical["no_audio_tracks"] = _extract_exact_bool(audio_source.get("no_audio_tracks"))
    canonical["acc_has_audio"] = _extract_exact_bool(audio_source.get("acc_has_audio"))
    canonical["emi_has_audio"] = _extract_exact_bool(audio_source.get("emi_has_audio"))

    # Fallback derivation for older metrics_snapshot where individual track probes were collapsed
    if canonical["acc_has_audio"] is None and canonical["emi_has_audio"] is None:
        if canonical["no_audio_tracks"] is True and canonical["audio_mismatch"] is False:
            canonical["acc_has_audio"] = False
            canonical["emi_has_audio"] = False
        elif (
            canonical["no_audio_tracks"] is False
            and canonical["audio_mismatch"] is False
            and (audio_source.get("has_audio") is True or audio_source.get("audio_pair_comparable") is True)
        ):
            canonical["acc_has_audio"] = True
            canonical["emi_has_audio"] = True

    # 3. Audio Spectral / Similarity
    raw_aud_sim = audio_source.get("similarity_score")
    if raw_aud_sim is None:
        raw_aud_sim = audio_source.get("audio_similarity")
    if raw_aud_sim is None and isinstance(audio_source.get("similarity"), dict):
        raw_aud_sim = audio_source.get("similarity", {}).get("overall_audio_similarity")
    canonical["audio_similarity"] = float(raw_aud_sim) if _is_valid_number(raw_aud_sim) else None

    # 4. Loudness (LUFS)
    loudness_dict = None
    if isinstance(audio_source.get("loudness"), dict):
        loudness_dict = audio_source.get("loudness")
    elif isinstance(raw_data.get("audio_loudness"), dict):
        loudness_dict = raw_data.get("audio_loudness")

    if loudness_dict is not None:
        comp = loudness_dict.get("comparison")
        if isinstance(comp, dict) and "lufs_difference" in comp:
            raw_lufs = comp.get("lufs_difference")
        else:
            raw_lufs = loudness_dict.get("lufs_difference")

        canonical["audio_loudness"] = {
            "lufs_difference": float(raw_lufs) if _is_valid_number(raw_lufs) else None,
            "acceptance_lufs": loudness_dict.get("acceptance", {}).get("integrated_lufs")
            if isinstance(loudness_dict.get("acceptance"), dict)
            else loudness_dict.get("acceptance_lufs"),
            "emission_lufs": loudness_dict.get("emission", {}).get("integrated_lufs")
            if isinstance(loudness_dict.get("emission"), dict)
            else loudness_dict.get("emission_lufs"),
            "has_loudness_issue": _extract_exact_bool(
                loudness_dict.get("has_loudness_differences")
                if "has_loudness_differences" in loudness_dict
                else loudness_dict.get("has_loudness_issue")
            ),
        }
    else:
        canonical["audio_loudness"] = None

    # 5. Speech To Text (STT) Payload
    stt_source = None
    if isinstance(audio_source.get("speech_to_text"), dict):
        stt_source = audio_source.get("speech_to_text")
    elif isinstance(raw_data.get("audio_transcription"), dict):
        stt_source = raw_data.get("audio_transcription")
    elif isinstance(raw_data.get("speech_to_text"), dict):
        stt_source = raw_data.get("speech_to_text")

    if isinstance(stt_source, dict):
        w_a = None
        w_b = None
        comp_data = stt_source.get("comparison")
        if isinstance(comp_data, dict):
            if _is_valid_number(comp_data.get("word_count_a")):
                w_a = int(comp_data.get("word_count_a"))
            if _is_valid_number(comp_data.get("word_count_b")):
                w_b = int(comp_data.get("word_count_b"))

        # Fallback to audio_analysis_data
        if (w_a is None or w_b is None) and isinstance(raw_data.get("audio_analysis_data"), dict):
            stt_analysis = raw_data.get("audio_analysis_data", {}).get("speech_to_text", {})
            if isinstance(stt_analysis, dict):
                comp_analysis = stt_analysis.get("comparison", {})
                if isinstance(comp_analysis, dict):
                    if w_a is None and _is_valid_number(comp_analysis.get("word_count_a")):
                        w_a = int(comp_analysis.get("word_count_a"))
                    if w_b is None and _is_valid_number(comp_analysis.get("word_count_b")):
                        w_b = int(comp_analysis.get("word_count_b"))

        # Fallback to top-level word_count in stt_source
        if w_a is None and _is_valid_number(stt_source.get("word_count_a")):
            w_a = int(stt_source.get("word_count_a"))
        if w_b is None and _is_valid_number(stt_source.get("word_count_b")):
            w_b = int(stt_source.get("word_count_b"))

        raw_sim = stt_source.get("text_similarity")
        canonical["audio_transcription"] = {
            "status": stt_source.get("status"),
            "text_similarity": float(raw_sim) if _is_valid_number(raw_sim) else None,
            "is_text_match": _extract_exact_bool(stt_source.get("is_text_match")),
            "acceptance_text": stt_source.get("acceptance_text", ""),
            "emission_text": stt_source.get("emission_text", ""),
            "is_uncertain": _extract_exact_bool(stt_source.get("is_uncertain")),
            "uncertainty_reason": stt_source.get("uncertainty_reason"),
            "skipped_reason": stt_source.get("skipped_reason"),
            "error_message": stt_source.get("error_message") or stt_source.get("error"),
            "word_count_a": w_a,
            "word_count_b": w_b,
        }
        if "comparison" in stt_source and isinstance(stt_source["comparison"], dict):
            canonical["audio_transcription"]["comparison"] = stt_source["comparison"]
    else:
        canonical["audio_transcription"] = None

    # 6. Raw VAD & Music Dominance
    raw_vad_complete = _extract_exact_bool(
        _first_not_none(audio_source.get("raw_vad_metrics_complete"), raw_data.get("raw_vad_metrics_complete"))
    )
    raw_vad_inconc = _extract_exact_bool(
        _first_not_none(audio_source.get("raw_vad_inconclusive"), raw_data.get("raw_vad_inconclusive"))
    )
    raw_vad_sp = _extract_exact_bool(
        _first_not_none(audio_source.get("raw_vad_speech"), raw_data.get("raw_vad_speech"))
    )
    raw_vad_err = _first_not_none(
        audio_source.get("raw_vad_error"), raw_data.get("raw_vad_error")
    )

    vad_a = audio_source.get("raw_vad_a") if isinstance(audio_source.get("raw_vad_a"), dict) else raw_data.get("raw_vad_a")
    vad_b = audio_source.get("raw_vad_b") if isinstance(audio_source.get("raw_vad_b"), dict) else raw_data.get("raw_vad_b")

    status_acc = _first_not_none(
        (vad_a.get("status") if isinstance(vad_a, dict) else None),
        audio_source.get("raw_vad_status_acc"),
        raw_data.get("raw_vad_status_acc"),
    )
    status_emi = _first_not_none(
        (vad_b.get("status") if isinstance(vad_b, dict) else None),
        audio_source.get("raw_vad_status_emi"),
        raw_data.get("raw_vad_status_emi"),
    )

    speech_acc = _extract_exact_bool(
        _first_not_none(
            (vad_a.get("has_speech") if isinstance(vad_a, dict) else None),
            audio_source.get("raw_vad_speech_acc"),
            raw_data.get("raw_vad_speech_acc"),
        )
    )
    speech_emi = _extract_exact_bool(
        _first_not_none(
            (vad_b.get("has_speech") if isinstance(vad_b, dict) else None),
            audio_source.get("raw_vad_speech_emi"),
            raw_data.get("raw_vad_speech_emi"),
        )
    )

    music_dom = None
    if "music_dominant" in audio_source and _extract_exact_bool(audio_source["music_dominant"]) is not None:
        music_dom = _extract_exact_bool(audio_source["music_dominant"])
    elif "music_dominant" in raw_data and _extract_exact_bool(raw_data["music_dominant"]) is not None:
        music_dom = _extract_exact_bool(raw_data["music_dominant"])
    elif _is_valid_number(audio_source.get("music_proportion")):
        music_dom = float(audio_source.get("music_proportion")) > 0.55
    elif _is_valid_number(raw_data.get("music_proportion")):
        music_dom = float(raw_data.get("music_proportion")) > 0.55

    canonical["raw_vad_metrics_complete"] = raw_vad_complete
    canonical["raw_vad_inconclusive"] = raw_vad_inconc
    canonical["raw_vad_speech"] = raw_vad_sp
    canonical["raw_vad_error"] = raw_vad_err
    canonical["raw_vad_status_acc"] = status_acc
    canonical["raw_vad_status_emi"] = status_emi
    canonical["raw_vad_speech_acc"] = speech_acc
    canonical["raw_vad_speech_emi"] = speech_emi
    canonical["music_dominant"] = music_dom

    return canonical
