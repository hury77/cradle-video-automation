from pydantic import BaseModel, Field, ConfigDict, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from .enums import JobStatusEnum, ComparisonTypeEnum, SensitivityLevel
from .files import FileResponse
# COMPARISON JOB SCHEMAS
# =============================================================================


class ComparisonJobBase(BaseModel):
    """Base comparison job schema"""

    job_name: str = Field(..., min_length=1, max_length=200)
    job_description: Optional[str] = Field(None, max_length=1000)
    comparison_type: ComparisonTypeEnum = ComparisonTypeEnum.FULL
    cradle_id: Optional[str] = Field(None, max_length=100)
    client_name: Optional[str] = Field(None, max_length=200)


class ComparisonJobCreate(ComparisonJobBase):
    """Schema for creating comparison job"""

    acceptance_file_id: int = Field(..., gt=0)
    emission_file_id: int = Field(..., gt=0)
    sensitivity_level: SensitivityLevel = Field(
        default=SensitivityLevel.MEDIUM,
        description="Comparison sensitivity: low (tolerant), medium (recommended), high (strict)"
    )
    # OCR fields removed — visual differences detected by SSIM+pixel diff
    processing_config: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = Field(None, max_length=100)

    @validator("acceptance_file_id", "emission_file_id")
    def validate_file_ids(cls, v):
        if v <= 0:
            raise ValueError("File ID must be positive")
        return v


class ComparisonJobUpdate(BaseModel):
    """Schema for updating comparison job"""

    job_name: Optional[str] = Field(None, min_length=1, max_length=200)
    job_description: Optional[str] = Field(None, max_length=1000)
    status: Optional[JobStatusEnum] = None
    progress: Optional[float] = Field(None, ge=0, le=100)
    error_message: Optional[str] = None
    processing_config: Optional[Dict[str, Any]] = None


class JobMetricsResponse(BaseModel):
    """Simplified metrics for job list view"""

    video_similarity: Optional[float] = None
    audio_similarity: Optional[float] = None
    overall_similarity: Optional[float] = None



class ComparisonJobResponse(ComparisonJobBase):
    """Schema for comparison job API response"""

    id: int
    acceptance_file_id: int
    emission_file_id: int
    sensitivity_level: Optional[SensitivityLevel] = SensitivityLevel.MEDIUM
    status: JobStatusEnum
    progress: float
    error_message: Optional[str] = None
    processing_config: Optional[Dict[str, Any]] = None

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_duration: Optional[float] = None

    # User info
    created_by: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Related files (optional, can be loaded)
    acceptance_file: Optional[FileResponse] = None
    emission_file: Optional[FileResponse] = None

    # Results summary (optional metrics)
    metrics: Optional[JobMetricsResponse] = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
