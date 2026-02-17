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
)
from config import get_sensitivity_config

logger = logging.getLogger(__name__)


class ComparisonService:
    """
    Main comparison service that orchestrates video and audio comparison
    """

    def __init__(self, temp_dir: Optional[str] = None):
        """Initialize comparison service with processors"""
        self.video_processor = VideoProcessor(temp_dir=temp_dir)
        self.audio_processor = AudioProcessor()
        logger.info("🔧 ComparisonService initialized")

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

            # Helper to check comparison type robustly (handles String vs Enum mismatch)
            def check_comp_type(job_type, target_types):
                # If it's a single type, make it a list
                if not isinstance(target_types, list):
                    target_types = [target_types]
                
                # Normalize job_type to string lower
                job_type_str = ""
                if hasattr(job_type, "value"):
                     job_type_str = str(job_type.value).lower()
                else:
                     job_type_str = str(job_type).lower()
                
                # Check against targets
                for t in target_types:
                    t_str = t.value.lower() if hasattr(t, "value") else str(t).lower()
                    if job_type_str == t_str:
                        return True
                return False

            results = {
                "video_result": None,
                "audio_result": None,
                "success": True,
            }
            
            # Define sensitivity-based processing defaults
            fps_map = {
                "low": 1.0,      # 1 frame/sec
                "medium": 2.0,   # 2 frames/sec
                "high": 5.0,     # 5 frames/sec (Detailed check)
                "automation": 5.0  # Same as HIGH
            }
            max_frames_map = {
                "low": 300,
                "medium": 900,
                "high": 3000,
                "automation": 3000  # Same as HIGH
            }
            threshold_map = {
                "low": 0.95,
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

            # Process based on comparison type
            logger.info(f"🔎 Checking Comparison Type: {job.comparison_type} (Enum: {ComparisonType.FULL}, {ComparisonType.VIDEO_ONLY})")
            


            # Process based on comparison type
            logger.info(f"🔎 Checking Comparison Type: {job.comparison_type} (Type: {type(job.comparison_type)})")
            print(f"DEBUG: Processing job {job.id} with type {job.comparison_type}")

            if check_comp_type(job.comparison_type, [ComparisonType.FULL, ComparisonType.VIDEO_ONLY, ComparisonType.AUTOMATION]):
                logger.info("🎬 Starting video comparison logic...")
                job.progress = 10.0
                db.commit()
                
                try:
                    video_result = self.video_processor.process_comparison(
                        job_id=job_id,
                        acceptance_file=acceptance_path,
                        emission_file=emission_path,
                        processing_config=processing_config,
                    )
                    logger.info(f"💾 Video Result Obtained: {video_result}")
                    results["video_result"] = video_result
                except Exception as e:
                    logger.error(f"❌ CRITICAL ERROR in process_comparison: {e}", exc_info=True)
                    results["video_result"] = None
                
                job.progress = 50.0
                db.commit()
                
                # MEMORY CLEANUP after video (especially important for AUTOMATION mode)
                if check_comp_type(job.comparison_type, ComparisonType.AUTOMATION):
                    logger.info("🧹 AUTOMATION: Releasing video memory before audio phase...")
                    import gc
                    gc.collect()
            else:
                logger.warning(f"⚠️ Skipping video comparison (Type mismatch: {job.comparison_type})")

            if check_comp_type(job.comparison_type, [ComparisonType.FULL, ComparisonType.AUDIO_ONLY, ComparisonType.AUTOMATION]):
                logger.info("🔊 Starting audio comparison...")
                job.progress = 65.0
                db.commit()
                
                audio_result = {}
                
                # LUFS Loudness comparison (new)
                try:
                    logger.info("📊 Measuring LUFS loudness levels...")
                    loudness_result = compare_loudness(acceptance_path, emission_path)
                    audio_result["loudness"] = loudness_result
                except Exception as lufs_err:
                    logger.warning(f"LUFS comparison failed: {lufs_err}")
                    audio_result["loudness"] = {"error": str(lufs_err)}
                
                job.progress = 75.0
                db.commit()
                
                # Audio similarity (MFCC-based)
                try:
                    logger.info("🎼 Computing audio similarity...")
                    similarity_result = compare_audio_similarity(acceptance_path, emission_path)
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
                    )
                    audio_result["spectral"] = legacy_result
                except Exception as audio_err:
                    logger.warning(f"Spectral audio comparison failed: {audio_err}")
                    audio_result["spectral"] = {"error": str(audio_err)}
                
                job.progress = 80.0
                db.commit()
                
                # Extended Audio Analysis (Demucs + Whisper)
                # Run in AUDIO_ONLY mode AND AUTOMATION mode
                if check_comp_type(job.comparison_type, [ComparisonType.AUDIO_ONLY, ComparisonType.AUTOMATION]):
                    mode_label = "AUTOMATION" if check_comp_type(job.comparison_type, ComparisonType.AUTOMATION) else "Audio-Only"
                    logger.info(f"🎧 {mode_label} Mode: Running enhanced analysis (Demucs + Whisper)...")
                    
                    import gc
                    gc.collect()
                    
                    # Speech-to-Text (Whisper + Demucs)
                    # The new pipeline handles Demucs internally per-file:
                    # acceptance → extract → Demucs → Whisper → result_a
                    # emission   → extract → Demucs → Whisper → result_b
                    # Then compares both transcripts
                    try:
                        logger.info("🎙️ Running Speech-to-Text pipeline (independent per file)...")
                        stt_result = compare_spoken_text(
                            acceptance_path,
                            emission_path,
                            use_separated_vocals=True
                        )
                        
                        # Extract pipeline info (source separation stats)
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
                            "timeline_data": {
                                "acceptance_segments": stt_result.get("transcript_acceptance", {}).get("segments", []),
                                "emission_segments": stt_result.get("transcript_emission", {}).get("segments", []),
                            },
                            "language": stt_result.get("transcript_acceptance", {}).get("language"),
                        }
                        
                        # Voiceover comparison is derived from source separation stats
                        audio_result["voiceover"] = stt_result.get("voiceover")
                        
                        logger.info(f"✅ Speech-to-Text complete: {stt_result.get('text_similarity', 0):.1%} match")
                        
                        del stt_result
                        gc.collect()
                        
                    except Exception as stt_err:
                        logger.warning(f"Speech-to-Text pipeline failed: {stt_err}")
                        audio_result["speech_to_text"] = {"error": str(stt_err)}
                        audio_result["source_separation"] = {"error": str(stt_err)}

                else:
                    # FULL / VIDEO_ONLY Mode — skip heavy audio processing
                    logger.info("⏩ Standard Mode: Skipping Demucs/Whisper to optimize performance.")
                    audio_result["source_separation"] = {"status": "skipped", "reason": "Available in Audio Only or Automation mode"}
                    audio_result["speech_to_text"] = None 
                    audio_result["voiceover"] = None
                
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
                    
                    # Handle potential timezone mismatch (SQLite often returns naive datetimes)
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
            
            return {"success": False, "error": str(e)}

        finally:
            db.close()

    def _save_results(
        self, db: Session, job: ComparisonJob, results: Dict[str, Any]
    ) -> None:
        """Save comparison results to database"""
        
        # Helper to ensure data is JSON serializable (handle numpy types)
        def ensure_serializable(obj):
            if isinstance(obj, dict):
                return {k: ensure_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [ensure_serializable(v) for v in obj]
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, np.generic):
                return obj.item()
            return obj
            
        # Sanitize entire results dict first
        results = ensure_serializable(results)
        
        video_result = results.get("video_result")
        audio_result = results.get("audio_result")
        
        # Calculate overall similarity
        overall_similarity = 1.0
        has_differences = False
        
        if video_result:
            overall_similarity = min(overall_similarity, video_result.overall_similarity)
            has_differences = has_differences or video_result.frames_with_differences > 0
            
        if audio_result and isinstance(audio_result, dict):
            audio_similarity = audio_result.get("similarity_score", 1.0)
            overall_similarity = min(overall_similarity, audio_similarity)
            has_differences = has_differences or audio_similarity < 0.99

        # Build report data
        report_data = {}

        # Add audio results to report_data
        if audio_result and isinstance(audio_result, dict):
            report_data["audio"] = {
                "loudness": audio_result.get("loudness"),
                "similarity": audio_result.get("similarity"),
                "has_loudness_differences": audio_result.get("loudness", {}).get("has_loudness_differences", False),
                "source_separation": audio_result.get("source_separation"),
                "voiceover": audio_result.get("voiceover"),
                "speech_to_text": audio_result.get("speech_to_text"),
            }

        # Add video diff frames to report_data
        if video_result and video_result.diff_image_paths:
            if "video" not in report_data:
                report_data["video"] = {}
            report_data["video"]["diff_frames"] = video_result.diff_image_paths

        # Create main comparison result
        comparison_result = ComparisonResult(
            job_id=job.id,
            overall_similarity=overall_similarity,
            is_match=not has_differences,
            video_similarity=video_result.overall_similarity if video_result else None,
            video_differences_count=video_result.frames_with_differences if video_result else 0,
            audio_similarity=audio_result.get("similarity_score") if audio_result else None,
            difference_timestamps=video_result.difference_timestamps if video_result else None,
            report_data=report_data if report_data else None,
        )
        db.add(comparison_result)
        
        # Save processing duration to job
        # Determine processing time from results or calculate it
        processing_duration = 0.0
        if video_result and hasattr(video_result, "processing_time"):
             processing_duration = video_result.processing_time
        
        # Fallback if 0
        if processing_duration <= 0 and job.started_at:
             # Handle timezone mismatch
             start_time = job.started_at
             end_time = datetime.now(timezone.utc)
             
             # Ensure start_time is aware if end_time is aware
             if start_time.tzinfo is None:
                 start_time = start_time.replace(tzinfo=timezone.utc)
                 
             processing_duration = (end_time - start_time).total_seconds()
             
        job.processing_duration = processing_duration

        # Save video results
        if video_result:
            video_db_result = VideoComparisonResult(
                job_id=job.id,
                similarity_score=video_result.overall_similarity,
                total_frames=video_result.total_frames_analyzed,
                different_frames=video_result.frames_with_differences,
                algorithm_used="MSE",
            )
            db.add(video_db_result)

            # Save difference timestamps
            if video_result.difference_timestamps:
                for timestamp in video_result.difference_timestamps:
                    diff = DifferenceTimestamp(
                        job_id=job.id,
                        timestamp_seconds=float(timestamp),
                        difference_type=DifferenceType.VIDEO_FRAME,
                        severity=SeverityLevel.MEDIUM,
                    )
                    db.add(diff)

        # Save audio results (audio_result is a dict from compare_audio_files)
        if audio_result and isinstance(audio_result, dict) and "error" not in audio_result:
            metadata = audio_result.get("comparison_metadata", {})
            audio_db_result = AudioComparisonResult(
                job_id=job.id,
                similarity_score=audio_result.get("similarity_score", 0.0),
                spectral_similarity=metadata.get("spectral_similarity"),
                mfcc_similarity=metadata.get("mfcc_similarity"),
                audio_analysis_data=audio_result,  # Save full audio analysis data
            )
            db.add(audio_db_result)

        db.commit()
        logger.info(f"💾 Saved comparison results for job {job.id}")


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
    Async wrapper for processing comparison job
    Uses ProcessPoolExecutor to guarantee non-blocking execution
    by running the heavy lifting in a completely separate process.
    """
    import asyncio
    from concurrent.futures import ProcessPoolExecutor
    
    loop = asyncio.get_running_loop()
    
    # Run in a separate process to avoid GIL/CPU blocking
    with ProcessPoolExecutor(max_workers=1) as pool:
        result = await loop.run_in_executor(pool, _run_job_in_process, job_id)
        
    return result
