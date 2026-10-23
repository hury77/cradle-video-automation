"""
Deterministic Decision Engine v1 for Cradle Video QA Automation.

KEY ARCHITECTURAL PRINCIPLES:
- Completely deterministic, auditable, rule-based QA verdict computation.
- Pure evaluation: NO imports of ollama, AnalystService, main, models.database,
  SQLAlchemy, or web APIs.
- Operates strictly on a metrics dictionary and an optional client_history_count.
- Returns verdict, confidence, reasoning, ai_reasoning, decided_by, rule_evaluation.
"""

from typing import Dict, Any, Optional
import math


# Canonical skipped reasons allowed by system policy
CANONICAL_FAST_PATH_IDENTICAL_AUDIO = "FAST_PATH_IDENTICAL_AUDIO"
CANONICAL_NO_AUDIO_STREAMS = "NO_AUDIO_STREAMS"
CANONICAL_FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH = (
    "FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH"
)
CANONICAL_DUPLICATE_INPUT = "DUPLICATE_INPUT"

ALLOWED_STT_SKIP_REASONS = {
    CANONICAL_FAST_PATH_IDENTICAL_AUDIO,
    CANONICAL_FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH,
}


def _is_valid_number(val: Any) -> bool:
    """Check if value is a finite float or int (not None, NaN, inf, or bool)."""
    if val is None or isinstance(val, bool):
        return False
    if not isinstance(val, (int, float)):
        return False
    return not (math.isnan(val) or math.isinf(val))


def _is_exact_bool(val: Any) -> bool:
    """Check if value is strictly of type bool (not str, int, float, or None)."""
    return isinstance(val, bool)


def _extract_vad_flag(key: str, metrics: Dict[str, Any], stt_payload: Dict[str, Any], audio_data: Dict[str, Any], vad_info: Dict[str, Any]) -> Any:
    """Helper to extract VAD flag from multiple possible payload locations."""
    if key in metrics:
        return metrics[key]
    if key in stt_payload:
        return stt_payload[key]
    if key in vad_info:
        return vad_info[key]
    if key in audio_data:
        return audio_data[key]
    return None


def is_verified_no_speech_result(metrics: Dict[str, Any], stt_payload: Dict[str, Any]) -> bool:
    """
    Validates whether a no-speech STT result (either completed_no_speech or legacy completed with 0 words)
    is strictly and fully proven. Returns True ONLY when:
      - status is 'completed_no_speech' OR ('completed' with explicitly empty text and word_count 0 on both sides)
      - word_count_a == 0 and word_count_b == 0
      - is_uncertain is strictly False
      - audio_mismatch is strictly False
      - is_binary_duplicate is strictly False
      - raw_vad_metrics_complete is strictly True
      - raw_vad_error is False or None
      - raw_vad_inconclusive is strictly False
      - raw_vad_speech is strictly False
      - raw_vad_status_acc and raw_vad_status_emi are strictly 'no_speech'
      - raw_vad_speech_acc and raw_vad_speech_emi are strictly False
      - music_dominant is strictly False
      - when audio_pair_comparable == True: lufs_difference exists, is numeric, and abs <= 3.0
    """
    if not isinstance(metrics, dict) or not isinstance(stt_payload, dict):
        return False

    status = stt_payload.get("status")
    if status == "completed_no_speech":
        pass
    elif status == "completed":
        acc_text = stt_payload.get("acceptance_text", "")
        emi_text = stt_payload.get("emission_text", "")
        if acc_text != "" or emi_text != "":
            return False
    else:
        return False

    # Extract word counts
    w_a = None
    w_b = None
    comp_data = stt_payload.get("comparison")
    if isinstance(comp_data, dict):
        w_a = comp_data.get("word_count_a")
        w_b = comp_data.get("word_count_b")
    if w_a is None:
        w_a = stt_payload.get("word_count_a")
    if w_b is None:
        w_b = stt_payload.get("word_count_b")

    if w_a != 0 or w_b != 0:
        return False

    # is_uncertain must be strictly False
    raw_is_uncertain = stt_payload.get("is_uncertain")
    if raw_is_uncertain is None and "is_uncertain" in metrics:
        raw_is_uncertain = metrics.get("is_uncertain")
    if raw_is_uncertain is not False:
        return False

    # audio_mismatch & is_binary_duplicate must be strictly False
    raw_audio_mismatch = metrics.get("audio_mismatch")
    raw_is_duplicate = metrics.get("is_binary_duplicate")
    if raw_audio_mismatch is not False or raw_is_duplicate is not False:
        return False

    audio_data = metrics.get("audio_analysis_data") if isinstance(metrics.get("audio_analysis_data"), dict) else {}
    vad_info = stt_payload.get("vad_info") if isinstance(stt_payload.get("vad_info"), dict) else {}

    # raw_vad_metrics_complete must be strictly True
    raw_vad_metrics_complete = _extract_vad_flag("raw_vad_metrics_complete", metrics, stt_payload, audio_data, vad_info)
    if raw_vad_metrics_complete is not True:
        return False

    # raw_vad_error must be False or None
    raw_vad_error = _extract_vad_flag("raw_vad_error", metrics, stt_payload, audio_data, vad_info)
    if raw_vad_error not in (False, None):
        return False

    # raw_vad_inconclusive must be strictly False
    raw_vad_inconclusive = _extract_vad_flag("raw_vad_inconclusive", metrics, stt_payload, audio_data, vad_info)
    if raw_vad_inconclusive is not False:
        return False

    # raw_vad_speech must be strictly False
    raw_vad_speech = _extract_vad_flag("raw_vad_speech", metrics, stt_payload, audio_data, vad_info)
    if raw_vad_speech is not False:
        return False

    # music_dominant must be strictly False
    music_dominant = _extract_vad_flag("music_dominant", metrics, stt_payload, audio_data, vad_info)
    if music_dominant is not False:
        return False

    # Side-specific raw_vad_status_acc and raw_vad_status_emi must be strictly "no_speech"
    status_acc = (
        metrics.get("raw_vad_status_acc")
        or stt_payload.get("raw_vad_status_acc")
        or vad_info.get("raw_vad_status_acc")
        or audio_data.get("raw_vad_a", {}).get("status")
    )
    status_emi = (
        metrics.get("raw_vad_status_emi")
        or stt_payload.get("raw_vad_status_emi")
        or vad_info.get("raw_vad_status_emi")
        or audio_data.get("raw_vad_b", {}).get("status")
    )
    if status_acc != "no_speech" or status_emi != "no_speech":
        return False

    # Side-specific raw_vad_speech_acc and raw_vad_speech_emi must be strictly False
    speech_acc = (
        _extract_vad_flag("raw_vad_speech_acc", metrics, stt_payload, audio_data, vad_info)
        if _extract_vad_flag("raw_vad_speech_acc", metrics, stt_payload, audio_data, vad_info) is not None
        else audio_data.get("raw_vad_a", {}).get("has_speech")
    )
    speech_emi = (
        _extract_vad_flag("raw_vad_speech_emi", metrics, stt_payload, audio_data, vad_info)
        if _extract_vad_flag("raw_vad_speech_emi", metrics, stt_payload, audio_data, vad_info) is not None
        else audio_data.get("raw_vad_b", {}).get("has_speech")
    )
    if speech_acc is not False or speech_emi is not False:
        return False

    # Check LUFS if audio pair comparable
    raw_acc_has_audio = metrics.get("acc_has_audio")
    raw_emi_has_audio = metrics.get("emi_has_audio")
    raw_no_audio = metrics.get("no_audio_tracks")

    audio_pair_comparable = (
        raw_acc_has_audio is True
        and raw_emi_has_audio is True
        and raw_audio_mismatch is False
        and raw_no_audio is False
    )
    if audio_pair_comparable:
        audio_loudness = metrics.get("audio_loudness")
        raw_lufs_diff = None
        if isinstance(audio_loudness, dict):
            raw_lufs_diff = audio_loudness.get("lufs_difference")
        elif "lufs_difference" in metrics:
            raw_lufs_diff = metrics.get("lufs_difference")
        if not _is_valid_number(raw_lufs_diff) or abs(float(raw_lufs_diff)) > 3.0:
            return False

    return True


def is_verified_full_no_speech_skip(metrics: Dict[str, Any], stt_payload: Dict[str, Any]) -> bool:
    """
    Validates whether FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH skip is strictly legitimate.
    """
    if not isinstance(metrics, dict) or not isinstance(stt_payload, dict):
        return False

    if stt_payload.get("status") != "skipped":
        return False

    skip_reason = stt_payload.get("skipped_reason") or metrics.get("stt_skipped_reason")
    if skip_reason != CANONICAL_FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH:
        return False

    # Probe & comparable check
    raw_acc_has_audio = metrics.get("acc_has_audio")
    raw_emi_has_audio = metrics.get("emi_has_audio")
    raw_audio_mismatch = metrics.get("audio_mismatch")
    raw_no_audio = metrics.get("no_audio_tracks")

    if not (_is_exact_bool(raw_acc_has_audio) and _is_exact_bool(raw_emi_has_audio) and _is_exact_bool(raw_audio_mismatch) and _is_exact_bool(raw_no_audio)):
        return False

    audio_pair_comparable = (
        raw_acc_has_audio is True
        and raw_emi_has_audio is True
        and raw_audio_mismatch is False
        and raw_no_audio is False
    )
    if not audio_pair_comparable:
        return False

    # Audio similarity check >= 0.75
    raw_audio_sim = metrics.get("audio_similarity")
    if raw_audio_sim is None and isinstance(metrics.get("audio_analysis_data"), dict):
        raw_audio_sim = metrics.get("audio_analysis_data", {}).get("similarity_score")
    if not _is_valid_number(raw_audio_sim) or float(raw_audio_sim) < 0.75:
        return False

    # LUFS check <= 3.0
    audio_loudness = metrics.get("audio_loudness")
    raw_lufs_diff = None
    if isinstance(audio_loudness, dict):
        raw_lufs_diff = audio_loudness.get("lufs_difference")
    elif "lufs_difference" in metrics:
        raw_lufs_diff = metrics.get("lufs_difference")
    if not _is_valid_number(raw_lufs_diff) or abs(float(raw_lufs_diff)) > 3.0:
        return False

    # Uncertainty check
    raw_is_uncertain = stt_payload.get("is_uncertain")
    if raw_is_uncertain is None and "is_uncertain" in metrics:
        raw_is_uncertain = metrics.get("is_uncertain")
    if raw_is_uncertain is not False:
        return False

    audio_data = metrics.get("audio_analysis_data") if isinstance(metrics.get("audio_analysis_data"), dict) else {}
    vad_info = stt_payload.get("vad_info") if isinstance(stt_payload.get("vad_info"), dict) else {}

    raw_vad_metrics_complete = _extract_vad_flag("raw_vad_metrics_complete", metrics, stt_payload, audio_data, vad_info)
    if raw_vad_metrics_complete is not True:
        return False

    raw_vad_error = _extract_vad_flag("raw_vad_error", metrics, stt_payload, audio_data, vad_info)
    if raw_vad_error not in (False, None):
        return False

    raw_vad_inconclusive = _extract_vad_flag("raw_vad_inconclusive", metrics, stt_payload, audio_data, vad_info)
    if raw_vad_inconclusive is not False:
        return False

    music_dominant = _extract_vad_flag("music_dominant", metrics, stt_payload, audio_data, vad_info)
    if music_dominant is not False:
        return False

    raw_vad_speech = _extract_vad_flag("raw_vad_speech", metrics, stt_payload, audio_data, vad_info)
    if raw_vad_speech is not False:
        return False

    status_acc = (
        metrics.get("raw_vad_status_acc")
        or stt_payload.get("raw_vad_status_acc")
        or vad_info.get("raw_vad_status_acc")
        or audio_data.get("raw_vad_a", {}).get("status")
    )
    status_emi = (
        metrics.get("raw_vad_status_emi")
        or stt_payload.get("raw_vad_status_emi")
        or vad_info.get("raw_vad_status_emi")
        or audio_data.get("raw_vad_b", {}).get("status")
    )
    if status_acc != "no_speech" or status_emi != "no_speech":
        return False

    speech_acc = (
        _extract_vad_flag("raw_vad_speech_acc", metrics, stt_payload, audio_data, vad_info)
        if _extract_vad_flag("raw_vad_speech_acc", metrics, stt_payload, audio_data, vad_info) is not None
        else audio_data.get("raw_vad_a", {}).get("has_speech")
    )
    speech_emi = (
        _extract_vad_flag("raw_vad_speech_emi", metrics, stt_payload, audio_data, vad_info)
        if _extract_vad_flag("raw_vad_speech_emi", metrics, stt_payload, audio_data, vad_info) is not None
        else audio_data.get("raw_vad_b", {}).get("has_speech")
    )
    if speech_acc is not False or speech_emi is not False:
        return False

    return True


def is_verified_fast_path_skip(metrics: Dict[str, Any], stt_payload: Dict[str, Any]) -> bool:
    """
    Validates whether FAST_PATH_IDENTICAL_AUDIO skip is strictly legitimate.
    """
    if not isinstance(metrics, dict) or not isinstance(stt_payload, dict):
        return False

    if stt_payload.get("status") != "skipped":
        return False

    skip_reason = stt_payload.get("skipped_reason") or metrics.get("stt_skipped_reason")
    if skip_reason != CANONICAL_FAST_PATH_IDENTICAL_AUDIO:
        return False

    raw_acc_has_audio = metrics.get("acc_has_audio")
    raw_emi_has_audio = metrics.get("emi_has_audio")
    raw_audio_mismatch = metrics.get("audio_mismatch")
    raw_no_audio = metrics.get("no_audio_tracks")
    raw_is_duplicate = metrics.get("is_binary_duplicate")

    if not (_is_exact_bool(raw_acc_has_audio) and _is_exact_bool(raw_emi_has_audio) and _is_exact_bool(raw_audio_mismatch) and _is_exact_bool(raw_no_audio) and _is_exact_bool(raw_is_duplicate)):
        return False

    if raw_is_duplicate is True or raw_audio_mismatch is True or raw_no_audio is True:
        return False

    audio_pair_comparable = (
        raw_acc_has_audio is True
        and raw_emi_has_audio is True
        and raw_audio_mismatch is False
        and raw_no_audio is False
    )
    if not audio_pair_comparable:
        return False

    raw_audio_sim = metrics.get("audio_similarity")
    if raw_audio_sim is None and isinstance(metrics.get("audio_analysis_data"), dict):
        raw_audio_sim = metrics.get("audio_analysis_data", {}).get("similarity_score")
    if not _is_valid_number(raw_audio_sim) or float(raw_audio_sim) < 0.98:
        return False

    audio_loudness = metrics.get("audio_loudness")
    raw_lufs_diff = None
    if isinstance(audio_loudness, dict):
        raw_lufs_diff = audio_loudness.get("lufs_difference")
    elif "lufs_difference" in metrics:
        raw_lufs_diff = metrics.get("lufs_difference")
    if not _is_valid_number(raw_lufs_diff) or abs(float(raw_lufs_diff)) > 3.0:
        return False

    raw_is_uncertain = stt_payload.get("is_uncertain")
    if raw_is_uncertain is None and "is_uncertain" in metrics:
        raw_is_uncertain = metrics.get("is_uncertain")
    if raw_is_uncertain is not False:
        return False

    return True


class DeterministicDecisionEngineV1:
    """
    Deterministic Decision Engine v1 for Cradle QA.
    Evaluates comparison metrics hierarchically:
      1. Guardrails / integrity & strict type validation
      2. Hard REJECT evaluation (highest precedence)
      3. Protective REVIEW evaluation
      4. Qualified APPROVE evaluation
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        policy_cfg = cfg.get("new_client_review_policy", {})
        self.new_client_policy_enabled = bool(policy_cfg.get("enabled", False))
        self.minimum_decisions_before_auto_approve = int(
            policy_cfg.get("minimum_decisions_before_auto_approve", 10)
        )

    def evaluate(
        self,
        metrics: Dict[str, Any],
        client_history_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate comparison metrics and return a deterministic decision.

        Args:
            metrics: Comparison metrics dictionary.
            client_history_count: Optional historical decisions count for client.

        Returns:
            Dict containing verdict, confidence, reasoning, ai_reasoning,
            decided_by, and rule_evaluation.
        """
        if not isinstance(metrics, dict):
            reasoning = "KRYTYCZNY BŁĄD WEJŚCIA: Metryki muszą być słownikiem. Wymuszono status REVIEW."
            return {
                "verdict": "review",
                "confidence": 0.0,
                "reasoning": reasoning,
                "ai_reasoning": reasoning,
                "decided_by": "deterministic_rules_v1",
                "rule_evaluation": {
                    "engine_version": "1.0.0",
                    "fired_rule": "RULE_INVALID_INPUT_METRICS",
                    "precedence_step": "GUARDRAILS_CHECK",
                    "error": "metrics is not a dict",
                },
            }

        type_errors = []

        # ------------------------------------------------------------------
        # 1. STRICT TYPE VALIDATION FOR CRITICAL BOOLEAN FLAGS
        # ------------------------------------------------------------------
        raw_is_binary_duplicate = metrics.get("is_binary_duplicate")
        if not _is_exact_bool(raw_is_binary_duplicate):
            type_errors.append("INVALID_METRIC_TYPE: is_binary_duplicate musi być typu bool")

        raw_audio_mismatch = metrics.get("audio_mismatch")
        if not _is_exact_bool(raw_audio_mismatch):
            type_errors.append("INVALID_METRIC_TYPE: audio_mismatch musi być typu bool")

        raw_no_audio = metrics.get("no_audio_tracks")
        if not _is_exact_bool(raw_no_audio):
            type_errors.append("INVALID_METRIC_TYPE: no_audio_tracks musi być typu bool")

        raw_acc_has_audio = metrics.get("acc_has_audio")
        if not _is_exact_bool(raw_acc_has_audio):
            type_errors.append("INVALID_METRIC_TYPE: acc_has_audio musi być typu bool")

        raw_emi_has_audio = metrics.get("emi_has_audio")
        if not _is_exact_bool(raw_emi_has_audio):
            type_errors.append("INVALID_METRIC_TYPE: emi_has_audio musi być typu bool")

        # Video similarity validation
        raw_video_sim = metrics.get("video_similarity")
        video_similarity_valid = _is_valid_number(raw_video_sim) and (0.0 <= float(raw_video_sim) <= 1.0)
        video_sim = float(raw_video_sim) if video_similarity_valid else None

        # Duration difference validation
        raw_duration_diff = metrics.get("duration_difference")
        duration_diff_valid = _is_valid_number(raw_duration_diff) and (float(raw_duration_diff) >= 0.0)
        duration_diff = float(raw_duration_diff) if duration_diff_valid else None

        # ARPP slate check
        raw_is_arpp = metrics.get("is_arpp_slate")
        is_arpp_slate = True if raw_is_arpp is True else (False if raw_is_arpp is False else None)

        # STT payload extraction
        stt_payload = metrics.get("audio_transcription")
        if not isinstance(stt_payload, dict) and isinstance(metrics.get("speech_to_text"), dict):
            stt_payload = metrics.get("speech_to_text")

        stt_present = isinstance(stt_payload, dict)
        stt_status = None
        stt_skipped_reason = None
        is_text_match = False
        text_sim = None
        text_sim_valid = False
        is_uncertain = False
        word_count_a = None
        word_count_b = None

        if stt_present:
            raw_is_uncertain = stt_payload.get("is_uncertain")
            if raw_is_uncertain is None and "is_uncertain" in metrics:
                raw_is_uncertain = metrics.get("is_uncertain")
            if not _is_exact_bool(raw_is_uncertain):
                type_errors.append("INVALID_METRIC_TYPE: is_uncertain musi być typu bool")
            else:
                is_uncertain = raw_is_uncertain

            stt_status = stt_payload.get("status")
            stt_skipped_reason = stt_payload.get("skipped_reason") or metrics.get("stt_skipped_reason")

            raw_is_text_match = stt_payload.get("is_text_match")
            if _is_exact_bool(raw_is_text_match):
                is_text_match = raw_is_text_match

            raw_text_sim = stt_payload.get("text_similarity")
            if _is_valid_number(raw_text_sim) and (0.0 <= float(raw_text_sim) <= 1.0):
                text_sim_valid = True
                text_sim = float(raw_text_sim)

            # Speech presence details
            comp_data = stt_payload.get("comparison")
            if isinstance(comp_data, dict):
                w_a = comp_data.get("word_count_a")
                w_b = comp_data.get("word_count_b")
                if _is_valid_number(w_a) and int(w_a) >= 0:
                    word_count_a = int(w_a)
                if _is_valid_number(w_b) and int(w_b) >= 0:
                    word_count_b = int(w_b)
            else:
                w_a = stt_payload.get("word_count_a")
                w_b = stt_payload.get("word_count_b")
                if _is_valid_number(w_a) and int(w_a) >= 0:
                    word_count_a = int(w_a)
                if _is_valid_number(w_b) and int(w_b) >= 0:
                    word_count_b = int(w_b)

        # Audio probe & comparable derivation
        audio_probe_complete = (
            _is_exact_bool(raw_acc_has_audio) and _is_exact_bool(raw_emi_has_audio)
        )
        audio_pair_comparable = (
            audio_probe_complete
            and raw_acc_has_audio is True
            and raw_emi_has_audio is True
            and raw_audio_mismatch is False
            and raw_no_audio is False
        )

        # Spectral Audio
        raw_audio_sim = metrics.get("audio_similarity")
        if raw_audio_sim is None and isinstance(metrics.get("audio_analysis_data"), dict):
            raw_audio_sim = metrics.get("audio_analysis_data", {}).get("similarity_score")
        audio_similarity_valid = _is_valid_number(raw_audio_sim) and (0.0 <= float(raw_audio_sim) <= 1.0)
        audio_sim = float(raw_audio_sim) if audio_similarity_valid else None

        # Loudness (LUFS)
        audio_loudness = metrics.get("audio_loudness")
        raw_lufs_diff = None
        if isinstance(audio_loudness, dict):
            raw_lufs_diff = audio_loudness.get("lufs_difference")
        elif "lufs_difference" in metrics:
            raw_lufs_diff = metrics.get("lufs_difference")

        lufs_diff_valid = _is_valid_number(raw_lufs_diff)
        lufs_diff = float(raw_lufs_diff) if lufs_diff_valid else None
        abs_lufs_diff = abs(lufs_diff) if lufs_diff is not None else None

        # ------------------------------------------------------------------
        # 2. EVALUATE HARD REJECT (PREVALENCE OVER REVIEW)
        # ------------------------------------------------------------------
        reject_reasons = []

        # A1: Video similarity < 0.95 (strictly on video_similarity)
        if video_similarity_valid and video_sim < 0.95:
            reject_reasons.append(
                f"Zgodność wideo ({video_sim:.2%}) jest poniżej bezwzględnego progu 95%."
            )

        # A2: Duration difference > 0.5s when is_arpp_slate is verified False
        if duration_diff_valid and duration_diff > 0.5 and is_arpp_slate is False:
            reject_reasons.append(
                f"Pliki różnią się długością o {duration_diff:.2f}s i nie jest to zweryfikowana plansza ARPP/Clearcast."
            )

        # A3: Confirmed VO mismatch
        confirmed_speech = (
            word_count_a is not None
            and word_count_b is not None
            and word_count_a > 0
            and word_count_b > 0
        )
        stt_clean_completed = (
            stt_present
            and stt_status == "completed"
            and "error" not in stt_payload
            and is_uncertain is False
        )

        if confirmed_speech and stt_clean_completed and not is_text_match:
            if text_sim_valid and text_sim < 0.90:
                reject_reasons.append(
                    f"Krytyczna niezgodność ścieżki lektorskiej VO: zgodność tekstu wynosi {text_sim:.2%} (poniżej progu 90%)."
                )

        if reject_reasons:
            reasoning = (
                "🚨 KRYTYCZNA RÓŻNICA (REJECT): "
                + " ".join(reject_reasons)
                + " Końcowy werdykt: REJECT."
            )
            return {
                "verdict": "reject",
                "confidence": 1.0,
                "reasoning": reasoning,
                "ai_reasoning": reasoning,
                "decided_by": "deterministic_rules_v1",
                "rule_evaluation": {
                    "engine_version": "1.0.0",
                    "fired_rule": "RULE_HARD_REJECT",
                    "precedence_step": "HARD_REJECT",
                    "reasons": reject_reasons,
                    "checks": {
                        "video_similarity": video_sim,
                        "duration_difference": duration_diff,
                        "is_arpp_slate": is_arpp_slate,
                        "text_similarity": text_sim,
                        "is_text_match": is_text_match,
                    },
                },
            }

        # ------------------------------------------------------------------
        # 3. EVALUATE PROTECTIVE REVIEW
        # ------------------------------------------------------------------
        review_reasons = []

        # B0: Type validation errors
        if type_errors:
            review_reasons.extend(type_errors)

        # B1: Missing / invalid video similarity
        if not video_similarity_valid:
            review_reasons.append(
                "Brak lub niepoprawna wartość metryki podobieństwa wideo (video_similarity)."
            )

        # B2: Duplicate input
        if raw_is_binary_duplicate is True:
            review_reasons.append(
                "Wykryto identyczność binarną plików wejściowych (DUPLICATE_INPUT) — wymagana weryfikacja poprawności pary."
            )

        # B3: Audio mismatch
        if raw_audio_mismatch is True:
            review_reasons.append(
                "Asymetria ścieżek dźwiękowych: jeden plik posiada audio, a drugi jest całkowicie niemy (AUDIO_MISMATCH)."
            )

        # B4: Unknown/incomplete audio probe
        if not audio_probe_complete:
            review_reasons.append(
                "Niekompletna lub nieznana sonda obecności strumieni audio w plikach."
            )

        # B5: Video in border zone (0.95 <= x < 0.98)
        if video_similarity_valid and (0.95 <= video_sim < 0.98):
            review_reasons.append(
                f"Zgodność wideo ({video_sim:.2%}) znajduje się w strefie granicznej (wymagany próg APPROVE >= 98.0%)."
            )

        # B6: Uncertain or unverified ARPP slate status when duration differs > 0.5s
        if duration_diff_valid and duration_diff > 0.5 and is_arpp_slate is not True:
            review_reasons.append(
                f"Rozbieżność czasu trwania {duration_diff:.2f}s bez jednoznacznie zweryfikowanej planszy ARPP/Clearcast."
            )

        # B7: Audio pair comparable checks (LUFS and Spectral)
        if audio_pair_comparable:
            # LUFS validation
            if not lufs_diff_valid:
                review_reasons.append(
                    "Brakująca, pusta lub nienumeryczna różnica głośności LUFS przy porównywalnym audio."
                )
            elif abs_lufs_diff > 3.0:
                review_reasons.append(
                    f"Różnica głośności |LUFS|={abs_lufs_diff:.2f} dB przekracza dopuszczalny próg tolerancji 3.0 dB."
                )

            # Spectral similarity validation
            if not audio_similarity_valid:
                review_reasons.append(
                    "Brakująca lub nienumeryczna wartość podobieństwa spektralnego audio przy porównywalnym audio."
                )
            elif audio_sim < 0.75:
                review_reasons.append(
                    f"Podobieństwo spektralne audio ({audio_sim:.4f}) spadło poniżej minimalnego progu 0.75."
                )

        # B8: STT Contract checks
        if not stt_present:
            # If both files legitimately have no audio streams, missing STT payload is acceptable (DOOH)
            if not (audio_probe_complete and raw_acc_has_audio is False and raw_emi_has_audio is False):
                review_reasons.append(
                    "Brak wymaganego payloadu analizy mowy (speech_to_text)."
                )
        else:
            if stt_status == "error" or "error" in stt_payload:
                review_reasons.append(
                    f"Błąd potoku Speech-to-Text: {stt_payload.get('error', 'nieznany błąd')}"
                )
            elif stt_status not in ("completed", "completed_no_speech", "skipped"):
                review_reasons.append(
                    f"Nieznany lub niekompletny status potoku Speech-to-Text ('{stt_status}')."
                )
            elif is_uncertain:
                review_reasons.append(
                    "Wykryto flagę niepewności transkrypcji Whisper (is_uncertain=True) — ryzyko artefaktu / halucynacji."
                )
            elif stt_status == "completed":
                if confirmed_speech and not is_text_match:
                    if text_sim_valid and 0.90 <= text_sim < 1.0:
                        review_reasons.append(
                            f"Wykryto drobne różnice w treści lektorskiej: podobieństwo tekstu wynosi {text_sim:.2%} (strefa REVIEW)."
                        )
                # Check legacy no-speech claim
                is_no_speech_claim = (
                    word_count_a == 0
                    and word_count_b == 0
                    and (not stt_payload.get("acceptance_text"))
                    and (not stt_payload.get("emission_text"))
                )
                if is_no_speech_claim:
                    if not is_verified_no_speech_result(metrics, stt_payload):
                        review_reasons.append(
                            "UNVERIFIED_NO_SPEECH_RESULT: Deklarowany brak mowy (completed legacy zero words) "
                            "nie posiada pełnego potwierdzenia (brakujące/niepoprawne metryki Raw VAD, VAD, muzyki lub LUFS)."
                        )
            elif stt_status == "completed_no_speech":
                if not is_verified_no_speech_result(metrics, stt_payload):
                    review_reasons.append(
                        "UNVERIFIED_NO_SPEECH_RESULT: Status completed_no_speech nie posiada pełnego potwierdzenia "
                        "(brakujące/niepoprawne metryki Raw VAD, VAD, muzyki lub LUFS)."
                    )
            elif stt_status == "skipped":
                if stt_skipped_reason == CANONICAL_FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH:
                    if not is_verified_full_no_speech_skip(metrics, stt_payload):
                        review_reasons.append(
                            "UNVERIFIED_FULL_NO_SPEECH_SKIP: Pominięcie transkrypcji FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH "
                            "nie spełnia pełnego zestawu zweryfikowanych warunków (wymagany komplet VAD, LUFS, brak muzyki i brak niepewności)."
                        )
                elif stt_skipped_reason == CANONICAL_FAST_PATH_IDENTICAL_AUDIO:
                    if not is_verified_fast_path_skip(metrics, stt_payload):
                        review_reasons.append(
                            "UNVERIFIED_FAST_PATH_AUDIO_SKIP: Pominięcie transkrypcji FAST_PATH_IDENTICAL_AUDIO "
                            "nie spełnia warunków (wymagane audio_similarity >= 0.98, brak duplicate, brak mismatch, LUFS <= 3.0 i brak niepewności)."
                        )
                else:
                    review_reasons.append(
                        f"Pominięcie transkrypcji ze zweryfikowanym powodem spoza allowlisty: '{stt_skipped_reason}'."
                    )

        # B9: Optional new client policy
        effective_history_count = (
            client_history_count
            if client_history_count is not None
            else metrics.get("client_history_count")
        )
        if self.new_client_policy_enabled:
            count_val = (
                int(effective_history_count)
                if _is_valid_number(effective_history_count)
                else 0
            )
            if count_val < self.minimum_decisions_before_auto_approve:
                review_reasons.append(
                    f"Nowy klient ({count_val} historycznych decyzji, wymagane minimum {self.minimum_decisions_before_auto_approve}) — "
                    "zgodnie z włączoną polityką new_client_review_policy wymagana jest weryfikacja człowieka."
                )

        if review_reasons:
            reasoning = (
                "⚠️ WYMAGANA WERYFIKACJA (REVIEW): "
                + " ".join(review_reasons)
                + " Końcowy werdykt: REVIEW."
            )
            return {
                "verdict": "review",
                "confidence": 0.0,
                "reasoning": reasoning,
                "ai_reasoning": reasoning,
                "decided_by": "deterministic_rules_v1",
                "rule_evaluation": {
                    "engine_version": "1.0.0",
                    "fired_rule": "RULE_PROTECTIVE_REVIEW",
                    "precedence_step": "PROTECTIVE_REVIEW",
                    "reasons": review_reasons,
                    "checks": {
                        "video_similarity": video_sim,
                        "duration_difference": duration_diff,
                        "is_arpp_slate": is_arpp_slate,
                        "audio_pair_comparable": audio_pair_comparable,
                        "audio_similarity": audio_sim,
                        "lufs_difference": lufs_diff,
                        "stt_status": stt_status,
                        "stt_skipped_reason": stt_skipped_reason,
                        "client_history_count": effective_history_count,
                        "new_client_policy_enabled": self.new_client_policy_enabled,
                    },
                },
            }

        # ------------------------------------------------------------------
        # 4. EVALUATE QUALIFIED APPROVE
        # ------------------------------------------------------------------
        parts = []
        diff_count = int(metrics.get("video_differences_count", 0)) if _is_valid_number(metrics.get("video_differences_count")) else 0
        parts.append(
            f"Obraz: zgodny (similarity={video_sim:.4f}, {diff_count} różnych klatek)."
        )

        if is_arpp_slate:
            parts.append("Zweryfikowano format planszy ARPP/Clearcast.")
        else:
            parts.append(f"Długość plików zgodna (różnica {duration_diff:.2f}s).")

        if raw_no_audio is True or (audio_probe_complete and raw_acc_has_audio is False and raw_emi_has_audio is False):
            parts.append("Audio: brak ścieżek dźwiękowych w obu plikach (DOOH/plik niemy — poprawny stan).")
        else:
            if audio_pair_comparable and audio_sim is not None:
                parts.append(f"Audio: zgodne spektralnie (similarity={audio_sim:.4f}).")
            if audio_pair_comparable and lufs_diff is not None:
                parts.append(f"Głośność: OK (|LUFS diff|={abs_lufs_diff:.2f} dB, norma <= 3.0 dB).")

            if stt_present:
                if stt_status == "skipped":
                    parts.append(
                        f"Transkrypcja pominięta na podstawie zweryfikowanej reguły optymalizacyjnej ({stt_skipped_reason})."
                    )
                elif stt_status == "completed_no_speech" or (stt_status == "completed" and word_count_a == 0 and word_count_b == 0 and not stt_payload.get("acceptance_text") and not stt_payload.get("emission_text")):
                    parts.append("Transkrypcja: potwierdzony brak mowy / VO.")
                elif stt_status == "completed" and is_text_match:
                    parts.append(
                        f"Transkrypcja lektora w pełni zgodna (text_similarity={text_sim if text_sim is not None else 1.0:.4f})."
                    )

        reasoning = " ".join(parts) + " Końcowy werdykt: APPROVE."

        return {
            "verdict": "approve",
            "confidence": 1.0,
            "reasoning": reasoning,
            "ai_reasoning": reasoning,
            "decided_by": "deterministic_rules_v1",
            "rule_evaluation": {
                "engine_version": "1.0.0",
                "fired_rule": "RULE_QUALIFIED_APPROVE",
                "precedence_step": "QUALIFIED_APPROVE",
                "checks": {
                    "video_similarity": video_sim,
                    "duration_difference": duration_diff,
                    "is_arpp_slate": is_arpp_slate,
                    "audio_pair_comparable": audio_pair_comparable,
                    "audio_similarity": audio_sim,
                    "lufs_difference": lufs_diff,
                    "stt_status": stt_status,
                    "stt_skipped_reason": stt_skipped_reason,
                    "client_history": {
                        "client_history_count": effective_history_count,
                        "policy_enabled": self.new_client_policy_enabled,
                    },
                },
            },
        }


def get_deterministic_engine(
    config: Optional[Dict[str, Any]] = None,
) -> DeterministicDecisionEngineV1:
    """Factory function for DeterministicDecisionEngineV1."""
    return DeterministicDecisionEngineV1(config=config)
