"""
Video Processing Celery Tasks
Handles background video comparison processing with WebSocket real-time updates
"""

import os
import logging
import requests
from typing import Dict, Any, Optional
from celery import current_task
from celery_config import celery_app
from services.video_processor import VideoProcessor
from models.models import ComparisonJob, JobStatus
from models.database import get_db
from sqlalchemy.orm import Session

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


@celery_app.task(bind=True, name="tasks.video.process_video_comparison")
def process_video_comparison(
    self, job_id: int, acceptance_file_path: str, emission_file_path: str
) -> Dict[str, Any]:
    """
    Process video comparison between acceptance and emission files with real-time updates

    Args:
        job_id: Database job ID for tracking
        acceptance_file_path: Path to acceptance video file
        emission_file_path: Path to emission video file

    Returns:
        Dict with comparison results and metadata
    """
    task_id = self.request.id

    try:
        # Update job status in database
        db = next(get_db())
        job = db.query(ComparisonJob).filter(ComparisonJob.id == job_id).first()
        if job:
            job.status = JobStatus.PROCESSING
            job.celery_task_id = task_id
            db.commit()

        # Initialize video processor
        video_processor = VideoProcessor()

        # Progress Update: Starting video analysis
        progress_data = {
            "current": 10,
            "total": 100,
            "status": "Initializing video analysis...",
            "stage": "video_init",
            "task_id": task_id,
            "job_type": "video_comparison",
        }

        current_task.update_state(state="PROGRESS", meta=progress_data)
        send_websocket_progress_update(job_id, progress_data)

        # Validate input files
        if not os.path.exists(acceptance_file_path):
            error_msg = f"Acceptance file not found: {acceptance_file_path}"

            error_data = {
                "current": 0,
                "total": 100,
                "status": "File validation failed",
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
                "status": "File validation failed",
                "stage": "error",
                "error": error_msg,
                "task_id": task_id,
            }
            send_websocket_progress_update(job_id, error_data)
            raise FileNotFoundError(error_msg)

        # Progress Update: Processing frames
        progress_data = {
            "current": 30,
            "total": 100,
            "status": "Processing video frames...",
            "stage": "video_processing",
            "task_id": task_id,
            "files": {
                "acceptance": os.path.basename(acceptance_file_path),
                "emission": os.path.basename(emission_file_path),
            },
        }

        current_task.update_state(state="PROGRESS", meta=progress_data)
        send_websocket_progress_update(job_id, progress_data)

        # Define progress callback for video processor
        def video_progress_callback(progress: float):
            """Callback for video processing progress updates"""
            current_progress = 30 + int(progress * 0.6)  # 30-90% range

            progress_data = {
                "current": current_progress,
                "total": 100,
                "status": f"Analyzing frames... {progress:.1f}%",
                "stage": "video_analysis",
                "task_id": task_id,
                "analysis_progress": progress,
            }

            current_task.update_state(state="PROGRESS", meta=progress_data)
            send_websocket_progress_update(job_id, progress_data)

        # Process video comparison
        comparison_results = video_processor.process_video_pair(
            acceptance_file_path,
            emission_file_path,
            progress_callback=video_progress_callback,
        )

        # Progress Update: Finalizing results
        progress_data = {
            "current": 95,
            "total": 100,
            "status": "Finalizing video analysis...",
            "stage": "video_finalize",
            "task_id": task_id,
            "results_preview": {
                "differences_found": len(comparison_results.get("differences", [])),
                "similarity_score": comparison_results.get("similarity_score", 0),
            },
        }

        current_task.update_state(state="PROGRESS", meta=progress_data)
        send_websocket_progress_update(job_id, progress_data)

        # Update job in database
        if job:
            job.video_results = comparison_results
            job.video_completed = True

            # Check if both video and audio are complete
            if job.audio_completed:
                job.status = JobStatus.COMPLETED

            db.commit()

        # Final success update
        final_results = {
            "status": "success",
            "job_id": job_id,
            "video_results": comparison_results,
            "processing_time": comparison_results.get("processing_time", 0),
            "differences_found": len(comparison_results.get("differences", [])),
        }

        success_data = {
            "current": 100,
            "total": 100,
            "status": "Video analysis completed successfully",
            "stage": "video_completed",
            "task_id": task_id,
            "results": final_results,
        }

        current_task.update_state(state="SUCCESS", meta=success_data)
        send_websocket_progress_update(job_id, success_data)

        logger.info(f"Video processing completed for job {job_id}")
        return final_results

    except Exception as e:
        logger.error(f"Video processing failed for job {job_id}: {str(e)}")

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
            "status": f"Video processing failed: {str(e)}",
            "stage": "failed",
            "error": str(e),
            "task_id": task_id,
        }

        current_task.update_state(state="FAILURE", meta=failure_data)
        send_websocket_progress_update(job_id, failure_data)

        raise


@celery_app.task(bind=True, name="tasks.video.extract_frames")
def extract_video_frames(self, video_path: str, output_dir: str) -> Dict[str, Any]:
    """
    Extract frames from video file for analysis with progress tracking

    Args:
        video_path: Path to video file
        output_dir: Directory to save extracted frames

    Returns:
        Dict with extraction results
    """
    task_id = self.request.id

    try:
        # Initial progress update
        progress_data = {
            "current": 0,
            "total": 100,
            "status": "Starting frame extraction...",
            "stage": "frame_extraction_init",
            "task_id": task_id,
            "video_file": os.path.basename(video_path),
        }

        current_task.update_state(state="PROGRESS", meta=progress_data)

        video_processor = VideoProcessor()

        # Progress callback for frame extraction
        def extraction_progress_callback(progress: float):
            progress_data = {
                "current": int(progress),
                "total": 100,
                "status": f"Extracting frames... {progress:.1f}%",
                "stage": "frame_extraction",
                "task_id": task_id,
            }

            current_task.update_state(state="PROGRESS", meta=progress_data)

        frames_info = video_processor.extract_frames_for_analysis(
            video_path, output_dir, progress_callback=extraction_progress_callback
        )

        # Success result
        result = {
            "status": "success",
            "frames_extracted": len(frames_info),
            "output_directory": output_dir,
            "frames_info": frames_info,
        }

        success_data = {
            "current": 100,
            "total": 100,
            "status": "Frame extraction completed",
            "stage": "frame_extraction_completed",
            "task_id": task_id,
            "results": result,
        }

        current_task.update_state(state="SUCCESS", meta=success_data)

        return result

    except Exception as e:
        logger.error(f"Frame extraction failed: {str(e)}")

        failure_data = {
            "current": 0,
            "total": 100,
            "status": f"Frame extraction failed: {str(e)}",
            "stage": "frame_extraction_failed",
            "error": str(e),
            "task_id": task_id,
        }

        current_task.update_state(state="FAILURE", meta=failure_data)

        raise


@celery_app.task(bind=True, name="tasks.video.cleanup_temp_files")
def cleanup_video_temp_files(self, temp_dirs: list) -> Dict[str, Any]:
    """
    Clean up temporary video processing files with progress tracking

    Args:
        temp_dirs: List of temporary directories to clean

    Returns:
        Cleanup results
    """
    task_id = self.request.id

    try:
        import shutil

        # Initial progress
        progress_data = {
            "current": 0,
            "total": 100,
            "status": f"Starting cleanup of {len(temp_dirs)} directories...",
            "stage": "cleanup_init",
            "task_id": task_id,
        }

        current_task.update_state(state="PROGRESS", meta=progress_data)

        cleaned_dirs = []
        total_dirs = len(temp_dirs)

        for i, temp_dir in enumerate(temp_dirs):
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                cleaned_dirs.append(temp_dir)

            # Progress update
            progress = int(((i + 1) / total_dirs) * 100)
            progress_data = {
                "current": progress,
                "total": 100,
                "status": f"Cleaned {i + 1}/{total_dirs} directories",
                "stage": "cleanup_in_progress",
                "task_id": task_id,
            }

            current_task.update_state(state="PROGRESS", meta=progress_data)

        # Success result
        result = {
            "status": "success",
            "cleaned_directories": cleaned_dirs,
            "count": len(cleaned_dirs),
        }

        success_data = {
            "current": 100,
            "total": 100,
            "status": "Cleanup completed successfully",
            "stage": "cleanup_completed",
            "task_id": task_id,
            "results": result,
        }

        current_task.update_state(state="SUCCESS", meta=success_data)

        return result

    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")

        failure_data = {
            "current": 0,
            "total": 100,
            "status": f"Cleanup failed: {str(e)}",
            "stage": "cleanup_failed",
            "error": str(e),
            "task_id": task_id,
        }

        current_task.update_state(state="FAILURE", meta=failure_data)

        raise
