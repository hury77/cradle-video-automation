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
    SensitivityLevel,
)
from models.schemas import (
    ComparisonJobCreate,
    ComparisonJobResponse,
    ComparisonJobUpdate,
    JobStatusEnum,
    ComparisonTypeEnum,
)
from config import settings
from services.comparison_service import process_comparison_job

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
    """Start background comparison processing"""
    logger.info(f"🔄 Starting comparison processing for job {job_id}")
    
    try:
        # Import here to avoid circular imports
        from services.comparison_service import process_comparison_job
        
        # Process the comparison (synchronous for prototype)
        result = await process_comparison_job(job_id)
        
        if result.get("success"):
            logger.info(f"✅ Comparison job {job_id} completed successfully")
        else:
            logger.error(f"❌ Comparison job {job_id} failed: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"❌ Error processing job {job_id}: {str(e)}")
        
        # Update job status to failed
        db = next(get_db())
        try:
            job = db.query(ComparisonJobModel).filter(ComparisonJobModel.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        finally:
            db.close()


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
        # Convert sensitivity level from value (e.g. "medium") to enum member
        sensitivity_value = job_data.sensitivity_level.value.upper()  # "medium" -> "MEDIUM"
        sensitivity_enum = SensitivityLevel[sensitivity_value]  # Get by name
        
        # Prepare processing config with OCR language
        proc_config = job_data.processing_config or {}
        if job_data.ocr_language:
            proc_config["ocr_language"] = job_data.ocr_language
        if job_data.ocr_similarity_threshold is not None:
            proc_config["ocr_similarity_threshold"] = job_data.ocr_similarity_threshold

        comparison_job = ComparisonJobModel(
            job_name=job_data.job_name,
            job_description=job_data.job_description,
            acceptance_file_id=job_data.acceptance_file_id,
            emission_file_id=job_data.emission_file_id,
            comparison_type=ComparisonType(job_data.comparison_type.value),
            sensitivity_level=sensitivity_enum,
            processing_config=proc_config,
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

    jobs = query.order_by(ComparisonJobModel.created_at.desc()).offset(skip).limit(limit).all()
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


# =============================================================================
# COMPARISON RESULTS ENDPOINT
# =============================================================================


@router.get("/{job_id}/results")
async def get_comparison_results(
    job_id: int,
    db: Session = Depends(get_db),
):
    """
    Get detailed comparison results for a job
    
    Returns video and audio analysis results from the ComparisonResult,
    VideoComparisonResult, and AudioComparisonResult tables.
    """
    from models.models import ComparisonResult, VideoComparisonResult, AudioComparisonResult, DifferenceTimestamp
    
    # Get job
    job = db.query(ComparisonJobModel).filter(ComparisonJobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400, 
            detail=f"Job not completed yet. Status: {job.status.value}"
        )
    
    # Get comparison result
    comparison_result = db.query(ComparisonResult).filter(
        ComparisonResult.job_id == job_id
    ).first()
    
    # Get video result
    video_result = db.query(VideoComparisonResult).filter(
        VideoComparisonResult.job_id == job_id
    ).first()
    
    # Get audio result
    audio_result = db.query(AudioComparisonResult).filter(
        AudioComparisonResult.job_id == job_id
    ).first()
    
    # Get difference timestamps
    differences = db.query(DifferenceTimestamp).filter(
        DifferenceTimestamp.job_id == job_id
    ).all()
    
    # Build response
    response = {
        "job_id": job_id,
        "job_name": job.job_name,
        "status": job.status.value,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "acceptance_file": {
            "id": job.acceptance_file.id,
            "filename": job.acceptance_file.filename,
            "duration": job.acceptance_file.duration,
            "width": job.acceptance_file.width,
            "height": job.acceptance_file.height,
            "fps": job.acceptance_file.fps,
        },
        "emission_file": {
            "id": job.emission_file.id,
            "filename": job.emission_file.filename,
            "duration": job.emission_file.duration,
            "width": job.emission_file.width,
            "height": job.emission_file.height,
            "fps": job.emission_file.fps,
        },
        "overall_result": None,
        "video_result": None,
        "audio_result": None,
        "differences": [],
    }
    
    # Add overall result if exists
    if comparison_result:
        response["overall_result"] = {
            "overall_similarity": comparison_result.overall_similarity,
            "is_match": comparison_result.is_match,
            "video_similarity": comparison_result.video_similarity,
            "audio_similarity": comparison_result.audio_similarity,
            "video_differences_count": comparison_result.video_differences_count,
            "audio_differences_count": comparison_result.audio_differences_count,
            "report_data": comparison_result.report_data,  # Contains OCR results
        }
    
    # Add video result if exists
    if video_result:
        response["video_result"] = {
            "similarity_score": video_result.similarity_score,
            "total_frames": video_result.total_frames,
            "different_frames": video_result.different_frames,
            "ssim_score": video_result.ssim_score,
            "histogram_similarity": video_result.histogram_similarity,
            "algorithm_used": video_result.algorithm_used,
        }
    
    # Add audio result if exists
    if audio_result:
        response["audio_result"] = {
            "similarity_score": audio_result.similarity_score,
            "spectral_similarity": audio_result.spectral_similarity,
            "mfcc_similarity": audio_result.mfcc_similarity,
            "cross_correlation": audio_result.cross_correlation,
            "sync_offset_ms": audio_result.sync_offset_ms,
        }
    
    # Add differences
    for diff in differences:
        response["differences"].append({
            "timestamp_seconds": diff.timestamp_seconds,
            "duration_seconds": diff.duration_seconds,
            "difference_type": diff.difference_type.value,
            "severity": diff.severity.value,
            "confidence": diff.confidence,
            "description": diff.description,
        })
    
    logger.info(f"📊 Returning results for job {job_id}")
    return response


@router.post("/{job_id}/reanalyze")
async def reanalyze_job(
    job_id: int,
    sensitivity_level: str = Form(...),
    comparison_type: str = Form(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """
    Re-analyze an existing comparison with a different sensitivity level.
    Creates a new job with the same files but different settings.
    """
    from services.comparison_service import get_comparison_service
    
    # Get original job
    original_job = db.query(ComparisonJobModel).filter(
        ComparisonJobModel.id == job_id
    ).first()
    
    if not original_job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Map sensitivity string to enum
    sensitivity_map = {
        "low": SensitivityLevel.LOW,
        "medium": SensitivityLevel.MEDIUM,
        "high": SensitivityLevel.HIGH,
    }
    new_sensitivity = sensitivity_map.get(sensitivity_level.lower())
    if not new_sensitivity:
        raise HTTPException(status_code=400, detail=f"Invalid sensitivity level: {sensitivity_level}")
        
    # Determine comparison type
    new_comparison_type = original_job.comparison_type
    if comparison_type:
        try:
            new_comparison_type = ComparisonType(comparison_type.lower())
        except ValueError:
             raise HTTPException(status_code=400, detail=f"Invalid comparison type: {comparison_type}")

    # Create new job with same files but new sensitivity/type
    new_job = ComparisonJobModel(
        job_name=f"{original_job.job_name} (re-analyzed: {sensitivity_level}, {new_comparison_type.value})",
        job_description=f"Re-analysis of job #{job_id} with {sensitivity_level} sensitivity ({new_comparison_type.value})",
        acceptance_file_id=original_job.acceptance_file_id,
        emission_file_id=original_job.emission_file_id,
        comparison_type=new_comparison_type,
        sensitivity_level=new_sensitivity,
        processing_config=original_job.processing_config,
        cradle_id=original_job.cradle_id,
        created_by=original_job.created_by,
        status=JobStatus.PENDING,
    )
    
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    logger.info(f"🔄 Created re-analysis job {new_job.id} from job {job_id} with sensitivity {sensitivity_level} and type {new_comparison_type.value}")
    
    # Start processing in background (using ProcessPoolExecutor wrapper)
    background_tasks.add_task(process_comparison_job, new_job.id)
    
    return {
        "message": "Re-analysis started",
        "original_job_id": job_id,
        "new_job_id": new_job.id,
        "sensitivity_level": sensitivity_level,
    }


@router.post("/{job_id}/cancel", response_model=ComparisonJobResponse)
async def cancel_comparison_job(
    job_id: int,
    db: Session = Depends(get_db),
):
    """Cancel a running comparison job"""
    job = db.query(ComparisonJobModel).filter(ComparisonJobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail="Job is not in a cancellable state")

    job.status = JobStatus.CANCELLED
    job.error_message = "Cancelled by user"
    job.completed_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(job)
    
    return job


@router.post("/{job_id}/retry", response_model=ComparisonJobResponse)
async def retry_comparison_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Retry a failed or cancelled comparison job"""
    job = db.query(ComparisonJobModel).filter(ComparisonJobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check if files still exist
    try:
        validate_files_for_comparison(job.acceptance_file, job.emission_file)
    except HTTPException as e:
        raise HTTPException(status_code=400, detail=f"Cannot retry job (files missing): {e.detail}")

    # Reset job state
    job.status = JobStatus.PENDING
    job.error_message = None
    job.progress = 0.0
    job.started_at = None
    job.completed_at = None
    job.processing_duration = None
    
    # Clear previous results
    job.video_result = None
    job.audio_result = None
    job.differences = []
    job.results = []
    
    db.commit()
    db.refresh(job)
    
    # Start processing in background
    background_tasks.add_task(start_comparison_processing, job.id)
    
    return job
