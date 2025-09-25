"""
New Video Compare - Comparison API Endpoints
Create and manage video/audio comparison jobs
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from datetime import datetime, timezone

# Import dependencies
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
from models.database import get_db
from models.models import (
    ComparisonJob as ComparisonJobModel,
    File as FileModel,
    JobStatus,
    ComparisonType,
    FileType,
)
from models.schemas import (
    ComparisonJobCreate,
    ComparisonJobResponse,
    ComparisonJobUpdate,
    JobStatusEnum,
    ComparisonTypeEnum,
)
from config import settings

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/compare", tags=["Comparison"])

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def validate_files_for_comparison(
    acceptance_file: FileModel, emission_file: FileModel
) -> None:
    """Validate that files are suitable for comparison"""

    # Check if files exist and are processed
    if not acceptance_file or not emission_file:
        raise HTTPException(status_code=404, detail="One or both files not found")

    # Check file types
    if acceptance_file.file_type != FileType.ACCEPTANCE:
        raise HTTPException(
            status_code=400,
            detail=f"File {acceptance_file.id} is not an acceptance file",
        )

    if emission_file.file_type != FileType.EMISSION:
        raise HTTPException(
            status_code=400, detail=f"File {emission_file.id} is not an emission file"
        )

    # Check if files exist on disk
    if not Path(acceptance_file.file_path).exists():
        raise HTTPException(
            status_code=400,
            detail=f"Acceptance file not found on disk: {acceptance_file.filename}",
        )

    if not Path(emission_file.file_path).exists():
        raise HTTPException(
            status_code=400,
            detail=f"Emission file not found on disk: {emission_file.filename}",
        )


async def start_comparison_processing(job_id: int):
    """Start background comparison processing (placeholder)"""
    # This will be implemented with Celery task queue
    logger.info(f"🔄 Starting comparison processing for job {job_id}")
    # TODO: Queue Celery task for video/audio analysis
    pass


# =============================================================================
# API ENDPOINTS
# =============================================================================


@router.post("/", response_model=ComparisonJobResponse)
async def create_comparison_job(
    job_data: ComparisonJobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Create a new comparison job

    - **job_name**: Name for the comparison job
    - **acceptance_file_id**: ID of the acceptance file
    - **emission_file_id**: ID of the emission file
    - **comparison_type**: Type of comparison (video_only, audio_only, full)
    - **cradle_id**: Optional Cradle ID for integration
    """
    try:
        # Get files from database
        acceptance_file = (
            db.query(FileModel)
            .filter(FileModel.id == job_data.acceptance_file_id)
            .first()
        )

        emission_file = (
            db.query(FileModel)
            .filter(FileModel.id == job_data.emission_file_id)
            .first()
        )

        # Validate files
        validate_files_for_comparison(acceptance_file, emission_file)

        # Create comparison job
        comparison_job = ComparisonJobModel(
            job_name=job_data.job_name,
            job_description=job_data.job_description,
            acceptance_file_id=job_data.acceptance_file_id,
            emission_file_id=job_data.emission_file_id,
            comparison_type=ComparisonType(job_data.comparison_type.value),
            processing_config=job_data.processing_config,
            cradle_id=job_data.cradle_id,
            created_by=job_data.created_by,
            status=JobStatus.PENDING,
        )

        db.add(comparison_job)
        db.commit()
        db.refresh(comparison_job)

        logger.info(
            f"✅ Comparison job created: ID={comparison_job.id}, Name='{comparison_job.job_name}'"
        )

        # Start background processing
        background_tasks.add_task(start_comparison_processing, comparison_job.id)

        # Load related files for response
        comparison_job.acceptance_file = acceptance_file
        comparison_job.emission_file = emission_file

        return comparison_job

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create comparison job: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create comparison job: {str(e)}"
        )


@router.get("/", response_model=List[ComparisonJobResponse])
async def list_comparison_jobs(
    skip: int = 0,
    limit: int = 100,
    status: Optional[JobStatusEnum] = None,
    cradle_id: Optional[str] = None,
    comparison_type: Optional[ComparisonTypeEnum] = None,
    db: Session = Depends(get_db),
):
    """
    List comparison jobs with optional filtering

    - **skip**: Number of jobs to skip (pagination)
    - **limit**: Maximum number of jobs to return
    - **status**: Filter by job status
    - **cradle_id**: Filter by Cradle ID
    - **comparison_type**: Filter by comparison type
    """
    query = db.query(ComparisonJobModel)

    if status:
        query = query.filter(ComparisonJobModel.status == JobStatus(status.value))

    if cradle_id:
        query = query.filter(ComparisonJobModel.cradle_id == cradle_id)

    if comparison_type:
        query = query.filter(
            ComparisonJobModel.comparison_type == ComparisonType(comparison_type.value)
        )

    jobs = query.offset(skip).limit(limit).all()
    return jobs


@router.get("/{job_id}", response_model=ComparisonJobResponse)
async def get_comparison_job(job_id: int, db: Session = Depends(get_db)):
    """
    Get comparison job by ID with related files

    - **job_id**: Comparison job ID
    """
    job = db.query(ComparisonJobModel).filter(ComparisonJobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Comparison job not found")

    return job


@router.put("/{job_id}", response_model=ComparisonJobResponse)
async def update_comparison_job(
    job_id: int, job_update: ComparisonJobUpdate, db: Session = Depends(get_db)
):
    """
    Update comparison job

    - **job_id**: Comparison job ID to update
    - **job_update**: Job update data
    """
    job = db.query(ComparisonJobModel).filter(ComparisonJobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Comparison job not found")

    # Update fields - Fixed for Pydantic v2
    for field, value in job_update.model_dump(exclude_unset=True).items():
        if field == "status" and value:
            setattr(job, field, JobStatus(value.value))
        else:
            setattr(job, field, value)

    db.commit()
    db.refresh(job)

    logger.info(f"✅ Comparison job updated: ID={job_id}")
    return job


@router.delete("/{job_id}")
async def delete_comparison_job(job_id: int, db: Session = Depends(get_db)):
    """
    Delete comparison job and its results

    - **job_id**: Comparison job ID to delete
    """
    job = db.query(ComparisonJobModel).filter(ComparisonJobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Comparison job not found")

    # Delete job (results will be cascade deleted due to relationship)
    db.delete(job)
    db.commit()

    logger.info(f"✅ Comparison job deleted: ID={job_id}")
    return {"message": "Comparison job deleted successfully"}


# =============================================================================
# JOB CONTROL ENDPOINTS
# =============================================================================


@router.post("/{job_id}/start")
async def start_comparison_job(
    job_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """
    Start or restart comparison job processing

    - **job_id**: Comparison job ID to start
    """
    job = db.query(ComparisonJobModel).filter(ComparisonJobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Comparison job not found")

    if job.status == JobStatus.PROCESSING:
        raise HTTPException(status_code=400, detail="Job is already processing")

    if job.status == JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job is already completed")

    # Update job status - Fixed datetime
    job.status = JobStatus.PROCESSING
    job.started_at = datetime.now(timezone.utc)
    job.progress = 0.0
    job.error_message = None

    db.commit()
    db.refresh(job)

    # Start background processing
    background_tasks.add_task(start_comparison_processing, job_id)

    logger.info(f"🚀 Comparison job started: ID={job_id}")
    return {
        "message": "Comparison job started successfully",
        "job_id": job_id,
        "status": "processing",
    }


@router.post("/{job_id}/cancel")
async def cancel_comparison_job(job_id: int, db: Session = Depends(get_db)):
    """
    Cancel running comparison job

    - **job_id**: Comparison job ID to cancel
    """
    job = db.query(ComparisonJobModel).filter(ComparisonJobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Comparison job not found")

    if job.status not in [JobStatus.PENDING, JobStatus.PROCESSING]:
        raise HTTPException(
            status_code=400, detail="Job cannot be cancelled in current status"
        )

    # Update job status - Fixed datetime
    job.status = JobStatus.CANCELLED
    job.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(job)

    logger.info(f"⏹️ Comparison job cancelled: ID={job_id}")
    return {
        "message": "Comparison job cancelled successfully",
        "job_id": job_id,
        "status": "cancelled",
    }


# =============================================================================
# BATCH OPERATIONS
# =============================================================================


@router.get("/cradle/{cradle_id}", response_model=List[ComparisonJobResponse])
async def get_jobs_by_cradle_id(cradle_id: str, db: Session = Depends(get_db)):
    """
    Get all comparison jobs for a specific Cradle ID

    - **cradle_id**: Cradle ID to search for
    """
    jobs = (
        db.query(ComparisonJobModel)
        .filter(ComparisonJobModel.cradle_id == cradle_id)
        .all()
    )
    return jobs


@router.get("/stats/summary")
async def get_comparison_stats(db: Session = Depends(get_db)):
    """Get comparison jobs statistics summary"""
    total_jobs = db.query(ComparisonJobModel).count()
    pending_jobs = (
        db.query(ComparisonJobModel)
        .filter(ComparisonJobModel.status == JobStatus.PENDING)
        .count()
    )
    processing_jobs = (
        db.query(ComparisonJobModel)
        .filter(ComparisonJobModel.status == JobStatus.PROCESSING)
        .count()
    )
    completed_jobs = (
        db.query(ComparisonJobModel)
        .filter(ComparisonJobModel.status == JobStatus.COMPLETED)
        .count()
    )
    failed_jobs = (
        db.query(ComparisonJobModel)
        .filter(ComparisonJobModel.status == JobStatus.FAILED)
        .count()
    )
    cancelled_jobs = (
        db.query(ComparisonJobModel)
        .filter(ComparisonJobModel.status == JobStatus.CANCELLED)
        .count()
    )

    return {
        "total_jobs": total_jobs,
        "pending_jobs": pending_jobs,
        "processing_jobs": processing_jobs,
        "completed_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "cancelled_jobs": cancelled_jobs,
        "active_jobs": pending_jobs + processing_jobs,
        "finished_jobs": completed_jobs + failed_jobs + cancelled_jobs,
    }


# =============================================================================
# SMART PAIRING ENDPOINT
# =============================================================================


@router.post("/auto-pair/{cradle_id}")
async def auto_pair_files_for_comparison(
    cradle_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    job_name: Optional[str] = Form(None),
    comparison_type: ComparisonTypeEnum = Form(ComparisonTypeEnum.FULL),
):
    """
    Automatically pair acceptance and emission files for a Cradle ID and create comparison job

    - **cradle_id**: Cradle ID to find files for
    - **job_name**: Optional job name (auto-generated if not provided)
    - **comparison_type**: Type of comparison to perform
    """
    # Find files for this Cradle ID
    files = db.query(FileModel).filter(FileModel.cradle_id == cradle_id).all()

    if len(files) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least 2 files for comparison, found {len(files)} for Cradle ID {cradle_id}",
        )

    # Find acceptance and emission files
    acceptance_files = [f for f in files if f.file_type == FileType.ACCEPTANCE]
    emission_files = [f for f in files if f.file_type == FileType.EMISSION]

    if not acceptance_files:
        raise HTTPException(
            status_code=400, detail="No acceptance files found for this Cradle ID"
        )

    if not emission_files:
        raise HTTPException(
            status_code=400, detail="No emission files found for this Cradle ID"
        )

    # Use first acceptance and emission files (can be enhanced with smart pairing later)
    acceptance_file = acceptance_files[0]
    emission_file = emission_files[0]

    # Generate job name if not provided
    if not job_name:
        job_name = f"Auto-comparison: {cradle_id}"

    # Create comparison job
    job_data = ComparisonJobCreate(
        job_name=job_name,
        job_description=f"Auto-generated comparison for Cradle ID {cradle_id}",
        acceptance_file_id=acceptance_file.id,
        emission_file_id=emission_file.id,
        comparison_type=comparison_type,
        cradle_id=cradle_id,
        created_by="auto-pairing",
    )

    # Create and start job
    return await create_comparison_job(job_data, background_tasks, db)
