"""
New Video Compare - Comparison Service
Orchestrates video and audio comparison processing for jobs
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import numpy as np

from .video_processor import VideoProcessor, ProcessingResult
from .audio_processor import AudioProcessor
# OCR removed — visual differences detected by SSIM+pixel diff comparison
from .audio_service import compare_loudness, compare_audio_similarity, compare_audio_full, separate_sources, compare_spoken_text
from utils.logging_utils import log_automation_event

# Database imports
import sys
sys.path.append(str(Path(__file__).parent.parent))
from models.database import SessionLocal
from models.models import (
    ComparisonJob,
    ComparisonResult,
    VideoComparisonResult,
    AudioComparisonResult,
    DifferenceTimestamp,
    JobStatus,
    ComparisonType,
    DifferenceType,
    SeverityLevel,
    SensitivityLevel,
    QADecision,
    DecisionVerdict,
)
from config import get_sensitivity_config

logger = logging.getLogger(__name__)


ALLOWLIST_EXPLICIT_SKIPS = {
    "FAST_PATH_IDENTICAL_AUDIO",
    "NO_AUDIO_STREAMS",
    "FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH",
    "DUPLICATE_INPUT",
}


def extract_normalized_skip_code(raw_skip_reason: Any) -> Optional[str]:
    """
    Extracts and validates the normalized skip reason code against the allowlist.
    Strictly checks the exact token or canonical prefix before ':' or ' -'.
    Rejects loose substrings or unverified prefixes.
    """
    if not raw_skip_reason or not isinstance(raw_skip_reason, str):
        return None
    s = raw_skip_reason.strip()
    if s in ALLOWLIST_EXPLICIT_SKIPS:
        return s
    for sep in (":", " -"):
        if sep in s:
            prefix = s.split(sep, 1)[0].strip()
            if prefix in ALLOWLIST_EXPLICIT_SKIPS:
                return prefix
    if s.startswith("Audio similarity ") and "STT skipped to avoid false positives" in s:
        return "FAST_PATH_IDENTICAL_AUDIO"
    return None


def is_trusted_stt_skip_reason(raw_skip_reason: Any) -> bool:
    """Validates whether an STT skip reason strictly matches an allowlisted canonical reason."""
    return extract_normalized_skip_code(raw_skip_reason) is not None

def check_comp_type(job_type, target_types):
    """Helper to check comparison type robustly (handles String vs Enum vs Mock mismatch)"""
    if not isinstance(target_types, (list, tuple, set)):
        target_types = [target_types]
    if job_type is None:
        return False
    
    def _extract_type_str(x):
        if hasattr(x, "_mock_name") and x._mock_name:
            return str(x._mock_name).lower()
        if hasattr(x, "value") and not hasattr(x.value, "_mock_name"):
            return str(x.value).lower()
        if hasattr(x, "name") and not hasattr(x.name, "_mock_name"):
            return str(x.name).lower()
        return str(x).lower()

    job_str = _extract_type_str(job_type)
    for t in target_types:
        if job_type is t:
            return True
        t_str = _extract_type_str(t)
        if job_str == t_str:
            return True
        for canonical in ("full", "audio_only", "video_only", "vo_transcript", "automation"):
            if canonical in job_str and canonical in t_str:
                return True
    return False


def is_valid_no_audio_streams_skip(audio_res: dict) -> bool:
    """
    Validates whether NO_AUDIO_STREAMS skip is strictly legitimate:
    Both files must have zero audio tracks. Audio mismatch or any audio stream strictly disqualifies skip.
    """
    if not isinstance(audio_res, dict):
        return False
    if audio_res.get("audio_mismatch") is True:
        return False
    if audio_res.get("has_audio_any") is True:
        return False
    if audio_res.get("acc_has_audio") is True or audio_res.get("emi_has_audio") is True:
        return False
    return bool(audio_res.get("no_audio_tracks"))


def is_valid_fast_path_audio_skip(comp_type, audio_res: dict) -> bool:
    """
    Strict validation for FAST_PATH_IDENTICAL_AUDIO:
    Must NOT be VO_TRANSCRIPT mode, must NOT have audio_mismatch,
    must NOT be DUPLICATE_INPUT in FULL or AUTOMATION mode,
    must have actual audio similarity score >= 0.98, and no loudness differences.
    """
    if not isinstance(audio_res, dict):
        return False
    if check_comp_type(comp_type, ComparisonType.VO_TRANSCRIPT):
        return False
    if audio_res.get("is_binary_duplicate") is True and check_comp_type(comp_type, [ComparisonType.FULL, ComparisonType.AUTOMATION]):
        return False
    if audio_res.get("audio_mismatch") is True:
        return False
    if audio_res.get("no_audio_tracks") is True:
        return False
    sim_score = audio_res.get("similarity_score")
    if sim_score is None:
        return False
    try:
        if float(sim_score) < 0.98:
            return False
    except (ValueError, TypeError):
        return False
    if audio_res.get("loudness", {}).get("has_loudness_differences", False):
        return False
    return True


def is_valid_full_stt_skip(comp_type, audio_res: dict) -> bool:
    """
    Strict validation for FULL mode STT skip:
    Requires matching LUFS, music_proportion <= 0.55, explicit raw_vad_status == 'no_speech',
    complete metrics for both files, no VAD errors/uncertainty, and no audio mismatch.
    """
    if not isinstance(audio_res, dict):
        return False
    if not check_comp_type(comp_type, ComparisonType.FULL):
        return False
    if audio_res.get("audio_mismatch") is True:
        return False
    if audio_res.get("loudness", {}).get("has_loudness_differences", False):
        return False
    if audio_res.get("music_proportion", 0.0) > 0.55:
        return False
    if audio_res.get("raw_vad_status") != "no_speech":
        return False
    if audio_res.get("raw_vad_speech") is not False:
        return False
    if audio_res.get("raw_vad_inconclusive") is True:
        return False
    if audio_res.get("raw_vad_error") is not None:
        return False

    vad_a = audio_res.get("raw_vad_a")
    vad_b = audio_res.get("raw_vad_b")
    metrics_complete = audio_res.get("raw_vad_metrics_complete")

    if vad_a is not None and vad_b is not None:
        a_ok = (
            isinstance(vad_a, dict)
            and vad_a.get("status") == "no_speech"
            and vad_a.get("has_speech") is False
            and vad_a.get("error") is None
            and isinstance(vad_a.get("speech_duration_s"), (int, float))
            and isinstance(vad_a.get("segments_count"), int)
        )
        b_ok = (
            isinstance(vad_b, dict)
            and vad_b.get("status") == "no_speech"
            and vad_b.get("has_speech") is False
            and vad_b.get("error") is None
            and isinstance(vad_b.get("speech_duration_s"), (int, float))
            and isinstance(vad_b.get("segments_count"), int)
        )
        return a_ok and b_ok and (metrics_complete is not False)
    return metrics_complete is True


class ComparisonService:
    """
    Main comparison service that orchestrates video and audio comparison
    """

    def __init__(self, temp_dir: Optional[str] = None):
        """Initialize comparison service with processors"""
        self.video_processor = VideoProcessor(temp_dir=temp_dir)
        self.audio_processor = AudioProcessor()
        logger.info("🔧 ComparisonService initialized")

    compare_files = None  # Alias set below

    def process_job(self, job_id: int) -> Dict[str, Any]:
        """
        Process a comparison job (synchronous for prototype)
        
        Args:
            job_id: ID of the comparison job to process
            
        Returns:
            Dict with processing results
        """
        logger.info(f"🚀 Starting comparison job {job_id}")
        
        db = SessionLocal()
        try:
            # Get job from database
            job = db.query(ComparisonJob).filter(ComparisonJob.id == job_id).first()
            if not job:
                logger.error(f"Job {job_id} not found")
                return {"success": False, "error": "Job not found"}

            # Update job status to processing
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now(timezone.utc)
            job.progress = 0.0
            db.commit()

            # Log job start
            log_automation_event(
                db=db,
                component="backend",
                action="JOB_START",
                message=f"Started comparison job: {job.job_name}",
                cradle_id=job.cradle_id,
                is_error=False,
                details={"job_id": job_id, "comparison_type": str(job.comparison_type.value)}
            )

            # Get file paths
            acceptance_path = job.acceptance_file.file_path
            emission_path = job.emission_file.file_path
            
            # Ensure absolute paths
            # Ensure absolute paths (with fallback logic)
            if not Path(acceptance_path).is_absolute():
                # Try backend-relative first (legacy)
                backend_rel = Path(__file__).parent.parent / acceptance_path
                if backend_rel.exists():
                    acceptance_path = str(backend_rel.resolve())
                else:
                    # Try CWD-relative (modern/root uploads)
                    cwd_rel = Path(acceptance_path)
                    if cwd_rel.exists():
                         acceptance_path = str(cwd_rel.resolve())
                    else:
                         acceptance_path = str(backend_rel.resolve()) # Default to what it was, to fail explicitly usually

            if not Path(emission_path).is_absolute():
                # Try backend-relative first (legacy)
                backend_rel = Path(__file__).parent.parent / emission_path
                if backend_rel.exists():
                    emission_path = str(backend_rel.resolve())
                else:
                    # Try CWD-relative (modern/root uploads)
                    cwd_rel = Path(emission_path)
                    if cwd_rel.exists():
                         emission_path = str(cwd_rel.resolve())
                    else:
                         emission_path = str(backend_rel.resolve())

            logger.info(f"📄 Acceptance: {acceptance_path}")
            logger.info(f"📄 Emission: {emission_path}")

            # Get sensitivity configuration
            sensitivity = job.sensitivity_level.value if job.sensitivity_level else "medium"
            logger.info(f"🎚️ Sensitivity Level: {sensitivity}")

            # Use robust module-level check_comp_type helper

            results = {
                "video_result": None,
                "audio_result": None,
                "success": True,
            }
            
            # Define sensitivity-based processing defaults
            fps_map = {
                "low": 3.0,      # Zwiększone z 1.0 dla lepszej precyzji czasowej
                "medium": 2.0,   # 2 frames/sec
                "high": 5.0,     # 5 frames/sec (Detailed check)
                "automation": 5.0  # Same as HIGH
            }
            max_frames_map = {
                "low": 1800,     # Dopasowane do FPS 3.0 (~10 minut)
                "medium": 900,
                "high": 3000,
                "automation": 3000  # Same as HIGH
            }
            threshold_map = {
                "low": 0.97,     # High ma 0.99, Low 0.97 dla mniejszej rygorystyczności Match Ratio
                "medium": 0.98,
                "high": 0.99,      # Extremely strict
                "automation": 0.99  # Same as HIGH (User requirement)
            }
            
            
            # Allow ComparisonType to OVERRIDE sensitivity defaults
            effective_sensitivity = sensitivity.lower()
            if check_comp_type(job.comparison_type, ComparisonType.AUTOMATION):
                 effective_sensitivity = "automation"
                 logger.info(f"⚙️ Comparison Type AUTOMATION overrides sensitivity to: automation")

            target_fps = fps_map.get(effective_sensitivity, 1.0)
            target_max_frames = max_frames_map.get(effective_sensitivity, 300)
            target_threshold = threshold_map.get(effective_sensitivity, 0.95)

            # Processing config - Merge defaults with job config, but enforce sensitivity FPS
            base_config = job.processing_config or {}
            processing_config = {
                "analysis_fps": target_fps,
                "max_frames": target_max_frames,
                "similarity_threshold": target_threshold,
                **base_config  # Keep other settings from job config
            }
            # Enforce FPS and Max Frames again to override any stale job config (e.g. from re-analyze copy)
            # Also enforce threshold if not explicitly overridden by "custom" (which we assume isn't set yet)
            # Actually, let's prefer sensitivity defaults unless base_config has it EXPLICITLY set? 
            # Re-analyze copies old config, so it HAS threshold: 0.95. We must OVERRIDE it for High Sensitivity fix.
            processing_config["analysis_fps"] = target_fps
            processing_config["max_frames"] = target_max_frames
            processing_config["similarity_threshold"] = target_threshold
            
            logger.info(f"⚙️ Analysis Config: {processing_config['analysis_fps']} FPS, {processing_config['max_frames']} Frames Max")
            
            sensitivity_config = get_sensitivity_config(sensitivity)

            # Merge sensitivity thresholds into processing_config so video_processor can use them
            processing_config["pixel_diff_tolerance"] = sensitivity_config.get("pixel_diff_tolerance", 0.05)
            processing_config["ssim_min"] = sensitivity_config.get("ssim_min", 0.92)
            logger.info(f"⚙️ Sensitivity '{sensitivity}': pixel_diff_tolerance={processing_config['pixel_diff_tolerance']:.0%}, ssim_min={processing_config['ssim_min']}")

            # Normalize comparison type check
            logger.info(f"🔎 Checking Comparison Type: {job.comparison_type} (Type: {type(job.comparison_type)})")
            
            # 1. Video Comparison
            if check_comp_type(job.comparison_type, [ComparisonType.FULL, ComparisonType.VIDEO_ONLY, ComparisonType.AUTOMATION, ComparisonType.VO_TRANSCRIPT]):
                logger.info("🎬 Starting video comparison logic...")
                job.progress = 10.0
                db.commit()
                
                log_automation_event(
                    db=db,
                    component="backend",
                    action="VIDEO_START",
                    message="Starting video analysis phase",
                    cradle_id=job.cradle_id,
                    is_error=False
                )
                
                try:
                    video_result = self.video_processor.process_comparison(
                        job_id=job_id,
                        acceptance_file=acceptance_path,
                        emission_file=emission_path,
                        processing_config=processing_config,
                    )
                    
                    if video_result and video_result.error_message:
                        logger.error(f"❌ Video comparison reported an error: {video_result.error_message}")
                        raise Exception(f"Video processing failed: {video_result.error_message}")
                        
                    logger.info(f"💾 Video Result Obtained: {video_result}")
                    results["video_result"] = video_result

                    log_automation_event(
                        db=db,
                        component="backend",
                        action="VIDEO_COMPLETE",
                        message=f"Video analysis complete. Similarity: {video_result.overall_similarity:.2%}",
                        cradle_id=job.cradle_id,
                        is_error=False,
                        details={
                            "similarity": video_result.overall_similarity,
                            "diff_frames": video_result.frames_with_differences
                        }
                    )
                except Exception as e:
                    logger.error(f"❌ CRITICAL ERROR in video comparison: {e}", exc_info=True)
                    # Re-raise to trigger job failure
                    raise Exception(str(e))

                # MEMORY CLEANUP after video phase
                logger.info("🧹 Releasing video memory before audio phase...")
                import gc
                gc.collect()
            else:
                logger.warning(f"⚠️ Skipping video comparison (Type mismatch: {job.comparison_type})")

            # 2. Audio Comparison
            if check_comp_type(job.comparison_type, [ComparisonType.FULL, ComparisonType.AUDIO_ONLY, ComparisonType.AUTOMATION, ComparisonType.VO_TRANSCRIPT]):
                logger.info("🔊 Starting audio comparison...")
                job.progress = 65.0
                db.commit()

                log_automation_event(
                    db=db,
                    component="backend",
                    action="AUDIO_START",
                    message="Starting audio analysis phase",
                    cradle_id=job.cradle_id,
                    is_error=False
                )
                
                # Determine ARPP/Clearcast slate logic based on duration diff for audio offset alignment
                is_arpp_slate = False
                duration_difference = 0.0
                start_time_acc = None
                start_time_emi = None
                audio_duration = None

                dur_acc = 0.0
                dur_emi = 0.0

                if video_result:
                    # Reading from serializable dict or object
                    if isinstance(video_result, dict):
                        acc_meta = video_result.get("acceptance_metadata")
                        emi_meta = video_result.get("emission_metadata")
                        dur_acc = acc_meta.get("duration", 0.0) if acc_meta else 0.0
                        dur_emi = emi_meta.get("duration", 0.0) if emi_meta else 0.0
                    else:
                        dur_acc = getattr(video_result.acceptance_metadata, "duration", 0.0) if getattr(video_result, "acceptance_metadata", None) else 0.0
                        dur_emi = getattr(video_result.emission_metadata, "duration", 0.0) if getattr(video_result, "emission_metadata", None) else 0.0
                
                if dur_acc <= 0 or dur_emi <= 0:
                    try:
                        acc_meta = self.video_processor.ffmpeg.get_video_metadata(acceptance_path)
                        emi_meta = self.video_processor.ffmpeg.get_video_metadata(emission_path)
                        dur_acc = acc_meta.duration
                        dur_emi = emi_meta.duration
                    except Exception as probe_e:
                        logger.warning(f"Failed to probe durations for audio offset: {probe_e}")

                if dur_acc > 0 and dur_emi > 0:
                    duration_difference = abs(dur_acc - dur_emi)
                    if 10.5 <= duration_difference <= 11.5:
                        is_arpp_slate = True
                        logger.info(f"⚠️ Detected ARPP/Clearcast slate in audio phase. Applying offsets: acc={10.0 if dur_acc > dur_emi else 0.0}s, emi={10.0 if dur_emi > dur_acc else 0.0}s")
                        if dur_acc > dur_emi:
                            start_time_acc = 10.0
                            start_time_emi = 0.0
                            audio_duration = dur_emi - 1.0  # Cut the 1s black at the end
                        else:
                            start_time_acc = 0.0
                            start_time_emi = 10.0
                            audio_duration = dur_acc - 1.0
                    elif 9.5 <= duration_difference <= 10.5:
                        is_arpp_slate = True  # Reuse same flag — drives same downstream logic (APPROVE, no duration REJECT)
                        logger.info(f"⚠️ Detected Clearcast slate (~10s) in audio phase. Applying offsets: acc={10.0 if dur_acc > dur_emi else 0.0}s, emi={10.0 if dur_emi > dur_acc else 0.0}s")
                        if dur_acc > dur_emi:
                            start_time_acc = 10.0
                            start_time_emi = 0.0
                            audio_duration = dur_emi  # No trailing black cut for Clearcast
                        else:
                            start_time_acc = 0.0
                            start_time_emi = 10.0
                            audio_duration = dur_acc  # No trailing black cut for Clearcast

                audio_result = {}
                
                # ── PRIORITY 1: Check binary identity (DUPLICATE_INPUT) ──
                from services.audio_service import get_audio_stream_count, compute_file_sha256, detect_raw_audio_speech
                is_binary_duplicate = False
                try:
                    sha_acc = compute_file_sha256(Path(acceptance_path))
                    sha_emi = compute_file_sha256(Path(emission_path))
                    if sha_acc == sha_emi:
                        is_binary_duplicate = True
                        logger.warning(f"🚨 DUPLICATE_INPUT detected in comparison: Acceptance and Emission have identical SHA256 ({sha_acc[:16]}...)")
                except Exception as sha_err:
                    logger.warning(f"Could not compute input SHA256: {sha_err}")

                # Probe audio streams
                acc_audio_streams = 0
                emi_audio_streams = 0
                try:
                    acc_audio_streams = get_audio_stream_count(Path(acceptance_path))
                    emi_audio_streams = get_audio_stream_count(Path(emission_path))
                except Exception as probe_audio_e:
                    logger.warning(f"Could not probe audio streams: {probe_audio_e}")

                acc_has_audio = acc_audio_streams > 0
                emi_has_audio = emi_audio_streams > 0
                has_audio_any = acc_has_audio or emi_has_audio
                audio_pair_comparable = acc_has_audio and emi_has_audio
                no_audio_tracks = not has_audio_any
                audio_mismatch = acc_has_audio != emi_has_audio

                audio_result["acc_has_audio"] = acc_has_audio
                audio_result["emi_has_audio"] = emi_has_audio
                audio_result["has_audio_any"] = has_audio_any
                audio_result["audio_pair_comparable"] = audio_pair_comparable
                audio_result["no_audio_tracks"] = no_audio_tracks
                audio_result["audio_mismatch"] = audio_mismatch
                audio_result["is_binary_duplicate"] = is_binary_duplicate

                if is_binary_duplicate and check_comp_type(job.comparison_type, [ComparisonType.FULL, ComparisonType.AUTOMATION]):
                    # FULL and AUTOMATION modes: binary duplicate inputs MUST trigger DUPLICATE_INPUT, skip STT, and force REVIEW
                    logger.warning(f"🚨 {job.comparison_type} mode duplicate inputs: Setting DUPLICATE_INPUT status and forcing REVIEW.")
                    audio_result["has_audio"] = audio_pair_comparable
                    audio_result["similarity_score"] = 1.0
                    audio_result["speech_to_text"] = {
                        "status": "skipped",
                        "text_similarity": None,
                        "is_text_match": None,
                        "skipped_reason": "DUPLICATE_INPUT: Acceptance and Emission are binary identical files (possible duplicate download)",
                        "is_uncertain": True,
                        "uncertainty_reason": "DUPLICATE_INPUT: Identical binary files detected; requires verification of download integrity",
                    }
                    results["audio_result"] = audio_result
                elif no_audio_tracks:
                    logger.info("🔇 No audio streams found in both files (silent video / GIF). Skipping audio comparison.")
                    audio_result["has_audio"] = False
                    audio_result["similarity_score"] = 1.0
                    audio_result["audio_comparison_skipped"] = True
                    audio_result["skip_reason"] = "NO_AUDIO_STREAMS: No audio tracks present in both source files"
                    audio_result["message"] = "Files are identical in audio (both are silent)"
                    results["audio_result"] = audio_result
                elif audio_mismatch:
                    logger.warning("⚠️ Audio stream mismatch: One file has audio tracks, the other has none.")
                    audio_result["has_audio"] = False
                    audio_result["similarity_score"] = 0.0
                    audio_result["audio_comparison_skipped"] = True
                    audio_result["skip_reason"] = "AUDIO_MISMATCH: One file contains audio, but the other has no audio streams."
                    results["audio_result"] = audio_result
                else:
                    audio_result["has_audio"] = True
                    # LUFS Loudness comparison (new)
                    try:
                        logger.info("📊 Measuring LUFS loudness levels...")
                        loudness_result = compare_loudness(
                            acceptance_path, 
                            emission_path,
                            start_time_acc=start_time_acc,
                            start_time_emi=start_time_emi,
                            duration=audio_duration
                        )
                        audio_result["loudness"] = loudness_result
                    except Exception as lufs_err:
                        logger.warning(f"LUFS comparison failed: {lufs_err}")
                        audio_result["loudness"] = {"error": str(lufs_err)}
                    
                    job.progress = 75.0
                    db.commit()
                    
                    # Audio similarity (MFCC-based)
                    try:
                        logger.info("🎼 Computing audio similarity...")
                        similarity_result = compare_audio_similarity(
                            acceptance_path, 
                            emission_path,
                            start_time_acc=start_time_acc,
                            start_time_emi=start_time_emi,
                            duration=audio_duration
                        )
                        audio_result["similarity"] = similarity_result
                        audio_result["similarity_score"] = similarity_result.get("overall_audio_similarity", 0.0)
                    except Exception as sim_err:
                        logger.warning(f"Audio similarity failed: {sim_err}")
                        audio_result["similarity"] = {"error": str(sim_err)}
                        audio_result["similarity_score"] = 0.0
                    
                    # Legacy audio processor (spectral comparison)
                    try:
                        legacy_result = self.audio_processor.compare_audio_files(
                            video_path1=acceptance_path,
                            video_path2=emission_path,
                            sync_audio=True,
                            start_time1=start_time_acc,
                            start_time2=start_time_emi,
                            duration=audio_duration
                        )
                        audio_result["spectral"] = legacy_result
                    except Exception as audio_err:
                        logger.warning(f"Spectral audio comparison failed: {audio_err}")
                        audio_result["spectral"] = {"error": str(audio_err)}
                
                job.progress = 80.0
                db.commit()
                
                # Extended Audio Analysis (Demucs + Whisper)
                # Runs for: AUDIO_ONLY and AUTOMATION only.
                # NOTE: FULL+HIGH was added in bdf5231 but caused OOM crashes on 16 GB M4
                # because Demucs(MPS) + MLX Whisper + Ollama all compete for the same Unified Memory.
                # FULL jobs get audio similarity score via MFCC — Ollama uses it for verdict.
                # Check Raw VAD on mixed audio if both files have audio and mode is FULL
                raw_vad_speech = False
                raw_vad_inconclusive = False
                raw_vad_status = None
                raw_vad_metrics_complete = False
                vad_a = None
                vad_b = None

                if check_comp_type(job.comparison_type, ComparisonType.FULL) and audio_result.get("audio_pair_comparable"):
                    try:
                        vad_a = detect_raw_audio_speech(acceptance_path)
                        vad_b = detect_raw_audio_speech(emission_path)
                        audio_result["raw_vad_a"] = vad_a
                        audio_result["raw_vad_b"] = vad_b

                        def _is_valid_vad_dict(v: Any) -> Tuple[bool, bool, bool]:
                            if not isinstance(v, dict):
                                return False, False, False
                            st = v.get("status")
                            err = v.get("error")
                            has_sp = v.get("has_speech")
                            dur = v.get("speech_duration_s")
                            segs = v.get("segments_count")
                            if err is not None:
                                return False, False, False
                            if not isinstance(dur, (int, float)) or not isinstance(segs, int):
                                return False, False, False
                            if st == "speech_detected" and has_sp is True:
                                return True, True, False
                            if st == "no_speech" and has_sp is False:
                                return True, False, True
                            return False, False, False

                        valid_a, sp_a, no_sp_a = _is_valid_vad_dict(vad_a)
                        valid_b, sp_b, no_sp_b = _is_valid_vad_dict(vad_b)

                        if not valid_a or not valid_b:
                            raw_vad_inconclusive = True
                            raw_vad_metrics_complete = False
                            if (isinstance(vad_a, dict) and vad_a.get("status") == "error") or (isinstance(vad_b, dict) and vad_b.get("status") == "error"):
                                raw_vad_status = "error"
                            elif (isinstance(vad_a, dict) and vad_a.get("status") == "uncertain") or (isinstance(vad_b, dict) and vad_b.get("status") == "uncertain"):
                                raw_vad_status = "uncertain"
                            else:
                                raw_vad_status = "uncertain"
                        else:
                            raw_vad_metrics_complete = True
                            if sp_a or sp_b:
                                raw_vad_speech = True
                                raw_vad_status = "speech_detected"
                            elif no_sp_a and no_sp_b:
                                raw_vad_speech = False
                                raw_vad_status = "no_speech"
                    except Exception as vad_err:
                        logger.warning(f"Raw VAD check encountered error: {vad_err}")
                        raw_vad_inconclusive = True
                        raw_vad_metrics_complete = False
                        raw_vad_status = "error"
                        audio_result["raw_vad_error"] = str(vad_err)

                audio_result["raw_vad_speech"] = raw_vad_speech
                audio_result["raw_vad_inconclusive"] = raw_vad_inconclusive
                audio_result["raw_vad_status"] = raw_vad_status
                audio_result["raw_vad_metrics_complete"] = raw_vad_metrics_complete

                loudness_match_issue = audio_result.get("loudness", {}).get("has_loudness_differences", False)
                audio_mismatch_issue = audio_result.get("audio_mismatch", False)
                has_duplicate_skip = (audio_result.get("is_binary_duplicate") and check_comp_type(job.comparison_type, [ComparisonType.FULL, ComparisonType.AUTOMATION]))

                # STT Decision Gate
                is_vo_mode = check_comp_type(job.comparison_type, ComparisonType.VO_TRANSCRIPT)
                is_auto_mode = check_comp_type(job.comparison_type, ComparisonType.AUTOMATION)
                is_audio_mode = check_comp_type(job.comparison_type, ComparisonType.AUDIO_ONLY)
                is_full_mode = check_comp_type(job.comparison_type, ComparisonType.FULL)

                if has_duplicate_skip and not is_vo_mode:
                    should_run_stt = False
                else:
                    music_dominance = audio_result.get("music_proportion", 0.0) > 0.55
                    should_run_stt = audio_result.get("has_audio_any", True) and not audio_result.get("no_audio_tracks", False) and (
                        is_audio_mode
                        or is_auto_mode
                        or is_vo_mode
                        or audio_mismatch_issue
                        or (is_full_mode and (loudness_match_issue or raw_vad_speech or raw_vad_inconclusive or music_dominance))
                    )
                if should_run_stt:
                    mode_label = "VO_TRANSCRIPT" if check_comp_type(job.comparison_type, ComparisonType.VO_TRANSCRIPT) else ("AUTOMATION" if check_comp_type(job.comparison_type, ComparisonType.AUTOMATION) else effective_sensitivity.upper())
                    logger.info(f"🎧 {mode_label} Mode: Running enhanced analysis (Demucs + Whisper)...")
                    
                    import gc
                    gc.collect()
                    
                    try:
                        logger.info("🎙️ Running Speech-to-Text pipeline (independent per file)...")
                        
                        should_filter_song = effective_sensitivity in ["high", "automation"]
                        
                        # Fix: Force STT if loudness differences were detected, even if spectral similarity is high
                        force_stt = loudness_match_issue or check_comp_type(job.comparison_type, ComparisonType.VO_TRANSCRIPT)
                        
                        stt_result = compare_spoken_text(
                            acceptance_path,
                            emission_path,
                            use_separated_vocals=True,
                            filter_song=should_filter_song,
                            audio_similarity_score=audio_result.get("similarity_score"),
                            force_stt=force_stt,
                            initial_prompt=job.client_name,
                            start_time_acc=start_time_acc,
                            start_time_emi=start_time_emi,
                            duration=audio_duration
                        )
                        
                        if stt_result and stt_result.get("error"):
                             logger.error(f"❌ Audio STT reported an error: {stt_result.get('error')}")
                             # Note: WE DON'T FAIL THE WHOLE JOB for STT errors yet as they can be flaky
                        
                        # Extract pipeline info
                        pipeline_info = stt_result.get("pipeline_info", {})
                        audio_result["source_separation"] = {
                            "acceptance": pipeline_info.get("acceptance_separation"),
                            "emission": pipeline_info.get("emission_separation"),
                        }
                        
                        audio_result["speech_to_text"] = {
                            "text_similarity": stt_result.get("text_similarity"),
                            "is_text_match": stt_result.get("is_text_match"),
                            "comparison": stt_result.get("comparison"),
                            "acceptance_text": stt_result.get("transcript_acceptance", {}).get("text", "")[:500],
                            "emission_text": stt_result.get("transcript_emission", {}).get("text", "")[:500],
                            "detected_language": stt_result.get("detected_language"),
                            "timeline_data": {
                                "acceptance_segments": stt_result.get("transcript_acceptance", {}).get("segments", []),
                                "emission_segments": stt_result.get("transcript_emission", {}).get("segments", []),
                            },
                            "status": stt_result.get("status", "completed"),
                            "skipped_reason": stt_result.get("skipped_reason"),
                            "error_message": stt_result.get("error_message"),
                        }
                        audio_result["voiceover"] = stt_result.get("voiceover")
                        
                        _sim_disp = stt_result.get('text_similarity')
                        _sim_disp_str = f"{_sim_disp:.1%}" if isinstance(_sim_disp, (int, float)) else "N/A"
                        logger.info(f"✅ Speech-to-Text complete: {_sim_disp_str} match")
                        
                        log_automation_event(
                            db=db,
                            component="backend",
                            action="AUDIO_COMPLETE",
                            message=f"Audio analysis complete. Similarity: {audio_result.get('similarity_score', 0):.2%}",
                            cradle_id=job.cradle_id,
                            is_error=False,
                            details={
                                "similarity": audio_result.get("similarity_score"),
                                "stt_match": stt_result.get("text_similarity")
                            }
                        )
                        
                    except Exception as stt_err:
                        logger.warning(f"Speech-to-Text pipeline failed: {stt_err}")
                        audio_result["speech_to_text"] = {"error": str(stt_err)}
                        # Fail job if audio comparison is CRITICAL for this job type
                        if check_comp_type(job.comparison_type, ComparisonType.AUDIO_ONLY):
                             raise Exception(f"Audio processing failed: {str(stt_err)}")

                results["audio_result"] = audio_result
                job.progress = 90.0
                db.commit()

            # Save results to database
            self._save_results(db, job, results)

            # Update job status to completed
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.progress = 100.0
            
            # Calculate duration
            if job.started_at:
                try:
                    start = job.started_at
                    end = job.completed_at
                    
                    if start and end:
                        if start.tzinfo is not None and end.tzinfo is None:
                            start = start.replace(tzinfo=None)
                        elif start.tzinfo is None and end.tzinfo is not None:
                            end = end.replace(tzinfo=None)
                            
                        duration = (end - start).total_seconds()
                        job.processing_duration = duration
                except Exception as e:
                    logger.error(f"Error calculating duration: {e}")
            
            db.commit()

            logger.info(f"✅ Comparison job {job_id} completed successfully")
            return results

        except Exception as e:
            logger.error(f"❌ Comparison job {job_id} failed: {str(e)}")
            
            # Update job status to failed
            job = db.query(ComparisonJob).filter(ComparisonJob.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                job.completed_at = datetime.now(timezone.utc)
                db.commit()

                log_automation_event(
                    db=db,
                    component="backend",
                    action="JOB_FAILED",
                    message=f"Job failed: {str(e)}",
                    cradle_id=job.cradle_id,
                    is_error=True,
                    details={"error": str(e)}
                )
            
            return {"success": False, "error": str(e)}

        finally:
            # Immediate file deletion removed in favor of periodic background cleanup (10-minute retention) in main.py
            db.close()

    def _save_results(
        self, db: Session, job: ComparisonJob, results: Dict[str, Any]
    ) -> None:
        """Save comparison results to database"""
        
        # Helper to ensure data is JSON serializable (handle numpy types)
        from dataclasses import is_dataclass, asdict
        
        def ensure_serializable(obj):
            if is_dataclass(obj):
                return ensure_serializable(asdict(obj))
            elif isinstance(obj, dict):
                return {k: ensure_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [ensure_serializable(v) for v in obj]
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, np.generic):
                return obj.item()
            return obj
            
        # Sanitize entire results dict first for general purpose usage
        # This replaces the entire results structure with a JSON-safe version (no numpy types)
        clean_results = ensure_serializable(results)
        
        video_result = clean_results.get("video_result")
        audio_result = clean_results.get("audio_result")
        
        # Calculate overall similarity
        overall_similarity = 1.0
        has_differences = False
        has_error = False
        
        if video_result:
            # video_result is now a dict (after ensure_serializable)
            error_msg = video_result.get("error_message")
            if error_msg:
                has_error = True
                has_differences = True
                overall_similarity = 0.0
            else:
                overall_similarity = min(overall_similarity, video_result.get("overall_similarity", 1.0))
                has_differences = has_differences or video_result.get("frames_with_differences", 0) > 0
            
        if audio_result and isinstance(audio_result, dict):
            if audio_result.get("audio_mismatch"):
                has_differences = True
                overall_similarity = 0.0
            elif audio_result.get("no_audio_tracks") or audio_result.get("has_audio") is False:
                # Source files have no audio streams (silent video / GIF) — DO NOT penalize overall_similarity!
                pass
            elif "error" in audio_result:
                has_error = True
                has_differences = True
                overall_similarity = 0.0
            else:
                audio_similarity = audio_result.get("similarity_score")
                if audio_similarity is not None:
                    overall_similarity = min(overall_similarity, audio_similarity)
                    has_differences = has_differences or audio_similarity < 0.99

        # Build report data
        report_data = {}

        # Add audio results to report_data
        if audio_result and isinstance(audio_result, dict):
            report_data["audio"] = {
                "has_audio": audio_result.get("has_audio", True),
                "no_audio_tracks": audio_result.get("no_audio_tracks", False),
                "message": audio_result.get("message"),
                "loudness": audio_result.get("loudness"),
                "similarity": audio_result.get("similarity"),
                "has_loudness_differences": audio_result.get("loudness", {}).get("has_loudness_differences", False) if isinstance(audio_result.get("loudness"), dict) else False,
                "source_separation": audio_result.get("source_separation"),
                "voiceover": audio_result.get("voiceover"),
                "speech_to_text": audio_result.get("speech_to_text"),
            }

        # Add video diff frames to report_data
        if video_result:
            if "video" not in report_data:
                report_data["video"] = {}
            if video_result.get("diff_image_paths"):
                report_data["video"]["diff_frames"] = video_result.get("diff_image_paths")
            report_data["video"]["is_arpp_slate"] = video_result.get("is_arpp_slate", False)
            report_data["video"]["duration_difference"] = video_result.get("duration_difference", 0.0)

        # Create main comparison result
        comparison_result = ComparisonResult(
            job_id=job.id,
            overall_similarity=overall_similarity,
            is_match=not has_differences,
            video_similarity=video_result.get("overall_similarity") if video_result else None,
            video_differences_count=video_result.get("frames_with_differences", 0) if video_result else 0,
            audio_similarity=audio_result.get("similarity_score") if audio_result else None,
            difference_timestamps=video_result.get("difference_timestamps") if video_result else None,
            report_data=report_data if report_data else None,
        )
        db.add(comparison_result)
        
        # Save processing duration to job
        processing_duration = video_result.get("processing_time", 0.0) if video_result else 0.0
        
        # Fallback if 0
        if processing_duration <= 0 and job.started_at:
             # Handle timezone mismatch
             start_time = job.started_at
             end_time = datetime.now(timezone.utc)
             
             if start_time.tzinfo is None:
                 start_time = start_time.replace(tzinfo=timezone.utc)
                 
             processing_duration = (end_time - start_time).total_seconds()
             
        job.processing_duration = processing_duration

        # Save video results
        if video_result:
            video_db_result = VideoComparisonResult(
                job_id=job.id,
                similarity_score=video_result.get("overall_similarity", 0.0),
                total_frames=video_result.get("total_frames_analyzed", 0),
                different_frames=video_result.get("frames_with_differences", 0),
                algorithm_used="SSIM/MSE",
                frame_analysis_data={
                    "frame_similarities": video_result.get("frame_similarities"),
                    "diff_image_paths": video_result.get("diff_image_paths"),
                    "difference_timestamps": video_result.get("difference_timestamps")
                }
            )
            db.add(video_db_result)

            # Save difference timestamps
            diff_timestamps = video_result.get("difference_timestamps")
            v_sim_score = video_result.get("similarity_score")
            
            if v_sim_score is not None:
                if v_sim_score >= 0.98:
                    video_sev = SeverityLevel.LOW
                elif v_sim_score >= 0.90:
                    video_sev = SeverityLevel.MEDIUM
                elif v_sim_score >= 0.50:
                    video_sev = SeverityLevel.HIGH
                else:
                    video_sev = SeverityLevel.CRITICAL
            else:
                video_sev = SeverityLevel.MEDIUM

            if diff_timestamps:
                for timestamp in diff_timestamps:
                    diff = DifferenceTimestamp(
                        job_id=job.id,
                        timestamp_seconds=float(timestamp),
                        difference_type=DifferenceType.VIDEO_FRAME,
                        severity=video_sev,
                    )
                    db.add(diff)

        # Save audio results
        if audio_result and isinstance(audio_result, dict) and "error" not in audio_result:
            metadata = audio_result.get("comparison_metadata", {})
            sim_score = audio_result.get("similarity_score")
            audio_db_result = AudioComparisonResult(
                job_id=job.id,
                similarity_score=sim_score,
                spectral_similarity=metadata.get("spectral_similarity"),
                mfcc_similarity=metadata.get("mfcc_similarity"),
                audio_analysis_data=audio_result,  # This is already clean_results["audio_result"]
            )
            db.add(audio_db_result)

            # Option B: Add a single general AUDIO_SPECTRAL difference on the timeline
            # UWAGA (QA vs UI): Próg 0.99 służy wyłącznie do wygenerowania wizualnego markera
            # (znacznika) na osi czasu w interfejsie użytkownika.
            # Rzeczywisty werdykt QA zapada w AnalystService (Zasady Decyzyjne), gdzie
            # obowiązują inne progi (REVIEW dla < 0.95, REJECT dla < 0.90).
            if sim_score is not None and sim_score < 0.99:
                if sim_score >= 0.95:
                    audio_sev = SeverityLevel.LOW
                elif sim_score >= 0.85:
                    audio_sev = SeverityLevel.MEDIUM
                elif sim_score >= 0.50:
                    audio_sev = SeverityLevel.HIGH
                else:
                    audio_sev = SeverityLevel.CRITICAL
                    
                audio_diff = DifferenceTimestamp(
                    job_id=job.id,
                    timestamp_seconds=0.0,
                    duration_seconds=job.acceptance_file.duration if job.acceptance_file and job.acceptance_file.duration else 1.0,
                    difference_type=DifferenceType.AUDIO_SPECTRAL,
                    severity=audio_sev,
                )
                db.add(audio_diff)


        # --- Phase 2: Analyst Brain (Agent 2) ---
        # Call this BEFORE the main commit to avoid deadlocks in SQLite
        try:
            db.flush() # Push pending results to DB so snapshot can read them
            clean_results["overall_similarity"] = overall_similarity
            self._run_ai_analyst(db, job.id, clean_results)
        except Exception as ai_e:
            logger.error(f"⚠️ AI Analyst failed: {ai_e}")
        finally:
            # GC cleanup after Ollama — model is unloaded (keep_alive=0) but Python wrappers
            # linger. Force collection before final DB commit to free ~1-2 GB sooner.
            import gc
            gc.collect()

        db.commit()
        logger.info(f"💾 Saved comparison results for job {job.id}")

    @classmethod
    def _build_ai_metrics(cls, job: ComparisonJob, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts and validates metrics dictionary from job results for AI Analyst.
        Enforces strict fail-closed allowlist for STT skip scenarios.
        """
        job_id = getattr(job, "id", None)
        job_name = getattr(job, "job_name", "")
        client_name = getattr(job, "client_name", "")
        comparison_type = getattr(job, "comparison_type", None)

        video_res = results.get("video_result")
        audio_res = results.get("audio_result")

        # NOTE: results passed here are already through ensure_serializable() — video_res is a DICT,
        # not a dataclass. Using hasattr() on a dict always returns False → similarity defaulted to 1.0.
        # Fix: use .get() for dict, hasattr() only as fallback for legacy dataclass objects.
        if isinstance(video_res, dict):
            computed_video_similarity = float(video_res.get("overall_similarity", 1.0))
            video_differences_count = int(video_res.get("frames_with_differences", 0))
        elif video_res and hasattr(video_res, "overall_similarity"):
            computed_video_similarity = float(video_res.overall_similarity)
            video_differences_count = int(getattr(video_res, "frames_with_differences", 0))
        else:
            computed_video_similarity = 1.0
            video_differences_count = 0
            
        penalized_overall = results.get("overall_similarity", computed_video_similarity)

        metrics = {
            "job_id": job_id,
            "job_name": job_name,
            "client_name": client_name,
            "overall_similarity": penalized_overall,
            "video_similarity": computed_video_similarity,
            "video_differences_count": video_differences_count,
            "is_arpp_slate": video_res.get("is_arpp_slate", False) if isinstance(video_res, dict) else getattr(video_res, "is_arpp_slate", False),
            "duration_difference": video_res.get("duration_difference", 0.0) if isinstance(video_res, dict) else getattr(video_res, "duration_difference", 0.0),
        }
        
        if audio_res and isinstance(audio_res, dict):
            metrics["audio_similarity"] = float(audio_res.get("similarity_score", 0.0))
            
            # Prune massive float arrays from audio_analysis_data to align with SOUL.md
            stt = audio_res.get("speech_to_text", {})
            metrics["audio_analysis_data"] = {
                "similarity": {
                    "error": audio_res.get("similarity", {}).get("error", "") if isinstance(audio_res.get("similarity"), dict) else ""
                },
                "speech_to_text": {
                    "comparison": {
                        "word_count_a": stt.get("comparison", {}).get("word_count_a", 0) if isinstance(stt.get("comparison"), dict) else 0,
                        "word_count_b": stt.get("comparison", {}).get("word_count_b", 0) if isinstance(stt.get("comparison"), dict) else 0,
                    } if isinstance(stt, dict) else {}
                }
            }
            metrics["audio_mismatch"] = audio_res.get("audio_mismatch", False)
            metrics["no_audio_tracks"] = audio_res.get("no_audio_tracks", False)

            if not stt or not isinstance(stt, dict):
                # Unregistered missing STT payload: protect against silent failure (Fail-Closed)
                # An empty/missing STT dictionary can ONLY be recognized as skipped if the job state
                # strictly proves a verified, allowlisted skip condition:
                is_legit_skip = False
                legit_reason = None
                if is_valid_no_audio_streams_skip(audio_res):
                    is_legit_skip = True
                    legit_reason = "NO_AUDIO_STREAMS"
                elif is_valid_full_stt_skip(comparison_type, audio_res):
                    is_legit_skip = True
                    legit_reason = "FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH"

                if is_legit_skip:
                    stt_status = "skipped"
                    metrics["audio_transcription"] = {
                        "status": "skipped",
                        "text_similarity": None,
                        "is_text_match": None,
                        "acceptance_text": "",
                        "emission_text": "",
                        "word_differences_count": 0,
                        "word_differences_sample": [],
                        "skipped_reason": legit_reason,
                        "error_message": None,
                        "is_uncertain": False,
                        "uncertainty_reason": None,
                    }
                    metrics["stt_skipped"] = True
                    metrics["stt_skipped_reason"] = legit_reason
                else:
                    stt_status = "failed"
                    metrics["audio_transcription"] = {
                        "status": "failed",
                        "text_similarity": None,
                        "is_text_match": None,
                        "acceptance_text": "",
                        "emission_text": "",
                        "word_differences_count": 0,
                        "word_differences_sample": [],
                        "skipped_reason": None,
                        "error_message": "Unexpected missing STT payload without allowlisted skip reason",
                        "is_uncertain": True,
                        "uncertainty_reason": "Unregistered missing STT payload",
                    }
                    metrics["stt_skipped"] = False
                    metrics["stt_skipped_reason"] = None
            else:
                stt_similarity = stt.get("text_similarity")
                acceptance_text = stt.get("acceptance_text", "")
                emission_text = stt.get("emission_text", "")
                comparison_data = stt.get("comparison", {})
                word_diffs = comparison_data.get("word_differences", [])
                raw_stt_status = stt.get("status")
                raw_skip_reason = stt.get("skipped_reason")

                is_uncertain = stt.get("is_uncertain", False)
                uncertainty_reason = stt.get("uncertainty_reason")

                if raw_stt_status == "skipped":
                    skip_code = extract_normalized_skip_code(raw_skip_reason)
                    if not skip_code:
                        stt_status = "failed"
                        is_uncertain = True
                        uncertainty_reason = f"Unverified STT skip reason: {raw_skip_reason}"
                    else:
                        # Strict code dispatch - verified against actual job state
                        if skip_code == "NO_AUDIO_STREAMS":
                            if not is_valid_no_audio_streams_skip(audio_res):
                                stt_status = "failed"
                                is_uncertain = True
                                uncertainty_reason = "NO_AUDIO_STREAMS skip invalid: audio stream present or audio mismatch detected"
                            else:
                                stt_status = "skipped"
                        elif skip_code == "FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH":
                            if not is_valid_full_stt_skip(comparison_type, audio_res):
                                stt_status = "failed"
                                is_uncertain = True
                                uncertainty_reason = "FULL_MODE skip invalid: Raw VAD, LUFS, music proportion or audio mismatch criteria not met"
                            else:
                                stt_status = "skipped"
                        elif skip_code == "FAST_PATH_IDENTICAL_AUDIO":
                            if not is_valid_fast_path_audio_skip(comparison_type, audio_res):
                                stt_status = "failed"
                                is_uncertain = True
                                uncertainty_reason = "FAST_PATH audio skip invalid: similarity < 0.98, mismatch, or loudness differences detected"
                            else:
                                stt_status = "skipped"
                        elif skip_code == "DUPLICATE_INPUT":
                            if not (check_comp_type(comparison_type, [ComparisonType.FULL, ComparisonType.AUTOMATION]) and audio_res.get("is_binary_duplicate") is True):
                                stt_status = "failed"
                                is_uncertain = True
                                uncertainty_reason = "DUPLICATE_INPUT skip invalid: inputs are not verified binary duplicates in FULL or AUTOMATION mode"
                            else:
                                stt_status = "skipped"
                                is_uncertain = True
                                uncertainty_reason = uncertainty_reason or "DUPLICATE_INPUT: Identical binary files detected; requires verification"
                        else:
                            stt_status = "failed"
                            is_uncertain = True
                            uncertainty_reason = f"Unknown skip code: {skip_code}"
                elif not raw_stt_status:
                    if "error" in stt:
                        stt_status = "failed"
                        is_uncertain = True
                        uncertainty_reason = f"STT error: {stt.get('error')}"
                    else:
                        stt_status = "failed"
                        is_uncertain = True
                        uncertainty_reason = "STT payload missing status field"
                else:
                    stt_status = raw_stt_status

                metrics["audio_transcription"] = {
                    "status": stt_status,
                    "text_similarity": stt_similarity,
                    "is_text_match": stt.get("is_text_match"),
                    "acceptance_text": acceptance_text[:300] if acceptance_text else "",
                    "emission_text": emission_text[:300] if emission_text else "",
                    "word_differences_count": len(word_diffs),
                    "word_differences_sample": word_diffs[:5],
                    "skipped_reason": stt.get("skipped_reason"),
                    "error_message": stt.get("error_message"),
                    "is_uncertain": is_uncertain,
                    "uncertainty_reason": uncertainty_reason,
                }
                metrics["stt_skipped"] = (stt_status == "skipped")
                metrics["stt_skipped_reason"] = stt.get("skipped_reason")
            
            loudness = audio_res.get("loudness", {})
            loudness_comparison = loudness.get("comparison", {})
            metrics["audio_loudness"] = {
                "acceptance_lufs": loudness.get("acceptance", {}).get("integrated_lufs"),
                "emission_lufs": loudness.get("emission", {}).get("integrated_lufs"),
                "lufs_difference": loudness_comparison.get("lufs_difference"),
                "peak_difference_db": loudness_comparison.get("peak_difference_db"),
                "has_loudness_issue": loudness.get("has_loudness_differences", False)
            }
            
        return metrics

    def _run_ai_analyst(self, db: Session, job_id: int, results: Dict[str, Any]) -> None:
        """
        Orchestrates the AI analyst brain for a given job.
        
        Args:
            db: Database session
            job_id: ID of the job to analyze
            results: Results dictionary from comparison
        """
        job = db.query(ComparisonJob).filter(ComparisonJob.id == job_id).first()
        if not job:
            return

        metrics = self._build_ai_metrics(job, results)

        # Call AI Analyst — pass db session so it can load per-client KB context (SOUL.md)
        from .analyst_service import get_analyst
        ai_result = get_analyst().analyze_job_results(metrics, db=db)
        
        # Save AI Verdict
        try:
            # Map string verdict to enum
            verdict_str = ai_result.get("verdict", "review").lower()
            verdict = DecisionVerdict.REVIEW
            if verdict_str == "approve":
                verdict = DecisionVerdict.APPROVE
            elif verdict_str == "reject":
                verdict = DecisionVerdict.REJECT
                
            stt_status = metrics.get("audio_transcription", {}).get("status")
            is_stt_uncertain = metrics.get("audio_transcription", {}).get("is_uncertain", False)
            if stt_status == "failed" and verdict == DecisionVerdict.APPROVE:
                verdict = DecisionVerdict.REVIEW
                error_msg = metrics.get("audio_transcription", {}).get("error_message", "Unknown error")
                ai_result["reasoning"] = f"[SYSTEM OVERRIDE] Odrzucono aprobatę AI. Moduł STT uległ awarii technicznej i weryfikacja głosu nie została ukończona. Zgłoszony błąd: {error_msg}\n\nOryginalna odpowiedź AI: {ai_result.get('reasoning', '')}"
            elif stt_status == "failed" and verdict == DecisionVerdict.REJECT:
                error_msg = metrics.get("audio_transcription", {}).get("error_message", "Unknown error")
                ai_result["reasoning"] = f"[SYSTEM OVERRIDE] Odrzucono (REJECT). Dodatkowo, moduł STT napotkał awarię techniczną: {error_msg}.\n\n" + ai_result.get("reasoning", "")
            elif is_stt_uncertain and verdict == DecisionVerdict.APPROVE:
                verdict = DecisionVerdict.REVIEW
                unc_msg = metrics.get("audio_transcription", {}).get("uncertainty_reason", "wykryto zapętlenie lektora")
                ai_result["reasoning"] = f"[SYSTEM OVERRIDE] Odrzucono aprobatę AI. Wynik STT oznaczono jako niepewny ({unc_msg}). Wymuszono status REVIEW do weryfikacji przez człowieka.\n\nOryginalna odpowiedź AI: {ai_result.get('reasoning', '')}"


            # Build knowledge snapshot — full audit trail for post-job-deletion review
            knowledge_snapshot = self._build_knowledge_snapshot(db, job_id, job, results)

            decision = db.query(QADecision).filter(QADecision.job_id == job_id).first()
            if not decision:
                decision = QADecision(
                    job_id=job_id,
                    verdict=verdict,
                    reasoning=ai_result.get('reasoning'),
                    ai_reasoning=ai_result.get('reasoning'),
                    client_name=job.client_name,
                    cradle_id=job.cradle_id,
                    metrics_snapshot=metrics,
                    knowledge_snapshot=knowledge_snapshot,
                    decided_by="agent"
                )
                db.add(decision)
            else:
                # Update if not already decided by human (SOUL.md: preserve human decisions)
                if decision.decided_by != "human":
                    decision.verdict = verdict
                    decision.reasoning = ai_result.get('reasoning')
                    decision.ai_reasoning = ai_result.get('reasoning')
                    decision.metrics_snapshot = metrics
                    decision.knowledge_snapshot = knowledge_snapshot

            logger.info(f"🧠 AI Analyst verdict for job {job_id}: {verdict_str} | KB snapshot saved")

        except Exception as e:
            logger.error(f"❌ Failed to prepare AI decision: {e}")

    def _build_knowledge_snapshot(self, db, job_id: int, job, results: dict) -> dict:
        """
        Build a full audit-trail snapshot that survives weekly job cleanup.
        
        Stores: video difference timeline, per-frame severity, audio LUFS + STT,
        and job metadata. Does NOT store raw waveform data (too large, no audit value).
        """
        try:
            snapshot = {
                "job_meta": {
                    "job_name": job.job_name,
                    "cradle_id": job.cradle_id,
                    "client_name": job.client_name,
                    "sensitivity": job.sensitivity_level.value if job.sensitivity_level else None,
                    "comparison_type": job.comparison_type.value if job.comparison_type else None,
                },
                "video": {},
                "audio": {},
            }

            # ── Video: frame-level differences ──────────────────────────────
            video_res = db.query(VideoComparisonResult).filter(
                VideoComparisonResult.job_id == job_id
            ).first()
            if video_res:
                snapshot["video"] = {
                    "similarity": round(float(video_res.similarity_score), 4),
                    "different_frames": video_res.different_frames,
                    "total_frames": video_res.total_frames,
                    "resolution": video_res.resolution,
                    "fps": video_res.fps,
                    "duration_seconds": video_res.duration_seconds,
                }

            # ── Difference timestamps — the Difference Inspector data ────────
            diff_timestamps = db.query(DifferenceTimestamp).filter(
                DifferenceTimestamp.job_id == job_id
            ).order_by(DifferenceTimestamp.timestamp_seconds).all()

            if diff_timestamps:
                # Full timeline (timestamps only — lightweight)
                snapshot["video"]["difference_timeline"] = [
                    round(d.timestamp_seconds, 2) for d in diff_timestamps
                ]
                # Top 20 worst frames with severity (for Difference Inspector replay)
                sorted_diffs = sorted(
                    diff_timestamps,
                    key=lambda d: d.similarity_score if d.similarity_score is not None else 1.0
                )
                snapshot["video"]["top_differences"] = [
                    {
                        "timestamp": round(d.timestamp_seconds, 2),
                        "severity": d.severity.value if d.severity else None,
                        "type": d.difference_type.value if d.difference_type else None,
                        "similarity": round(float(d.similarity_score), 4) if d.similarity_score else None,
                    }
                    for d in sorted_diffs[:20]
                ]

            # ── Audio: LUFS + STT only (skip raw waveform — too large) ──────
            audio_res_db = db.query(AudioComparisonResult).filter(
                AudioComparisonResult.job_id == job_id
            ).first()
            if audio_res_db:
                audio_data = audio_res_db.audio_analysis_data or {}
                loudness = audio_data.get("loudness", {})
                loudness_comp = loudness.get("comparison", {})
                stt = audio_data.get("speech_to_text", {})

                snapshot["audio"] = {
                    "similarity": round(float(audio_res_db.similarity_score), 4),
                    "lufs_acceptance": loudness.get("acceptance", {}).get("integrated_lufs"),
                    "lufs_emission": loudness.get("emission", {}).get("integrated_lufs"),
                    "lufs_difference": loudness_comp.get("lufs_difference"),
                    "peak_difference_db": loudness_comp.get("peak_difference_db"),
                    "stt_text_similarity": stt.get("text_similarity"),
                    "stt_is_match": stt.get("is_text_match"),
                    "stt_acceptance_text": (stt.get("acceptance_text") or "")[:500],
                    "stt_emission_text": (stt.get("emission_text") or "")[:500],
                    "stt_word_differences": (stt.get("comparison") or {}).get("word_differences", [])[:10],
                    "stt_segment_differences": (stt.get("comparison") or {}).get("segment_differences", [])[:10],
                    "stt_status": stt.get("status") or ("skipped" if not stt else "completed"),
                    "stt_skipped": (stt.get("status") == "skipped") if stt.get("status") else (stt.get("skipped", True) if stt else True),
                    "stt_skipped_reason": stt.get("skipped_reason") or ("STT was not executed for this job" if not stt else None),
                    "is_uncertain": stt.get("is_uncertain", False),
                }

            return snapshot

        except Exception as e:
            logger.warning(f"⚠️ Could not build knowledge_snapshot for job {job_id}: {e}")
            return {}



# Singleton instance for the service
_comparison_service: Optional[ComparisonService] = None


def get_comparison_service() -> ComparisonService:
    """Get or create singleton comparison service instance"""
    global _comparison_service
    if _comparison_service is None:
        _comparison_service = ComparisonService()
    return _comparison_service


def _run_job_in_process(job_id: int) -> Dict[str, Any]:
    """
    Standalone function to run job in a separate process.
    Must be at module level to be picklable.
    """
    # Create a fresh service instance for the new process
    # Create a fresh service instance for the new process
    # Fix: Use the same 'uploads' directory that main.py serves statically
    # comparison_service.py is in backend/services, so uploads is ../uploads
    uploads_dir = Path(__file__).parent.parent / "uploads"
    uploads_dir.mkdir(exist_ok=True)
    
    # We append "temp" because VideoProcessor appends "job_{id}", resulting in backend/uploads/temp/job_{id}
    # which matches strict static mounting logic if we want to organize it
    # Actually, VideoProcessor logic is: self.temp_dir / f"job_{job_id}"
    # If we pass uploads_dir as temp_dir, it becomes backend/uploads/job_{id}
    # But URL construction is: /uploads/temp/job_{id}
    # So we need to match that.
    
    temp_dir = uploads_dir / "temp"
    temp_dir.mkdir(exist_ok=True)

    service = ComparisonService(temp_dir=str(temp_dir))
    return service.process_job(job_id)


async def process_comparison_job(job_id: int) -> Dict[str, Any]:
    """
    Async wrapper for processing comparison job.
    Uses ThreadPoolExecutor so that the worker runs in the SAME process as uvicorn.
    This ensures that hot-reloaded modules (via uvicorn --reload) are visible to the worker.
    ProcessPoolExecutor was previously used but spawns a fresh interpreter that ignores
    any in-process module reloads — causing stale code to run even after file edits.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    loop = asyncio.get_running_loop()

    # Run in a thread to avoid blocking the event loop (GIL is released for I/O-heavy work)
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = await loop.run_in_executor(pool, _run_job_in_process, job_id)

    return result


ComparisonService.compare_files = ComparisonService.process_job
