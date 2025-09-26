"""
Audio Processing Celery Tasks
Handles background audio comparison processing with WebSocket real-time updates
"""

import os
import logging
import requests
from typing import Dict, Any
from celery import current_task
from celery_config import celery_app
from services.audio_processor import AudioProcessor
from models.models import ComparisonJob, JobStatus
from models.database import get_db

logger = logging.getLogger(__name__)

# WebSocket API configuration
WEBSOCKET_API_BASE = os.getenv("WEBSOCKET_API_BASE", "http://localhost:8000/api/v1/ws")
WEBSOCKET_TIMEOUT = int(os.getenv("WEBSOCKET_TIMEOUT", "5"))


def send_websocket_progress_update(job_id: int, progress_data: Dict[str, Any]) -> bool:
    """
    Send progress update to WebSocket API for real-time client notifications

    Args:
        job_id: Job identifier
        progress_data: Progress information to send

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        url = f"{WEBSOCKET_API_BASE}/notify/job/{job_id}"
        response = requests.post(
            url,
            json=progress_data,
            timeout=WEBSOCKET_TIMEOUT,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 200:
            logger.debug(f"WebSocket progress update sent for job {job_id}")
            return True
        else:
            logger.warning(
                f"WebSocket API returned {response.status_code} for job {job_id}"
            )
            return False

    except requests.exceptions.Timeout:
        logger.warning(f"WebSocket API timeout for job {job_id}")
        return False
    except requests.exceptions.ConnectionError:
        logger.warning(f"WebSocket API connection error for job {job_id}")
        return False
    except Exception as e:
        logger.error(f"WebSocket progress update failed for job {job_id}: {e}")
        return False


@celery_app.task(bind=True, name="tasks.audio.process_audio_comparison")
def process_audio_comparison(
    self, job_id: int, acceptance_file_path: str, emission_file_path: str
) -> Dict[str, Any]:
    """
    Process audio comparison between acceptance and emission files with real-time updates

    Args:
        job_id: Database job ID for tracking
        acceptance_file_path: Path to acceptance video file
        emission_file_path: Path to emission video file

    Returns:
        Dict with audio comparison results
    """
    task_id = self.request.id

    try:
        # Update job status in database
        db = next(get_db())
        job = db.query(ComparisonJob).filter(ComparisonJob.id == job_id).first()
        if job:
            job.celery_task_id = task_id
            db.commit()

        # Initialize audio processor
        audio_processor = AudioProcessor()

        # Progress Update: Starting audio analysis
        progress_data = {
            "current": 10,
            "total": 100,
            "status": "Initializing audio analysis...",
            "stage": "audio_init",
            "task_id": task_id,
            "job_type": "audio_comparison",
        }

        current_task.update_state(state="PROGRESS", meta=progress_data)
        send_websocket_progress_update(job_id, progress_data)

        # Validate input files
        if not os.path.exists(acceptance_file_path):
            error_msg = f"Acceptance file not found: {acceptance_file_path}"

            error_data = {
                "current": 0,
                "total": 100,
                "status": "Audio file validation failed",
                "stage": "error",
                "error": error_msg,
                "task_id": task_id,
            }
            send_websocket_progress_update(job_id, error_data)
            raise FileNotFoundError(error_msg)

        if not os.path.exists(emission_file_path):
            error_msg = f"Emission file not found: {emission_file_path}"

            error_data = {
                "current": 0,
                "total": 100,
                "status": "Audio file validation failed",
                "stage": "error",
                "error": error_msg,
                "task_id": task_id,
            }
            send_websocket_progress_update(job_id, error_data)
            raise FileNotFoundError(error_msg)

        # Progress Update: Extracting audio
        progress_data = {
            "current": 25,
            "total": 100,
            "status": "Extracting audio tracks...",
            "stage": "audio_extraction",
            "task_id": task_id,
            "files": {
                "acceptance": os.path.basename(acceptance_file_path),
                "emission": os.path.basename(emission_file_path),
            },
        }

        current_task.update_state(state="PROGRESS", meta=progress_data)
        send_websocket_progress_update(job_id, progress_data)

        # Define progress callback for audio processor
        def audio_progress_callback(progress: float):
            """Callback for audio processing progress updates"""
            current_progress = 25 + int(progress * 0.65)  # 25-90% range

            progress_data = {
                "current": current_progress,
                "total": 100,
                "status": f"Analyzing audio... {progress:.1f}%",
                "stage": "audio_analysis",
                "task_id": task_id,
                "analysis_progress": progress,
            }

            current_task.update_state(state="PROGRESS", meta=progress_data)
            send_websocket_progress_update(job_id, progress_data)

        # Process audio comparison with progress callback
        comparison_results = audio_processor.process_audio_pair(
            acceptance_file_path,
            emission_file_path,
            progress_callback=audio_progress_callback,
        )

        # Progress Update: Finalizing
        progress_data = {
            "current": 95,
            "total": 100,
            "status": "Finalizing audio analysis...",
            "stage": "audio_finalize",
            "task_id": task_id,
            "results_preview": {
                "audio_differences": len(
                    comparison_results.get("comprehensive_comparison", {})
                ),
                "similarity_score": comparison_results.get("similarity_score", 0),
            },
        }

        current_task.update_state(state="PROGRESS", meta=progress_data)
        send_websocket_progress_update(job_id, progress_data)

        # Update job in database
        if job:
            job.audio_results = comparison_results
            job.audio_completed = True

            # Check if both video and audio are complete
            if job.video_completed:
                job.status = JobStatus.COMPLETED

            db.commit()

        # Final success update
        final_results = {
            "status": "success",
            "job_id": job_id,
            "audio_results": comparison_results,
            "processing_time": comparison_results.get("processing_time", 0),
            "audio_differences": comparison_results.get("comprehensive_comparison", {}),
        }

        success_data = {
            "current": 100,
            "total": 100,
            "status": "Audio analysis completed successfully",
            "stage": "audio_completed",
            "task_id": task_id,
            "results": final_results,
        }

        current_task.update_state(state="SUCCESS", meta=success_data)
        send_websocket_progress_update(job_id, success_data)

        logger.info(f"Audio processing completed for job {job_id}")
        return final_results

    except Exception as e:
        logger.error(f"Audio processing failed for job {job_id}: {str(e)}")

        # Update job status to failed in database
        try:
            if job:
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update job status in database: {db_error}")

        # Send failure update via WebSocket
        failure_data = {
            "current": 0,
            "total": 100,
            "status": f"Audio processing failed: {str(e)}",
            "stage": "failed",
            "error": str(e),
            "task_id": task_id,
        }

        current_task.update_state(state="FAILURE", meta=failure_data)
        send_websocket_progress_update(job_id, failure_data)

        raise


@celery_app.task(bind=True, name="tasks.audio.extract_audio")
def extract_audio_track(self, video_path: str, output_path: str) -> Dict[str, Any]:
    """
    Extract audio track from video file with progress tracking

    Args:
        video_path: Path to video file
        output_path: Path for extracted audio file

    Returns:
        Audio extraction results
    """
    task_id = self.request.id

    try:
        # Initial progress update
        progress_data = {
            "current": 0,
            "total": 100,
            "status": "Starting audio extraction...",
            "stage": "audio_extraction_init",
            "task_id": task_id,
            "video_file": os.path.basename(video_path),
            "output_file": os.path.basename(output_path),
        }

        current_task.update_state(state="PROGRESS", meta=progress_data)

        audio_processor = AudioProcessor()

        # Progress update: Processing
        progress_data = {
            "current": 50,
            "total": 100,
            "status": "Extracting audio track...",
            "stage": "audio_extraction_processing",
            "task_id": task_id,
        }

        current_task.update_state(state="PROGRESS", meta=progress_data)

        audio_info = audio_processor.extract_audio(video_path, output_path)

        # Success result
        result = {
            "status": "success",
            "audio_file": output_path,
            "audio_info": audio_info,
        }

        success_data = {
            "current": 100,
            "total": 100,
            "status": "Audio extraction completed",
            "stage": "audio_extraction_completed",
            "task_id": task_id,
            "results": result,
        }

        current_task.update_state(state="SUCCESS", meta=success_data)

        return result

    except Exception as e:
        logger.error(f"Audio extraction failed: {str(e)}")

        failure_data = {
            "current": 0,
            "total": 100,
            "status": f"Audio extraction failed: {str(e)}",
            "stage": "audio_extraction_failed",
            "error": str(e),
            "task_id": task_id,
        }

        current_task.update_state(state="FAILURE", meta=failure_data)

        raise


@celery_app.task(bind=True, name="tasks.audio.normalize_audio_levels")
def normalize_audio_levels(
    self, audio_path: str, target_lufs: float = -23.0
) -> Dict[str, Any]:
    """
    Normalize audio levels to target LUFS with progress tracking

    Args:
        audio_path: Path to audio file
        target_lufs: Target loudness in LUFS

    Returns:
        Normalization results
    """
    task_id = self.request.id

    try:
        # Initial progress update
        progress_data = {
            "current": 0,
            "total": 100,
            "status": f"Starting audio normalization to {target_lufs} LUFS...",
            "stage": "audio_normalization_init",
            "task_id": task_id,
            "audio_file": os.path.basename(audio_path),
            "target_lufs": target_lufs,
        }

        current_task.update_state(state="PROGRESS", meta=progress_data)

        audio_processor = AudioProcessor()

        # Progress update: Analyzing current levels
        progress_data = {
            "current": 25,
            "total": 100,
            "status": "Analyzing current audio levels...",
            "stage": "audio_level_analysis",
            "task_id": task_id,
        }

        current_task.update_state(state="PROGRESS", meta=progress_data)

        # Progress update: Applying normalization
        progress_data = {
            "current": 75,
            "total": 100,
            "status": "Applying loudness normalization...",
            "stage": "audio_normalization_processing",
            "task_id": task_id,
        }

        current_task.update_state(state="PROGRESS", meta=progress_data)

        normalized_data = audio_processor.normalize_loudness(audio_path, target_lufs)

        # Success result
        result = {
            "status": "success",
            "original_lufs": normalized_data.get("original_lufs"),
            "target_lufs": target_lufs,
            "gain_applied": normalized_data.get("gain_applied"),
        }

        success_data = {
            "current": 100,
            "total": 100,
            "status": "Audio normalization completed",
            "stage": "audio_normalization_completed",
            "task_id": task_id,
            "results": result,
        }

        current_task.update_state(state="SUCCESS", meta=success_data)

        return result

    except Exception as e:
        logger.error(f"Audio normalization failed: {str(e)}")

        failure_data = {
            "current": 0,
            "total": 100,
            "status": f"Audio normalization failed: {str(e)}",
            "stage": "audio_normalization_failed",
            "error": str(e),
            "task_id": task_id,
        }

        current_task.update_state(state="FAILURE", meta=failure_data)

        raise
