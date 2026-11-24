"""
Unit and regression tests for silent audio loudness handling (job 1894 fix):
1. compare_loudness in services/audio_service.py:
   - both sides silent (None or -inf) -> lufs_difference=0.0, both_silent=True, no 'error' key
   - one side silent -> lufs_difference=None, one_side_silent=True, no 'error' key
   - normal loudness -> unchanged numeric lufs_difference, both_silent=False, one_side_silent=False
2. DeterministicMetricsAdapter + DeterministicDecisionEngineV1:
   - both_silent=True with audio_similarity >= 0.98 does not block APPROVE
   - one_side_silent=True forces REVIEW
   - Anonymized fixture of job 1894 (pre-fix error/None vs post-fix both_silent=True, lufs_difference=0.0)
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from services.audio_service import compare_loudness
from services.deterministic_decision_engine import DeterministicDecisionEngineV1
from services.deterministic_metrics_adapter import (
    adapt_comparison_metrics,
    is_metrics_contract_complete,
)


class TestCompareLoudnessSilentHandling:

    def test_both_silent_none_returns_zero_lufs_and_flag(self):
        acc = {"integrated_lufs": None, "true_peak_db": -200.0}
        emi = {"integrated_lufs": None, "true_peak_db": -200.0}

        with patch("services.audio_service.measure_loudness", side_effect=[acc, emi]):
            res = compare_loudness("acc.wav", "emi.wav")

        assert "error" not in res
        assert res["comparison"]["lufs_difference"] == 0.0
        assert res["comparison"]["both_silent"] is True
        assert res["comparison"]["one_side_silent"] is False
        assert res["comparison"]["is_lufs_match"] is True
        assert res["comparison"]["is_peak_match"] is True
        assert res["has_loudness_differences"] is False

    def test_both_silent_neg_inf_returns_zero_lufs_and_flag(self):
        acc = {"integrated_lufs": float("-inf"), "true_peak_db": float("-inf")}
        emi = {"integrated_lufs": float("-inf"), "true_peak_db": float("-inf")}

        with patch("services.audio_service.measure_loudness", side_effect=[acc, emi]):
            res = compare_loudness("acc.wav", "emi.wav")

        assert "error" not in res
        assert res["comparison"]["lufs_difference"] == 0.0
        assert res["comparison"]["both_silent"] is True
        assert res["comparison"]["one_side_silent"] is False
        assert res["comparison"]["is_lufs_match"] is True
        assert res["comparison"]["is_peak_match"] is True
        assert res["has_loudness_differences"] is False

    def test_both_silent_missing_peaks_still_matches(self):
        acc = {"integrated_lufs": None, "true_peak_db": None}
        emi = {"integrated_lufs": None, "true_peak_db": None}

        with patch("services.audio_service.measure_loudness", side_effect=[acc, emi]):
            res = compare_loudness("acc.wav", "emi.wav")

        assert "error" not in res
        assert res["comparison"]["lufs_difference"] == 0.0
        assert res["comparison"]["both_silent"] is True
        assert res["comparison"]["one_side_silent"] is False
        assert res["comparison"]["is_lufs_match"] is True
        assert res["comparison"]["is_peak_match"] is True
        assert res["has_loudness_differences"] is False

    def test_one_side_silent_no_crash_and_sets_flag(self):
        acc = {"integrated_lufs": None, "true_peak_db": -200.0}
        emi = {"integrated_lufs": -23.4, "true_peak_db": -1.2}

        with patch("services.audio_service.measure_loudness", side_effect=[acc, emi]):
            res = compare_loudness("acc.wav", "emi.wav")

        assert "error" not in res
        assert res["comparison"]["lufs_difference"] is None
        assert res["comparison"]["both_silent"] is False
        assert res["comparison"]["one_side_silent"] is True
        assert res["comparison"]["is_lufs_match"] is False

    def test_normal_loudness_unchanged(self):
        acc = {"integrated_lufs": -23.0, "true_peak_db": -1.5}
        emi = {"integrated_lufs": -23.5, "true_peak_db": -1.7}

        with patch("services.audio_service.measure_loudness", side_effect=[acc, emi]):
            res = compare_loudness("acc.wav", "emi.wav")

        assert "error" not in res
        assert res["comparison"]["lufs_difference"] == -0.5
        assert res["comparison"]["both_silent"] is False
        assert res["comparison"]["one_side_silent"] is False
        assert res["comparison"]["is_lufs_match"] is True


class TestSilentAudioAdapterAndEngine:

    def _base_automation_payload(self, loudness_block, stt_block, raw_vad_complete=True):
        return {
            "overall_similarity": 0.998,
            "video_result": {
                "overall_similarity": 0.998,
                "duration_difference": 0.0,
                "is_arpp_slate": False,
            },
            "audio_result": {
                "similarity_score": 0.995,
                "acc_has_audio": True,
                "emi_has_audio": True,
                "audio_mismatch": False,
                "no_audio_tracks": False,
                "is_binary_duplicate": False,
                "loudness": loudness_block,
                "speech_to_text": stt_block,
                "raw_vad_metrics_complete": raw_vad_complete,
                "raw_vad_inconclusive": False if raw_vad_complete else None,
                "raw_vad_speech": False if raw_vad_complete else None,
                "raw_vad_error": None,
                "raw_vad_a": {"status": "no_speech", "has_speech": False} if raw_vad_complete else None,
                "raw_vad_b": {"status": "no_speech", "has_speech": False} if raw_vad_complete else None,
                "music_dominant": None,
                "music_proportion": None,
            },
        }

    def test_both_silent_allows_approve_in_automation(self):
        payload = self._base_automation_payload(
            loudness_block={
                "acceptance": {"integrated_lufs": None, "true_peak_db": -200.0},
                "emission": {"integrated_lufs": None, "true_peak_db": -200.0},
                "comparison": {
                    "lufs_difference": 0.0,
                    "peak_difference_db": 0.0,
                    "is_lufs_match": True,
                    "is_peak_match": True,
                    "both_silent": True,
                    "one_side_silent": False,
                },
                "has_loudness_differences": False,
            },
            stt_block={
                "status": "completed_no_speech",
                "text_similarity": 1.0,
                "is_text_match": True,
                "is_uncertain": False,
                "comparison": {"word_count_a": 0, "word_count_b": 0, "word_differences": []},
            },
        )
        canonical = adapt_comparison_metrics(payload, job_meta={"comparison_type": "automation"})
        complete, flags = is_metrics_contract_complete(canonical)
        assert complete is True
        assert flags["has_lufs"] is True
        assert canonical["audio_loudness"]["both_silent"] is True
        assert canonical["audio_loudness"]["one_side_silent"] is False

        decision = DeterministicDecisionEngineV1().evaluate(canonical)
        assert decision["verdict"] == "approve"

    def test_one_side_silent_forces_review(self):
        payload = self._base_automation_payload(
            loudness_block={
                "acceptance": {"integrated_lufs": None, "true_peak_db": -200.0},
                "emission": {"integrated_lufs": -23.0, "true_peak_db": -1.5},
                "comparison": {
                    "lufs_difference": None,
                    "peak_difference_db": None,
                    "is_lufs_match": False,
                    "is_peak_match": False,
                    "both_silent": False,
                    "one_side_silent": True,
                },
                "has_loudness_differences": True,
            },
            stt_block={
                "status": "completed_no_speech",
                "text_similarity": 1.0,
                "is_text_match": True,
                "is_uncertain": False,
                "comparison": {"word_count_a": 0, "word_count_b": 0, "word_differences": []},
            },
        )
        canonical = adapt_comparison_metrics(payload, job_meta={"comparison_type": "automation"})
        complete, flags = is_metrics_contract_complete(canonical)
        assert complete is True
        assert flags["has_lufs"] is True

        decision = DeterministicDecisionEngineV1().evaluate(canonical)
        assert decision["verdict"] == "review"
        assert any("ciszy" in r.lower() for r in decision["rule_evaluation"]["reasons"])

    def test_job_1894_anonymized_preflight_vs_postfix(self):
        # Pre-fix: compare_loudness crashed -> lufs_difference=None, Raw VAD not populated -> insufficient contract
        preflight_payload = self._base_automation_payload(
            loudness_block={"error": "unsupported format string passed to NoneType.__format__"},
            stt_block={"status": "skipped", "skipped_reason": "SILENCE_NO_SPEECH", "is_uncertain": False},
            raw_vad_complete=False,
        )
        canonical_pre = adapt_comparison_metrics(preflight_payload, job_meta={"comparison_type": "automation"})
        complete_pre, flags_pre = is_metrics_contract_complete(canonical_pre)
        assert complete_pre is False
        assert flags_pre["has_lufs"] is False

        # Post-fix: both_silent=True, lufs_difference=0.0, Raw VAD populated -> APPROVE
        postfix_payload = self._base_automation_payload(
            loudness_block={
                "acceptance": {"integrated_lufs": None, "true_peak_db": -200.0},
                "emission": {"integrated_lufs": None, "true_peak_db": -200.0},
                "comparison": {
                    "lufs_difference": 0.0,
                    "peak_difference_db": 0.0,
                    "is_lufs_match": True,
                    "is_peak_match": True,
                    "both_silent": True,
                    "one_side_silent": False,
                },
                "has_loudness_differences": False,
            },
            stt_block={
                "status": "completed_no_speech",
                "text_similarity": 1.0,
                "is_text_match": True,
                "is_uncertain": False,
                "comparison": {"word_count_a": 0, "word_count_b": 0, "word_differences": []},
            },
            raw_vad_complete=True,
        )
        canonical_post = adapt_comparison_metrics(postfix_payload, job_meta={"comparison_type": "automation"})
        complete_post, flags_post = is_metrics_contract_complete(canonical_post)
        assert complete_post is True
        assert flags_post["has_lufs"] is True
        assert flags_post["has_raw_vad_complete"] is True
        assert DeterministicDecisionEngineV1().evaluate(canonical_post)["verdict"] == "approve"
