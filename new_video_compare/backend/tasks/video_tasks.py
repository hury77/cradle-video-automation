"""
Video Processing Celery Tasks
Handles background video comparison processing
"""

import os
import logging
from typing import Dict, Any
from celery import current_task
from backend.celery_config import celery_app
from backend.services.video_processor import VideoProcessor
from backend.models.models import ComparisonJob, JobStatus
from backend.models.database import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="tasks.video.process_video_comparison")
def process_video_comparison(
    self, job_id: int, acceptance_file_path: str, emission_file_path: str
) -> Dict[str, Any]:
    """
    Process video comparison between acceptance and emission files

    Args:
        job_id: Database job ID for tracking
        acceptance_file_path: Path to acceptance video file
        emission_file_path: Path to emission video file

    Returns:
        Dict with comparison results and metadata
    """
    try:
        # Update job status
        db = next(get_db())
        job = db.query(ComparisonJob).filter(ComparisonJob.id == job_id).first()
        if job:
            job.status = JobStatus.PROCESSING
            job.celery_task_id = self.request.id
            db.commit()

        # Initialize video processor
        video_processor = VideoProcessor()

        # Update progress: Starting video analysis
        current_task.update_state(
            state="PROGRESS",
            meta={
                "current": 10,
                "total": 100,
                "status": "Initializing video analysis...",
                "stage": "video_init",
            },
        )

        # Validate input files
        if not os.path.exists(acceptance_file_path):
            raise FileNotFoundError(
                f"Acceptance file not found: {acceptance_file_path}"
            )
        if not os.path.exists(emission_file_path):
            raise FileNotFoundError(f"Emission file not found: {emission_file_path}")

        # Update progress: Processing frames
        current_task.update_state(
            state="PROGRESS",
            meta={
                "current": 30,
                "total": 100,
                "status": "Processing video frames...",
                "stage": "video_processing",
            },
        )

        # Process video comparison
        comparison_results = video_processor.process_video_pair(
            acceptance_file_path,
            emission_file_path,
            progress_callback=lambda progress: current_task.update_state(
                state="PROGRESS",
                meta={
                    "current": 30 + int(progress * 0.6),  # 30-90% range
                    "total": 100,
                    "status": f"Analyzing frames... {progress:.1f}%",
                    "stage": "video_analysis",
                },
            ),
        )

        # Update progress: Finalizing results
        current_task.update_state(
            state="PROGRESS",
            meta={
                "current": 95,
                "total": 100,
                "status": "Finalizing video analysis...",
                "stage": "video_finalize",
            },
        )

        # Update job in database
        if job:
            job.video_results = comparison_results
            job.video_completed = True

            # Check if both video and audio are complete
            if job.audio_completed:
                job.status = JobStatus.COMPLETED

            db.commit()

        logger.info(f"Video processing completed for job {job_id}")

        return {
            "status": "success",
            "job_id": job_id,
            "video_results": comparison_results,
            "processing_time": comparison_results.get("processing_time", 0),
            "differences_found": len(comparison_results.get("differences", [])),
        }

    except Exception as e:
        logger.error(f"Video processing failed for job {job_id}: {str(e)}")

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
                "status": f"Video processing failed: {str(e)}",
                "error": str(e),
            },
        )

        raise


@celery_app.task(name="tasks.video.extract_frames")
def extract_video_frames(video_path: str, output_dir: str) -> Dict[str, Any]:
    """
    Extract frames from video file for analysis

    Args:
        video_path: Path to video file
        output_dir: Directory to save extracted frames

    Returns:
        Dict with extraction results
    """
    try:
        video_processor = VideoProcessor()

        frames_info = video_processor.extract_frames_for_analysis(
            video_path, output_dir
        )

        return {
            "status": "success",
            "frames_extracted": len(frames_info),
            "output_directory": output_dir,
            "frames_info": frames_info,
        }

    except Exception as e:
        logger.error(f"Frame extraction failed: {str(e)}")
        raise


@celery_app.task(name="tasks.video.cleanup_temp_files")
def cleanup_video_temp_files(temp_dirs: list) -> Dict[str, Any]:
    """
    Clean up temporary video processing files

    Args:
        temp_dirs: List of temporary directories to clean

    Returns:
        Cleanup results
    """
    try:
        import shutil

        cleaned_dirs = []

        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                cleaned_dirs.append(temp_dir)

        return {
            "status": "success",
            "cleaned_directories": cleaned_dirs,
            "count": len(cleaned_dirs),
        }

    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")
        raise
