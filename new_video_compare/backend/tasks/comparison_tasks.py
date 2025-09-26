"""
Unified Comparison Tasks
Orchestrates video and audio processing for complete comparison
"""

import logging
from typing import Dict, Any
from celery import group, chain, current_task
from backend.celery_config import celery_app
from backend.tasks.video_tasks import process_video_comparison
from backend.tasks.audio_tasks import process_audio_comparison
from backend.models.models import ComparisonJob, JobStatus
from backend.models.database import get_db

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="tasks.comparison.process_complete_comparison")
def process_complete_comparison(
    self,
    job_id: int,
    acceptance_file_path: str,
    emission_file_path: str,
    priority: str = "normal",
) -> Dict[str, Any]:
    """
    Process complete comparison (video + audio) for acceptance vs emission

    Args:
        job_id: Database job ID
        acceptance_file_path: Path to acceptance file
        emission_file_path: Path to emission file
        priority: Job priority (normal, high, critical)

    Returns:
        Complete comparison results
    """
    try:
        # Update job status
        db = next(get_db())
        job = db.query(ComparisonJob).filter(ComparisonJob.id == job_id).first()
        if job:
            job.status = JobStatus.PROCESSING
            job.celery_task_id = self.request.id
            db.commit()

        # Update progress: Starting parallel processing
        current_task.update_state(
            state="PROGRESS",
            meta={
                "current": 5,
                "total": 100,
                "status": "Starting parallel video and audio analysis...",
                "stage": "initialization",
            },
        )

        # Create parallel processing group for video and audio
        parallel_tasks = group(
            process_video_comparison.s(
                job_id, acceptance_file_path, emission_file_path
            ),
            process_audio_comparison.s(
                job_id, acceptance_file_path, emission_file_path
            ),
        )

        # Execute parallel processing
        current_task.update_state(
            state="PROGRESS",
            meta={
                "current": 10,
                "total": 100,
                "status": "Processing video and audio in parallel...",
                "stage": "parallel_processing",
            },
        )

        # Wait for parallel tasks to complete
        result = parallel_tasks.apply_async()

        # Monitor progress (simplified - real implementation would track both tasks)
        while not result.ready():
            current_task.update_state(
                state="PROGRESS",
                meta={
                    "current": 50,
                    "total": 100,
                    "status": "Processing in progress...",
                    "stage": "processing",
                },
            )
            result.join(timeout=1.0, propagate=False)

        # Get results
        video_result, audio_result = result.get()

        # Update progress: Combining results
        current_task.update_state(
            state="PROGRESS",
            meta={
                "current": 90,
                "total": 100,
                "status": "Combining analysis results...",
                "stage": "combining_results",
            },
        )

        # Combine results and calculate overall score
        combined_results = combine_analysis_results(video_result, audio_result)

        # Update job with final results
        if job:
            job.status = JobStatus.COMPLETED
            job.final_results = combined_results
            job.overall_score = combined_results.get("overall_score", 0.0)
            db.commit()

        # Final progress update
        current_task.update_state(
            state="SUCCESS",
            meta={
                "current": 100,
                "total": 100,
                "status": "Analysis completed successfully",
                "stage": "completed",
            },
        )

        logger.info(f"Complete comparison finished for job {job_id}")

        return combined_results

    except Exception as e:
        logger.error(f"Complete comparison failed for job {job_id}: {str(e)}")

        # Update job status
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
                "status": f"Analysis failed: {str(e)}",
                "error": str(e),
            },
        )

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
                "analysis_timestamp": "now",  # TODO: Real timestamp
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


@celery_app.task(name="tasks.comparison.generate_report")
def generate_comparison_report(job_id: int, format: str = "json") -> Dict[str, Any]:
    """
    Generate detailed comparison report

    Args:
        job_id: Job ID to generate report for
        format: Report format (json, pdf, html)

    Returns:
        Report generation results
    """
    try:
        db = next(get_db())
        job = db.query(ComparisonJob).filter(ComparisonJob.id == job_id).first()

        if not job:
            raise ValueError(f"Job {job_id} not found")

        if not job.final_results:
            raise ValueError(f"Job {job_id} has no results to report")

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
            raise ValueError(f"Unsupported report format: {format}")

        return {
            "status": "success",
            "job_id": job_id,
            "format": format,
            "report_data": report_data,
        }

    except Exception as e:
        logger.error(f"Report generation failed for job {job_id}: {str(e)}")
        raise
