"""
Unified Comparison Tasks
Orchestrates video and audio processing for complete comparison with WebSocket real-time updates
"""

import logging
import requests
import time
from typing import Dict, Any
from celery import group, chain, current_task
from celery_config import celery_app
from tasks.video_tasks import process_video_comparison
from tasks.audio_tasks import process_audio_comparison
from models.models import ComparisonJob, JobStatus
from models.database import get_db
from datetime import datetime

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


@celery_app.task(bind=True, name="tasks.comparison.process_complete_comparison")
def process_complete_comparison(
    self,
    job_id: int,
    acceptance_file_path: str,
    emission_file_path: str,
    priority: str = "normal",
) -> Dict[str, Any]:
    """
    Process complete comparison (video + audio) for acceptance vs emission with real-time updates

    Args:
        job_id: Database job ID
        acceptance_file_path: Path to acceptance file
        emission_file_path: Path to emission file
        priority: Job priority (normal, high, critical)

    Returns:
        Complete comparison results
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

        # Progress Update: Starting parallel processing
        progress_data = {
            "current": 5,
            "total": 100,
            "status": "Starting parallel video and audio analysis...",
            "stage": "initialization",
            "task_id": task_id,
            "job_type": "complete_comparison",
            "priority": priority,
            "files": {
                "acceptance": os.path.basename(acceptance_file_path),
                "emission": os.path.basename(emission_file_path),
            },
        }

        current_task.update_state(state="PROGRESS", meta=progress_data)
        send_websocket_progress_update(job_id, progress_data)

        # Create parallel processing group for video and audio
        parallel_tasks = group(
            process_video_comparison.s(
                job_id, acceptance_file_path, emission_file_path
            ),
            process_audio_comparison.s(
                job_id, acceptance_file_path, emission_file_path
            ),
        )

        # Progress Update: Launching parallel tasks
        progress_data = {
            "current": 10,
            "total": 100,
            "status": "Launching video and audio processing in parallel...",
            "stage": "parallel_launch",
            "task_id": task_id,
            "sub_tasks": {"video_task": "starting", "audio_task": "starting"},
        }

        current_task.update_state(state="PROGRESS", meta=progress_data)
        send_websocket_progress_update(job_id, progress_data)

        # Execute parallel processing
        result = parallel_tasks.apply_async()

        # Enhanced progress monitoring
        progress_updates = 0
        max_updates = 100  # Prevent infinite loops

        while not result.ready() and progress_updates < max_updates:
            progress_updates += 1

            # Calculate dynamic progress (15% to 85% range during parallel processing)
            base_progress = 15
            processing_range = 70
            time_progress = min(progress_updates / max_updates, 1.0)
            current_progress = base_progress + int(time_progress * processing_range)

            # Get sub-task status if available
            sub_task_status = {}
            try:
                # Check individual task states (simplified)
                sub_task_status = {
                    "video_progress": "processing",
                    "audio_progress": "processing",
                    "estimated_completion": f"{100 - current_progress}% remaining",
                }
            except:
                pass

            progress_data = {
                "current": current_progress,
                "total": 100,
                "status": f"Processing video and audio in parallel... ({current_progress}%)",
                "stage": "parallel_processing",
                "task_id": task_id,
                "sub_tasks": sub_task_status,
                "processing_time": progress_updates * 1.0,  # Rough estimate
            }

            current_task.update_state(state="PROGRESS", meta=progress_data)
            send_websocket_progress_update(job_id, progress_data)

            # Wait before next check
            time.sleep(1.0)

        # Get results from parallel tasks
        try:
            video_result, audio_result = result.get(timeout=10.0)
        except Exception as e:
            error_msg = f"Parallel processing failed: {str(e)}"

            error_data = {
                "current": 0,
                "total": 100,
                "status": error_msg,
                "stage": "parallel_processing_failed",
                "error": error_msg,
                "task_id": task_id,
            }
            send_websocket_progress_update(job_id, error_data)
            raise

        # Progress Update: Combining results
        progress_data = {
            "current": 90,
            "total": 100,
            "status": "Combining analysis results...",
            "stage": "combining_results",
            "task_id": task_id,
            "sub_results": {
                "video_completed": video_result.get("status") == "success",
                "audio_completed": audio_result.get("status") == "success",
            },
        }

        current_task.update_state(state="PROGRESS", meta=progress_data)
        send_websocket_progress_update(job_id, progress_data)

        # Combine results and calculate overall score
        combined_results = combine_analysis_results(video_result, audio_result)

        # Update job with final results
        if job:
            job.status = JobStatus.COMPLETED
            job.final_results = combined_results
            job.overall_score = combined_results.get("overall_score", 0.0)
            db.commit()

        # Final success update
        final_results = {
            "job_id": job_id,
            "overall_score": combined_results.get("overall_score", 0.0),
            "recommendation": combined_results.get("summary", {}).get(
                "recommendation", ""
            ),
            "total_differences": combined_results.get("summary", {}).get(
                "total_differences", 0
            ),
            "critical_issues": len(
                combined_results.get("summary", {}).get("critical_issues", [])
            ),
            "processing_time": combined_results.get("metadata", {}).get(
                "total_processing_time", 0
            ),
        }

        success_data = {
            "current": 100,
            "total": 100,
            "status": "Complete analysis finished successfully",
            "stage": "completed",
            "task_id": task_id,
            "results": final_results,
        }

        current_task.update_state(state="SUCCESS", meta=success_data)
        send_websocket_progress_update(job_id, success_data)

        logger.info(f"Complete comparison finished for job {job_id}")
        return combined_results

    except Exception as e:
        logger.error(f"Complete comparison failed for job {job_id}: {str(e)}")

        # Update job status in database
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
            "status": f"Complete analysis failed: {str(e)}",
            "stage": "failed",
            "error": str(e),
            "task_id": task_id,
        }

        current_task.update_state(state="FAILURE", meta=failure_data)
        send_websocket_progress_update(job_id, failure_data)

        raise


def combine_analysis_results(video_result: Dict, audio_result: Dict) -> Dict[str, Any]:
    """
    Combine video and audio analysis results into unified report

    Args:
        video_result: Video comparison results
        audio_result: Audio comparison results

    Returns:
        Combined analysis results
    """
    try:
        # Extract key metrics
        video_data = video_result.get("video_results", {})
        audio_data = audio_result.get("audio_results", {})

        # Calculate weighted overall score
        video_score = video_data.get("overall_similarity", 0.0)
        audio_score = audio_data.get("comprehensive_comparison", {}).get(
            "overall_score", 0.0
        )

        # Weighted combination (60% video, 40% audio)
        overall_score = (video_score * 0.6) + (audio_score * 0.4)

        # Combine differences
        video_differences = video_data.get("differences", [])
        audio_differences = audio_data.get("differences", [])

        # Create comprehensive report
        combined_results = {
            "overall_score": overall_score,
            "video_analysis": {
                "score": video_score,
                "differences_count": len(video_differences),
                "processing_time": video_result.get("processing_time", 0),
                "algorithms_used": video_data.get("algorithms_used", []),
                "differences": video_differences,
            },
            "audio_analysis": {
                "score": audio_score,
                "differences_detected": len(audio_differences),
                "processing_time": audio_result.get("processing_time", 0),
                "analysis_types": list(audio_data.keys()),
                "differences": audio_differences,
            },
            "summary": {
                "total_differences": len(video_differences) + len(audio_differences),
                "confidence_level": min(
                    video_data.get("confidence", 0.0), audio_data.get("confidence", 0.0)
                ),
                "recommendation": get_recommendation(overall_score),
                "critical_issues": get_critical_issues(
                    video_differences, audio_differences
                ),
            },
            "metadata": {
                "analysis_timestamp": datetime.now().isoformat(),
                "processing_version": "1.0.0",
                "total_processing_time": (
                    video_result.get("processing_time", 0)
                    + audio_result.get("processing_time", 0)
                ),
            },
        }

        return combined_results

    except Exception as e:
        logger.error(f"Failed to combine results: {str(e)}")
        raise


def get_recommendation(overall_score: float) -> str:
    """Get recommendation based on overall score"""
    if overall_score >= 0.95:
        return "APPROVE - Excellent match"
    elif overall_score >= 0.85:
        return "APPROVE - Good match with minor differences"
    elif overall_score >= 0.70:
        return "REVIEW - Moderate differences detected"
    else:
        return "REJECT - Significant differences found"


def get_critical_issues(video_diffs: list, audio_diffs: list) -> list:
    """Identify critical issues from differences"""
    critical_issues = []

    # Check video critical issues
    for diff in video_diffs:
        if diff.get("severity", "low") == "critical":
            critical_issues.append(
                {
                    "type": "video",
                    "issue": diff.get("description", "Unknown video issue"),
                    "timestamp": diff.get("timestamp", 0),
                }
            )

    # Check audio critical issues
    for diff in audio_diffs:
        if diff.get("severity", "low") == "critical":
            critical_issues.append(
                {
                    "type": "audio",
                    "issue": diff.get("description", "Unknown audio issue"),
                    "timestamp": diff.get("timestamp", 0),
                }
            )

    return critical_issues


@celery_app.task(bind=True, name="tasks.comparison.generate_report")
def generate_comparison_report(
    self, job_id: int, format: str = "json"
) -> Dict[str, Any]:
    """
    Generate detailed comparison report with progress tracking

    Args:
        job_id: Job ID to generate report for
        format: Report format (json, pdf, html)

    Returns:
        Report generation results
    """
    task_id = self.request.id

    try:
        # Initial progress update
        progress_data = {
            "current": 0,
            "total": 100,
            "status": f"Starting {format.upper()} report generation...",
            "stage": "report_generation_init",
            "task_id": task_id,
            "report_format": format,
        }

        current_task.update_state(state="PROGRESS", meta=progress_data)
        send_websocket_progress_update(job_id, progress_data)

        # Get job data
        db = next(get_db())
        job = db.query(ComparisonJob).filter(ComparisonJob.id == job_id).first()

        if not job:
            error_msg = f"Job {job_id} not found"

            error_data = {
                "current": 0,
                "total": 100,
                "status": "Report generation failed - job not found",
                "stage": "error",
                "error": error_msg,
                "task_id": task_id,
            }
            send_websocket_progress_update(job_id, error_data)
            raise ValueError(error_msg)

        if not job.final_results:
            error_msg = f"Job {job_id} has no results to report"

            error_data = {
                "current": 0,
                "total": 100,
                "status": "Report generation failed - no results",
                "stage": "error",
                "error": error_msg,
                "task_id": task_id,
            }
            send_websocket_progress_update(job_id, error_data)
            raise ValueError(error_msg)

        # Progress update: Processing data
        progress_data = {
            "current": 25,
            "total": 100,
            "status": "Processing job results...",
            "stage": "data_processing",
            "task_id": task_id,
        }

        current_task.update_state(state="PROGRESS", meta=progress_data)
        send_websocket_progress_update(job_id, progress_data)

        # Progress update: Generating report
        progress_data = {
            "current": 50,
            "total": 100,
            "status": f"Generating {format.upper()} report...",
            "stage": "report_generation",
            "task_id": task_id,
        }

        current_task.update_state(state="PROGRESS", meta=progress_data)
        send_websocket_progress_update(job_id, progress_data)

        # Generate report based on format
        if format == "json":
            report_data = job.final_results
        elif format == "pdf":
            # TODO: Implement PDF report generation
            report_data = {"message": "PDF generation not yet implemented"}
        elif format == "html":
            # TODO: Implement HTML report generation
            report_data = {"message": "HTML generation not yet implemented"}
        else:
            error_msg = f"Unsupported report format: {format}"

            error_data = {
                "current": 0,
                "total": 100,
                "status": "Invalid report format",
                "stage": "error",
                "error": error_msg,
                "task_id": task_id,
            }
            send_websocket_progress_update(job_id, error_data)
            raise ValueError(error_msg)

        # Success result
        result = {
            "status": "success",
            "job_id": job_id,
            "format": format,
            "report_data": report_data,
        }

        success_data = {
            "current": 100,
            "total": 100,
            "status": f"{format.upper()} report generated successfully",
            "stage": "report_completed",
            "task_id": task_id,
            "results": result,
        }

        current_task.update_state(state="SUCCESS", meta=success_data)
        send_websocket_progress_update(job_id, success_data)

        return result

    except Exception as e:
        logger.error(f"Report generation failed for job {job_id}: {str(e)}")

        failure_data = {
            "current": 0,
            "total": 100,
            "status": f"Report generation failed: {str(e)}",
            "stage": "report_generation_failed",
            "error": str(e),
            "task_id": task_id,
        }

        current_task.update_state(state="FAILURE", meta=failure_data)
        send_websocket_progress_update(job_id, failure_data)

        raise
