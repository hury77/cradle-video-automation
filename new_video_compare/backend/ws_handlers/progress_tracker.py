"""
Progress Tracker for New Video Compare
Manages real-time progress updates from Celery tasks to WebSocket clients
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from models.schemas import DesktopAppMessage
from models.models import ComparisonJob, JobStatus
from models.database import get_db
from ws_handlers.handlers import connection_manager

logger = logging.getLogger(__name__)


class ProgressStage(Enum):
    """Progress stages for comparison jobs"""

    INITIALIZING = "initializing"
    VIDEO_PROCESSING = "video_processing"
    AUDIO_PROCESSING = "audio_processing"
    PARALLEL_PROCESSING = "parallel_processing"
    COMBINING_RESULTS = "combining_results"
    GENERATING_REPORT = "generating_report"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProgressUpdate:
    """Progress update data structure"""

    job_id: int
    stage: ProgressStage
    overall_percent: float
    video_percent: float = 0.0
    audio_percent: float = 0.0
    current_step: str = ""
    total_steps: int = 0
    current_step_number: int = 0
    estimated_remaining_seconds: Optional[int] = None
    details: Dict[str, Any] = None
    error_message: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.details is None:
            self.details = {}


class ProgressTracker:
    """Tracks and broadcasts job progress updates"""

    def __init__(self):
        # Current progress for active jobs
        self.job_progress: Dict[int, ProgressUpdate] = {}
        # Progress history (last 10 updates per job)
        self.progress_history: Dict[int, List[ProgressUpdate]] = {}
        # Job start times for ETA calculation
        self.job_start_times: Dict[int, datetime] = {}
        # Stage durations for better ETA estimates
        self.stage_durations: Dict[ProgressStage, List[float]] = {}

    async def update_progress(
        self,
        job_id: int,
        stage: ProgressStage,
        overall_percent: float,
        current_step: str = "",
        video_percent: float = 0.0,
        audio_percent: float = 0.0,
        details: Dict[str, Any] = None,
        error_message: Optional[str] = None,
    ):
        """Update job progress and broadcast to subscribers"""
        try:
            # Create progress update
            progress = ProgressUpdate(
                job_id=job_id,
                stage=stage,
                overall_percent=min(100.0, max(0.0, overall_percent)),
                video_percent=min(100.0, max(0.0, video_percent)),
                audio_percent=min(100.0, max(0.0, audio_percent)),
                current_step=current_step,
                details=details or {},
                error_message=error_message,
                timestamp=datetime.now(),
            )

            # Calculate ETA if job is running
            if stage not in [ProgressStage.COMPLETED, ProgressStage.FAILED]:
                progress.estimated_remaining_seconds = self._calculate_eta(
                    job_id, progress
                )

            # Store current progress
            self.job_progress[job_id] = progress

            # Add to history
            if job_id not in self.progress_history:
                self.progress_history[job_id] = []
            self.progress_history[job_id].append(progress)

            # Keep only last 10 updates
            if len(self.progress_history[job_id]) > 10:
                self.progress_history[job_id] = self.progress_history[job_id][-10:]

            # Update database job status
            await self._update_database_job_status(job_id, progress)

            # Broadcast to WebSocket subscribers
            await self._broadcast_progress_update(job_id, progress)

            # Log significant progress updates
            if overall_percent % 10 == 0 or stage in [
                ProgressStage.COMPLETED,
                ProgressStage.FAILED,
            ]:
                logger.info(
                    f"Job {job_id} progress: {overall_percent}% - {stage.value} - {current_step}"
                )

        except Exception as e:
            logger.error(f"Error updating progress for job {job_id}: {str(e)}")

    async def start_job_tracking(self, job_id: int):
        """Start tracking new job"""
        try:
            self.job_start_times[job_id] = datetime.now()

            await self.update_progress(
                job_id=job_id,
                stage=ProgressStage.INITIALIZING,
                overall_percent=0.0,
                current_step="Job started, initializing processing...",
            )

            logger.info(f"Started tracking job {job_id}")

        except Exception as e:
            logger.error(f"Error starting job tracking for {job_id}: {str(e)}")

    async def complete_job_tracking(
        self, job_id: int, success: bool = True, error_message: str = None
    ):
        """Complete job tracking"""
        try:
            stage = ProgressStage.COMPLETED if success else ProgressStage.FAILED
            progress_percent = 100.0 if success else 0.0

            # Record stage duration for future ETA calculations
            if job_id in self.job_start_times:
                total_duration = (
                    datetime.now() - self.job_start_times[job_id]
                ).total_seconds()
                self._record_stage_duration(ProgressStage.COMPLETED, total_duration)

            await self.update_progress(
                job_id=job_id,
                stage=stage,
                overall_percent=progress_percent,
                current_step="Processing completed" if success else "Processing failed",
                error_message=error_message,
                details={
                    "completion_time": datetime.now().isoformat(),
                    "total_duration_seconds": (
                        (datetime.now() - self.job_start_times[job_id]).total_seconds()
                        if job_id in self.job_start_times
                        else None
                    ),
                },
            )

            # Clean up tracking data after delay to allow final updates
            asyncio.create_task(self._cleanup_job_tracking(job_id, delay_seconds=300))

            logger.info(f"Completed tracking job {job_id} - Success: {success}")

        except Exception as e:
            logger.error(f"Error completing job tracking for {job_id}: {str(e)}")

    async def get_job_progress(self, job_id: int) -> Optional[ProgressUpdate]:
        """Get current progress for job"""
        return self.job_progress.get(job_id)

    async def get_job_progress_history(self, job_id: int) -> List[ProgressUpdate]:
        """Get progress history for job"""
        return self.progress_history.get(job_id, [])

    async def get_active_jobs(self) -> Dict[int, ProgressUpdate]:
        """Get all currently active jobs"""
        active_jobs = {}
        for job_id, progress in self.job_progress.items():
            if progress.stage not in [ProgressStage.COMPLETED, ProgressStage.FAILED]:
                active_jobs[job_id] = progress
        return active_jobs

    def _calculate_eta(
        self, job_id: int, current_progress: ProgressUpdate
    ) -> Optional[int]:
        """Calculate estimated time remaining for job"""
        try:
            if job_id not in self.job_start_times:
                return None

            elapsed_seconds = (
                datetime.now() - self.job_start_times[job_id]
            ).total_seconds()

            if current_progress.overall_percent <= 0:
                return None

            # Simple linear projection
            total_estimated_seconds = (
                elapsed_seconds * 100
            ) / current_progress.overall_percent
            remaining_seconds = total_estimated_seconds - elapsed_seconds

            # Add stage-based adjustments if we have historical data
            stage_adjustment = self._get_stage_adjustment(current_progress.stage)
            remaining_seconds *= stage_adjustment

            return max(0, int(remaining_seconds))

        except Exception as e:
            logger.error(f"Error calculating ETA for job {job_id}: {str(e)}")
            return None

    def _get_stage_adjustment(self, stage: ProgressStage) -> float:
        """Get adjustment factor based on historical stage durations"""
        # Default adjustments based on typical processing patterns
        adjustments = {
            ProgressStage.INITIALIZING: 1.0,
            ProgressStage.VIDEO_PROCESSING: 1.2,  # Video typically takes longer
            ProgressStage.AUDIO_PROCESSING: 0.8,  # Audio typically faster
            ProgressStage.PARALLEL_PROCESSING: 0.9,
            ProgressStage.COMBINING_RESULTS: 1.1,
            ProgressStage.GENERATING_REPORT: 1.0,
        }
        return adjustments.get(stage, 1.0)

    def _record_stage_duration(self, stage: ProgressStage, duration_seconds: float):
        """Record stage duration for future ETA calculations"""
        if stage not in self.stage_durations:
            self.stage_durations[stage] = []

        self.stage_durations[stage].append(duration_seconds)

        # Keep only last 20 measurements
        if len(self.stage_durations[stage]) > 20:
            self.stage_durations[stage] = self.stage_durations[stage][-20:]

    async def _update_database_job_status(self, job_id: int, progress: ProgressUpdate):
        """Update job status in database"""
        from models.database import SessionLocal  # Import here to avoid circular imports if any

        db = SessionLocal()
        try:
            job = db.query(ComparisonJob).filter(ComparisonJob.id == job_id).first()

            if job:
                # Update job status based on progress stage
                if progress.stage == ProgressStage.COMPLETED:
                    job.status = JobStatus.COMPLETED
                elif progress.stage == ProgressStage.FAILED:
                    job.status = JobStatus.FAILED
                    if progress.error_message:
                        job.error_message = progress.error_message
                elif progress.stage in [
                    ProgressStage.VIDEO_PROCESSING,
                    ProgressStage.AUDIO_PROCESSING,
                    ProgressStage.PARALLEL_PROCESSING,
                    ProgressStage.COMBINING_RESULTS,
                ]:
                    job.status = JobStatus.PROCESSING

                # Update progress metadata
                job.progress_metadata = {
                    "overall_percent": progress.overall_percent,
                    "video_percent": progress.video_percent,
                    "audio_percent": progress.audio_percent,
                    "current_stage": progress.stage.value,
                    "current_step": progress.current_step,
                    "estimated_remaining_seconds": progress.estimated_remaining_seconds,
                    "last_updated": progress.timestamp.isoformat(),
                }

                job.updated_at = datetime.now()
                db.commit()

        except Exception as e:
            logger.error(f"Error updating database for job {job_id}: {str(e)}")
            db.rollback()
        finally:
            db.close()

    async def _broadcast_progress_update(self, job_id: int, progress: ProgressUpdate):
        """Broadcast progress update to WebSocket subscribers"""
        try:
            # Create WebSocket message
            message = DesktopAppMessage(
                action="progress_update",
                data={
                    "job_id": job_id,
                    "stage": progress.stage.value,
                    "overall_percent": progress.overall_percent,
                    "video_percent": progress.video_percent,
                    "audio_percent": progress.audio_percent,
                    "current_step": progress.current_step,
                    "estimated_remaining_seconds": progress.estimated_remaining_seconds,
                    "details": progress.details,
                    "error_message": progress.error_message,
                    "timestamp": progress.timestamp.isoformat(),
                },
                timestamp=progress.timestamp,
            )

            # Broadcast to job subscribers
            await connection_manager.broadcast_to_job_subscribers(job_id, message)

        except Exception as e:
            logger.error(
                f"Error broadcasting progress update for job {job_id}: {str(e)}"
            )

    async def _cleanup_job_tracking(self, job_id: int, delay_seconds: int = 300):
        """Clean up job tracking data after delay"""
        try:
            await asyncio.sleep(delay_seconds)

            # Remove from active tracking
            if job_id in self.job_progress:
                del self.job_progress[job_id]
            if job_id in self.job_start_times:
                del self.job_start_times[job_id]

            # Keep history but limit size
            if job_id in self.progress_history:
                self.progress_history[job_id] = self.progress_history[job_id][-5:]

            logger.debug(f"Cleaned up tracking data for job {job_id}")

        except Exception as e:
            logger.error(f"Error cleaning up tracking data for job {job_id}: {str(e)}")


# Global progress tracker instance
progress_tracker = ProgressTracker()


# Convenience functions for Celery tasks
async def update_job_progress(
    job_id: int,
    stage: str,
    percent: float,
    step: str = "",
    video_percent: float = 0.0,
    audio_percent: float = 0.0,
    details: Dict[str, Any] = None,
):
    """Convenience function for updating progress from Celery tasks"""
    try:
        stage_enum = ProgressStage(stage)
        await progress_tracker.update_progress(
            job_id=job_id,
            stage=stage_enum,
            overall_percent=percent,
            current_step=step,
            video_percent=video_percent,
            audio_percent=audio_percent,
            details=details,
        )
    except Exception as e:
        logger.error(f"Error in update_job_progress: {str(e)}")


async def start_job_progress_tracking(job_id: int):
    """Start progress tracking for new job"""
    await progress_tracker.start_job_tracking(job_id)


async def complete_job_progress_tracking(
    job_id: int, success: bool = True, error: str = None
):
    """Complete progress tracking for job"""
    await progress_tracker.complete_job_tracking(job_id, success, error)
