"""
New Video Compare - Results API
API endpoints for comparison results management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timezone

# Import database and models
from models.database import get_db
from models.models import (
    ComparisonJob,
    ComparisonResult,
    VideoComparisonResult,
    AudioComparisonResult,
    DifferenceTimestamp,
    JobStatus,
    DifferenceType,
    SeverityLevel,
)
from models.schemas import (
    DetailedComparisonResults,
    VideoComparisonResultCreate,
    VideoComparisonResultResponse,
    AudioComparisonResultCreate,
    AudioComparisonResultResponse,
    DifferenceTimestampCreate,
    DifferenceTimestampResponse,
    DifferenceTimestampUpdate,
    ResultsSummary,
    JobStatusEnum,
)

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/results", tags=["Results"])


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_job_or_404(db: Session, job_id: int) -> ComparisonJob:
    """Get comparison job by ID or raise 404"""
    job = db.query(ComparisonJob).filter(ComparisonJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison job {job_id} not found",
        )
    return job


def calculate_severity_counts(differences: List[DifferenceTimestamp]) -> Dict[str, int]:
    """Calculate counts by severity level"""
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for diff in differences:
        counts[diff.severity.value] += 1
    return counts


# =============================================================================
# DETAILED RESULTS ENDPOINTS
# =============================================================================


@router.get("/{job_id}", response_model=DetailedComparisonResults)
async def get_detailed_results(job_id: int, db: Session = Depends(get_db)):
    """
    Get all detailed results for a comparison job

    Returns combined video results, audio results, and difference timestamps
    """
    logger.info(f"Getting detailed results for job {job_id}")

    # Get job and verify it exists
    job = get_job_or_404(db, job_id)

    # Get detailed results
    video_result = (
        db.query(VideoComparisonResult)
        .filter(VideoComparisonResult.job_id == job_id)
        .first()
    )

    audio_result = (
        db.query(AudioComparisonResult)
        .filter(AudioComparisonResult.job_id == job_id)
        .first()
    )

    differences = (
        db.query(DifferenceTimestamp)
        .filter(DifferenceTimestamp.job_id == job_id)
        .order_by(DifferenceTimestamp.timestamp_seconds)
        .all()
    )

    # Get basic result for overall metrics
    basic_result = (
        db.query(ComparisonResult).filter(ComparisonResult.job_id == job_id).first()
    )

    # Calculate severity counts
    severity_counts = calculate_severity_counts(differences)

    return DetailedComparisonResults(
        job_id=job_id,
        job_status=JobStatusEnum(job.status.value),
        overall_similarity=basic_result.overall_similarity if basic_result else None,
        is_match=basic_result.is_match if basic_result else None,
        confidence_score=basic_result.confidence_score if basic_result else None,
        video_result=video_result,
        audio_result=audio_result,
        differences=differences,
        total_differences=len(differences),
        critical_differences=severity_counts["critical"],
        high_differences=severity_counts["high"],
        medium_differences=severity_counts["medium"],
        low_differences=severity_counts["low"],
    )


# =============================================================================
# VIDEO RESULTS ENDPOINTS
# =============================================================================


@router.post("/{job_id}/video", response_model=VideoComparisonResultResponse)
async def create_video_result(
    job_id: int, video_data: VideoComparisonResultCreate, db: Session = Depends(get_db)
):
    """Create or update video comparison result"""
    logger.info(f"Creating video result for job {job_id}")

    # Verify job exists
    job = get_job_or_404(db, job_id)

    # Check if video result already exists
    existing_result = (
        db.query(VideoComparisonResult)
        .filter(VideoComparisonResult.job_id == job_id)
        .first()
    )

    if existing_result:
        # Update existing result
        for field, value in video_data.model_dump(
            exclude={"job_id"}, exclude_unset=True
        ).items():
            setattr(existing_result, field, value)
        db.commit()
        db.refresh(existing_result)
        return existing_result
    else:
        # Create new result
        video_result = VideoComparisonResult(
            job_id=job_id, **video_data.model_dump(exclude={"job_id"})
        )
        db.add(video_result)
        db.commit()
        db.refresh(video_result)
        return video_result


@router.get("/{job_id}/video", response_model=Optional[VideoComparisonResultResponse])
async def get_video_result(job_id: int, db: Session = Depends(get_db)):
    """Get video comparison result for a job"""
    logger.info(f"Getting video result for job {job_id}")

    # Verify job exists
    job = get_job_or_404(db, job_id)

    video_result = (
        db.query(VideoComparisonResult)
        .filter(VideoComparisonResult.job_id == job_id)
        .first()
    )

    return video_result


# =============================================================================
# AUDIO RESULTS ENDPOINTS
# =============================================================================


@router.post("/{job_id}/audio", response_model=AudioComparisonResultResponse)
async def create_audio_result(
    job_id: int, audio_data: AudioComparisonResultCreate, db: Session = Depends(get_db)
):
    """Create or update audio comparison result"""
    logger.info(f"Creating audio result for job {job_id}")

    # Verify job exists
    job = get_job_or_404(db, job_id)

    # Check if audio result already exists
    existing_result = (
        db.query(AudioComparisonResult)
        .filter(AudioComparisonResult.job_id == job_id)
        .first()
    )

    if existing_result:
        # Update existing result
        for field, value in audio_data.model_dump(
            exclude={"job_id"}, exclude_unset=True
        ).items():
            setattr(existing_result, field, value)
        db.commit()
        db.refresh(existing_result)
        return existing_result
    else:
        # Create new result
        audio_result = AudioComparisonResult(
            job_id=job_id, **audio_data.model_dump(exclude={"job_id"})
        )
        db.add(audio_result)
        db.commit()
        db.refresh(audio_result)
        return audio_result


@router.get("/{job_id}/audio", response_model=Optional[AudioComparisonResultResponse])
async def get_audio_result(job_id: int, db: Session = Depends(get_db)):
    """Get audio comparison result for a job"""
    logger.info(f"Getting audio result for job {job_id}")

    # Verify job exists
    job = get_job_or_404(db, job_id)

    audio_result = (
        db.query(AudioComparisonResult)
        .filter(AudioComparisonResult.job_id == job_id)
        .first()
    )

    return audio_result


# =============================================================================
# DIFFERENCE TIMESTAMPS ENDPOINTS
# =============================================================================


@router.post("/{job_id}/differences", response_model=DifferenceTimestampResponse)
async def add_difference_timestamp(
    job_id: int,
    difference_data: DifferenceTimestampCreate,
    db: Session = Depends(get_db),
):
    """Add a new difference timestamp"""
    logger.info(
        f"Adding difference timestamp for job {job_id} at {difference_data.timestamp_seconds}s"
    )

    # Verify job exists
    job = get_job_or_404(db, job_id)

    # Create difference timestamp
    difference = DifferenceTimestamp(
        job_id=job_id, **difference_data.model_dump(exclude={"job_id"})
    )
    db.add(difference)
    db.commit()
    db.refresh(difference)

    return difference


@router.get("/{job_id}/differences", response_model=List[DifferenceTimestampResponse])
async def get_difference_timestamps(
    job_id: int,
    difference_type: Optional[DifferenceType] = None,
    severity: Optional[SeverityLevel] = None,
    min_timestamp: Optional[float] = None,
    max_timestamp: Optional[float] = None,
    db: Session = Depends(get_db),
):
    """Get difference timestamps for a job with optional filtering"""
    logger.info(f"Getting difference timestamps for job {job_id}")

    # Verify job exists
    job = get_job_or_404(db, job_id)

    # Build query with filters
    query = db.query(DifferenceTimestamp).filter(DifferenceTimestamp.job_id == job_id)

    if difference_type:
        query = query.filter(DifferenceTimestamp.difference_type == difference_type)

    if severity:
        query = query.filter(DifferenceTimestamp.severity == severity)

    if min_timestamp is not None:
        query = query.filter(DifferenceTimestamp.timestamp_seconds >= min_timestamp)

    if max_timestamp is not None:
        query = query.filter(DifferenceTimestamp.timestamp_seconds <= max_timestamp)

    differences = query.order_by(DifferenceTimestamp.timestamp_seconds).all()

    return differences


@router.put(
    "/{job_id}/differences/{difference_id}", response_model=DifferenceTimestampResponse
)
async def update_difference_timestamp(
    job_id: int,
    difference_id: int,
    update_data: DifferenceTimestampUpdate,
    db: Session = Depends(get_db),
):
    """Update a difference timestamp"""
    logger.info(f"Updating difference timestamp {difference_id} for job {job_id}")

    # Verify job exists
    job = get_job_or_404(db, job_id)

    # Get difference timestamp
    difference = (
        db.query(DifferenceTimestamp)
        .filter(
            DifferenceTimestamp.id == difference_id,
            DifferenceTimestamp.job_id == job_id,
        )
        .first()
    )

    if not difference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Difference timestamp {difference_id} not found for job {job_id}",
        )

    # Update fields
    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(difference, field, value)

    db.commit()
    db.refresh(difference)

    return difference


@router.delete("/{job_id}/differences/{difference_id}")
async def delete_difference_timestamp(
    job_id: int, difference_id: int, db: Session = Depends(get_db)
):
    """Delete a difference timestamp"""
    logger.info(f"Deleting difference timestamp {difference_id} for job {job_id}")

    # Verify job exists
    job = get_job_or_404(db, job_id)

    # Get and delete difference timestamp
    difference = (
        db.query(DifferenceTimestamp)
        .filter(
            DifferenceTimestamp.id == difference_id,
            DifferenceTimestamp.job_id == job_id,
        )
        .first()
    )

    if not difference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Difference timestamp {difference_id} not found for job {job_id}",
        )

    db.delete(difference)
    db.commit()

    return {"message": f"Difference timestamp {difference_id} deleted successfully"}


# =============================================================================
# EXPORT AND UTILITY ENDPOINTS
# =============================================================================


@router.get("/{job_id}/export")
async def export_results(
    job_id: int, format: str = "json", db: Session = Depends(get_db)  # json, csv, pdf
):
    """Export comparison results in various formats"""
    logger.info(f"Exporting results for job {job_id} in {format} format")

    if format not in ["json", "csv", "pdf"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format must be one of: json, csv, pdf",
        )

    # Get detailed results
    results = await get_detailed_results(job_id, db)

    if format == "json":
        return results
    elif format == "csv":
        # TODO: Implement CSV export
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="CSV export not yet implemented",
        )
    elif format == "pdf":
        # TODO: Implement PDF export
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="PDF export not yet implemented",
        )


@router.delete("/{job_id}")
async def delete_all_results(job_id: int, db: Session = Depends(get_db)):
    """Delete all results for a comparison job"""
    logger.info(f"Deleting all results for job {job_id}")

    # Verify job exists
    job = get_job_or_404(db, job_id)

    # Delete all related results (cascading should handle this, but let's be explicit)
    deleted_count = 0

    # Delete difference timestamps
    diff_count = (
        db.query(DifferenceTimestamp)
        .filter(DifferenceTimestamp.job_id == job_id)
        .delete()
    )
    deleted_count += diff_count

    # Delete video result
    video_count = (
        db.query(VideoComparisonResult)
        .filter(VideoComparisonResult.job_id == job_id)
        .delete()
    )
    deleted_count += video_count

    # Delete audio result
    audio_count = (
        db.query(AudioComparisonResult)
        .filter(AudioComparisonResult.job_id == job_id)
        .delete()
    )
    deleted_count += audio_count

    # Delete basic results
    basic_count = (
        db.query(ComparisonResult).filter(ComparisonResult.job_id == job_id).delete()
    )
    deleted_count += basic_count

    db.commit()

    return {
        "message": f"All results for job {job_id} deleted successfully",
        "deleted_items": deleted_count,
        "breakdown": {
            "differences": diff_count,
            "video_results": video_count,
            "audio_results": audio_count,
            "basic_results": basic_count,
        },
    }


# =============================================================================
# SUMMARY AND STATISTICS ENDPOINTS
# =============================================================================


@router.get("/summary", response_model=ResultsSummary)
async def get_results_summary(
    cradle_id: Optional[str] = None, db: Session = Depends(get_db)
):
    """Get summary statistics across all comparison results"""
    logger.info("Getting results summary")

    # Base query for jobs
    jobs_query = db.query(ComparisonJob)
    if cradle_id:
        jobs_query = jobs_query.filter(ComparisonJob.cradle_id == cradle_id)

    total_jobs = jobs_query.count()
    completed_jobs = jobs_query.filter(
        ComparisonJob.status == JobStatus.COMPLETED
    ).count()

    # Get all basic results for completed jobs
    results_query = (
        db.query(ComparisonResult)
        .join(ComparisonJob)
        .filter(ComparisonJob.status == JobStatus.COMPLETED)
    )
    if cradle_id:
        results_query = results_query.filter(ComparisonJob.cradle_id == cradle_id)

    results = results_query.all()

    # Calculate average similarity
    similarities = [
        r.overall_similarity for r in results if r.overall_similarity is not None
    ]
    average_similarity = sum(similarities) / len(similarities) if similarities else None

    # Get all differences for completed jobs
    differences_query = (
        db.query(DifferenceTimestamp)
        .join(ComparisonJob)
        .filter(ComparisonJob.status == JobStatus.COMPLETED)
    )
    if cradle_id:
        differences_query = differences_query.filter(
            ComparisonJob.cradle_id == cradle_id
        )

    all_differences = differences_query.all()

    # Count by severity and type
    differences_by_severity = {}
    differences_by_type = {}

    for diff in all_differences:
        severity_key = diff.severity.value
        type_key = diff.difference_type.value

        differences_by_severity[severity_key] = (
            differences_by_severity.get(severity_key, 0) + 1
        )
        differences_by_type[type_key] = differences_by_type.get(type_key, 0) + 1

    # Calculate total processing time
    processing_times = [
        job.processing_duration
        for job in jobs_query.all()
        if job.processing_duration is not None
    ]
    total_processing_time = sum(processing_times)

    return ResultsSummary(
        total_jobs=total_jobs,
        completed_jobs=completed_jobs,
        average_similarity=average_similarity,
        total_differences_found=len(all_differences),
        processing_time_total=total_processing_time,
        differences_by_severity=differences_by_severity,
        differences_by_type=differences_by_type,
    )
