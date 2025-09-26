"""
Audio Processing Celery Tasks
Handles background audio comparison processing
"""

import os
import logging
from typing import Dict, Any
from celery import current_task
from backend.celery_config import celery_app
from backend.services.audio_processor import AudioProcessor
from backend.models.models import ComparisonJob, JobStatus
from backend.models.database import get_db

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="tasks.audio.process_audio_comparison")
def process_audio_comparison(
    self, job_id: int, acceptance_file_path: str, emission_file_path: str
) -> Dict[str, Any]:
    """
    Process audio comparison between acceptance and emission files

    Args:
        job_id: Database job ID for tracking
        acceptance_file_path: Path to acceptance video file
        emission_file_path: Path to emission video file

    Returns:
        Dict with audio comparison results
    """
    try:
        # Update job status
        db = next(get_db())
        job = db.query(ComparisonJob).filter(ComparisonJob.id == job_id).first()
        if job:
            job.celery_task_id = self.request.id
            db.commit()

        # Initialize audio processor
        audio_processor = AudioProcessor()

        # Update progress: Starting audio analysis
        current_task.update_state(
            state="PROGRESS",
            meta={
                "current": 10,
                "total": 100,
                "status": "Initializing audio analysis...",
                "stage": "audio_init",
            },
        )

        # Validate input files
        if not os.path.exists(acceptance_file_path):
            raise FileNotFoundError(
                f"Acceptance file not found: {acceptance_file_path}"
            )
        if not os.path.exists(emission_file_path):
            raise FileNotFoundError(f"Emission file not found: {emission_file_path}")

        # Update progress: Extracting audio
        current_task.update_state(
            state="PROGRESS",
            meta={
                "current": 25,
                "total": 100,
                "status": "Extracting audio tracks...",
                "stage": "audio_extraction",
            },
        )

        # Process audio comparison with progress callback
        comparison_results = audio_processor.process_audio_pair(
            acceptance_file_path,
            emission_file_path,
            progress_callback=lambda progress: current_task.update_state(
                state="PROGRESS",
                meta={
                    "current": 25 + int(progress * 0.65),  # 25-90% range
                    "total": 100,
                    "status": f"Analyzing audio... {progress:.1f}%",
                    "stage": "audio_analysis",
                },
            ),
        )

        # Update progress: Finalizing
        current_task.update_state(
            state="PROGRESS",
            meta={
                "current": 95,
                "total": 100,
                "status": "Finalizing audio analysis...",
                "stage": "audio_finalize",
            },
        )

        # Update job in database
        if job:
            job.audio_results = comparison_results
            job.audio_completed = True

            # Check if both video and audio are complete
            if job.video_completed:
                job.status = JobStatus.COMPLETED

            db.commit()

        logger.info(f"Audio processing completed for job {job_id}")

        return {
            "status": "success",
            "job_id": job_id,
            "audio_results": comparison_results,
            "processing_time": comparison_results.get("processing_time", 0),
            "audio_differences": comparison_results.get("comprehensive_comparison", {}),
        }

    except Exception as e:
        logger.error(f"Audio processing failed for job {job_id}: {str(e)}")

        # Update job status to failed
        try:
            if job:
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                db.commit()
        except:
            pass

        # Update task state
        current_task.update_state(
            state="FAILURE",
            meta={
                "current": 0,
                "total": 100,
                "status": f"Audio processing failed: {str(e)}",
                "error": str(e),
            },
        )

        raise


@celery_app.task(name="tasks.audio.extract_audio")
def extract_audio_track(video_path: str, output_path: str) -> Dict[str, Any]:
    """
    Extract audio track from video file

    Args:
        video_path: Path to video file
        output_path: Path for extracted audio file

    Returns:
        Audio extraction results
    """
    try:
        audio_processor = AudioProcessor()

        audio_info = audio_processor.extract_audio(video_path, output_path)

        return {
            "status": "success",
            "audio_file": output_path,
            "audio_info": audio_info,
        }

    except Exception as e:
        logger.error(f"Audio extraction failed: {str(e)}")
        raise


@celery_app.task(name="tasks.audio.normalize_audio_levels")
def normalize_audio_levels(
    audio_path: str, target_lufs: float = -23.0
) -> Dict[str, Any]:
    """
    Normalize audio levels to target LUFS

    Args:
        audio_path: Path to audio file
        target_lufs: Target loudness in LUFS

    Returns:
        Normalization results
    """
    try:
        audio_processor = AudioProcessor()

        normalized_data = audio_processor.normalize_loudness(audio_path, target_lufs)

        return {
            "status": "success",
            "original_lufs": normalized_data.get("original_lufs"),
            "target_lufs": target_lufs,
            "gain_applied": normalized_data.get("gain_applied"),
        }

    except Exception as e:
        logger.error(f"Audio normalization failed: {str(e)}")
        raise
