"""
New Video Compare - Pydantic Schemas
API request/response models and validation
"""

from pydantic import BaseModel, Field, validator, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

# Import new enums from models
from .models import DifferenceType, SeverityLevel

# =============================================================================
# ENUMS (mirroring SQLAlchemy enums)
# =============================================================================




class FileTypeEnum(str, Enum):
    ACCEPTANCE = "acceptance"
    EMISSION = "emission"
    UNKNOWN = "unknown"


class FileFormatEnum(str, Enum):
    MP4 = "mp4"
    MOV = "mov"
    AVI = "avi"
    MKV = "mkv"
    MXF = "mxf"
    PRORES = "prores"
    WAV = "wav"
    MP3 = "mp3"
    AAC = "aac"
    FLAC = "flac"


class JobStatusEnum(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ComparisonTypeEnum(str, Enum):
    VIDEO_ONLY = "video_only"
    AUDIO_ONLY = "audio_only"
    FULL = "full"
    AUTOMATION = "automation"


class SensitivityLevel(str, Enum):
    """Sensitivity level for comparison thresholds"""
    LOW = "low"      # High tolerance - quick check
    MEDIUM = "medium"  # Recommended - Standard comparison
    HIGH = "high"    # Critical QA - near-perfect match




# =============================================================================
# FILE SCHEMAS
# =============================================================================


class FileBase(BaseModel):
    """Base file schema"""

    filename: str = Field(..., min_length=1, max_length=255)
    file_type: FileTypeEnum
    file_format: FileFormatEnum
    cradle_id: Optional[str] = Field(None, max_length=100)
    external_id: Optional[str] = Field(None, max_length=100)


class FileCreate(FileBase):
    """Schema for creating a new file"""

    original_name: str = Field(..., min_length=1, max_length=255)
    file_path: str = Field(..., min_length=1, max_length=500)
    file_size: int = Field(..., gt=0)

    # Optional metadata
    duration: Optional[float] = Field(None, ge=0)
    width: Optional[int] = Field(None, gt=0)
    height: Optional[int] = Field(None, gt=0)
    fps: Optional[float] = Field(None, gt=0)
    bitrate: Optional[int] = Field(None, gt=0)
    codec: Optional[str] = Field(None, max_length=50)

    # Audio metadata
    audio_channels: Optional[int] = Field(None, gt=0, le=32)
    audio_sample_rate: Optional[int] = Field(None, gt=0)
    audio_bitrate: Optional[int] = Field(None, gt=0)
    audio_codec: Optional[str] = Field(None, max_length=50)

    # Additional metadata
    file_metadata: Optional[Dict[str, Any]] = None


class FileUpdate(BaseModel):
    """Schema for updating file info"""

    filename: Optional[str] = Field(None, min_length=1, max_length=255)
    file_type: Optional[FileTypeEnum] = None
    is_processed: Optional[bool] = None
    processing_error: Optional[str] = None
    file_metadata: Optional[Dict[str, Any]] = None


class FileResponse(FileBase):
    """Schema for file API response"""

    id: int
    original_name: str
    file_path: str
    file_size: int
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    bitrate: Optional[int] = None
    codec: Optional[str] = None

    # Audio metadata
    audio_channels: Optional[int] = None
    audio_sample_rate: Optional[int] = None
    audio_bitrate: Optional[int] = None
    audio_codec: Optional[str] = None

    # Status
    is_processed: bool
    processing_error: Optional[str] = None

    # Additional metadata
    file_metadata: Optional[Dict[str, Any]] = None

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# COMPARISON JOB SCHEMAS
# =============================================================================


class ComparisonJobBase(BaseModel):
    """Base comparison job schema"""

    job_name: str = Field(..., min_length=1, max_length=200)
    job_description: Optional[str] = Field(None, max_length=1000)
    comparison_type: ComparisonTypeEnum = ComparisonTypeEnum.FULL
    cradle_id: Optional[str] = Field(None, max_length=100)


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

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# COMPARISON RESULT SCHEMAS
# =============================================================================


class ComparisonResultBase(BaseModel):
    """Base comparison result schema"""

    overall_similarity: Optional[float] = Field(None, ge=0, le=1)
    is_match: Optional[bool] = None
    confidence_score: Optional[float] = Field(None, ge=0, le=1)


class ComparisonResultCreate(ComparisonResultBase):
    """Schema for creating comparison result"""

    job_id: int = Field(..., gt=0)
    video_similarity: Optional[float] = Field(None, ge=0, le=1)
    video_differences_count: Optional[int] = Field(None, ge=0)
    video_analysis_data: Optional[Dict[str, Any]] = None

    audio_similarity: Optional[float] = Field(None, ge=0, le=1)
    audio_differences_count: Optional[int] = Field(None, ge=0)
    audio_analysis_data: Optional[Dict[str, Any]] = None

    difference_timestamps: Optional[List[float]] = None
    report_summary: Optional[str] = None
    report_data: Optional[Dict[str, Any]] = None


class ComparisonResultResponse(ComparisonResultBase):
    """Schema for comparison result API response"""

    id: int
    job_id: int

    # Analysis results
    video_similarity: Optional[float] = None
    video_differences_count: Optional[int] = None
    video_analysis_data: Optional[Dict[str, Any]] = None

    audio_similarity: Optional[float] = None
    audio_differences_count: Optional[int] = None
    audio_analysis_data: Optional[Dict[str, Any]] = None

    # Navigation data
    difference_timestamps: Optional[List[float]] = None

    # Reports
    report_summary: Optional[str] = None
    report_data: Optional[Dict[str, Any]] = None
    report_pdf_path: Optional[str] = None
    report_html_path: Optional[str] = None
    report_json_path: Optional[str] = None

    # Processing info
    analysis_duration: Optional[float] = None
    algorithms_used: Optional[List[str]] = None

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# DETAILED RESULTS SCHEMAS
# =============================================================================


# ---- Video Comparison Results ----
class VideoComparisonResultBase(BaseModel):
    """Base schema for video comparison results"""

    similarity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Video similarity score (0-1)"
    )
    total_frames: int = Field(..., gt=0, description="Total number of frames analyzed")
    different_frames: int = Field(
        ..., ge=0, description="Number of frames with differences"
    )
    resolution: Optional[str] = Field(
        None, description="Video resolution (e.g., '1920x1080')"
    )
    fps: Optional[float] = Field(None, gt=0, description="Frames per second")
    duration_seconds: Optional[float] = Field(
        None, gt=0, description="Video duration in seconds"
    )

    # Analysis metrics
    ssim_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="SSIM structural similarity score"
    )
    histogram_similarity: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Color histogram similarity"
    )
    perceptual_hash_distance: Optional[float] = Field(
        None, ge=0.0, description="Perceptual hash distance"
    )
    edge_similarity: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Edge detection similarity"
    )

    # Processing info
    algorithm_used: str = Field(
        default="SSIM+Histogram", description="Algorithm used for analysis"
    )
    processing_time_seconds: Optional[float] = Field(
        None, gt=0, description="Time taken for analysis"
    )
    frames_per_second_processed: Optional[float] = Field(
        None, gt=0, description="Processing speed (FPS)"
    )

    # Additional data
    frame_analysis_data: Optional[Dict[str, Any]] = Field(
        None, description="Detailed frame analysis data"
    )


class VideoComparisonResultCreate(VideoComparisonResultBase):
    """Schema for creating video comparison results"""

    job_id: int = Field(..., description="Associated comparison job ID")


class VideoComparisonResultUpdate(BaseModel):
    """Schema for updating video comparison results"""

    similarity_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    different_frames: Optional[int] = Field(None, ge=0)
    processing_time_seconds: Optional[float] = Field(None, gt=0)
    frame_analysis_data: Optional[Dict[str, Any]] = None


class VideoComparisonResultResponse(VideoComparisonResultBase):
    """Schema for video comparison result responses"""

    id: int
    job_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---- Audio Comparison Results ----
class AudioComparisonResultBase(BaseModel):
    """Base schema for audio comparison results"""

    similarity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Audio similarity score (0-1)"
    )
    sync_offset_ms: Optional[float] = Field(
        None, description="Audio sync offset in milliseconds"
    )

    # Technical details
    sample_rate: Optional[int] = Field(None, gt=0, description="Audio sample rate (Hz)")
    channels: Optional[int] = Field(
        None, ge=1, le=8, description="Number of audio channels"
    )
    duration_seconds: Optional[float] = Field(
        None, gt=0, description="Audio duration in seconds"
    )

    # Analysis results
    rms_difference: Optional[float] = Field(
        None, ge=0.0, description="RMS volume difference"
    )
    peak_difference: Optional[float] = Field(
        None, ge=0.0, description="Peak level difference"
    )
    spectral_similarity: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Frequency domain similarity"
    )
    mfcc_similarity: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="MFCC perceptual similarity"
    )
    cross_correlation: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Time domain correlation"
    )

    # Loudness analysis
    lufs_difference: Optional[float] = Field(
        None, description="LUFS loudness difference"
    )
    lra_difference: Optional[float] = Field(
        None, ge=0.0, description="Loudness Range difference"
    )

    # Processing info
    processing_time_seconds: Optional[float] = Field(
        None, gt=0, description="Processing time"
    )
    algorithm_used: str = Field(
        default="FFT+MFCC+CrossCorr", description="Analysis algorithm"
    )
    window_size_ms: int = Field(
        default=1000, gt=0, description="Analysis window size (ms)"
    )

    # Additional data
    audio_analysis_data: Optional[Dict[str, Any]] = Field(
        None, description="Detailed audio analysis data"
    )


class AudioComparisonResultCreate(AudioComparisonResultBase):
    """Schema for creating audio comparison results"""

    job_id: int = Field(..., description="Associated comparison job ID")


class AudioComparisonResultUpdate(BaseModel):
    """Schema for updating audio comparison results"""

    similarity_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    sync_offset_ms: Optional[float] = None
    processing_time_seconds: Optional[float] = Field(None, gt=0)
    audio_analysis_data: Optional[Dict[str, Any]] = None


class AudioComparisonResultResponse(AudioComparisonResultBase):
    """Schema for audio comparison result responses"""

    id: int
    job_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---- Difference Timestamps ----
class DifferenceTimestampBase(BaseModel):
    """Base schema for difference timestamps"""

    timestamp_seconds: float = Field(
        ..., ge=0.0, description="Timestamp where difference occurs"
    )
    duration_seconds: float = Field(
        default=1.0, gt=0, description="Duration of the difference"
    )
    difference_type: DifferenceType = Field(
        ..., description="Type of difference detected"
    )
    severity: SeverityLevel = Field(..., description="Severity level of the difference")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence in detection"
    )

    # Metrics
    similarity_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Local similarity score"
    )
    metric_value: Optional[float] = Field(None, description="Specific metric value")

    # Visual/Audio bounds
    frame_number: Optional[int] = Field(
        None, ge=0, description="Frame number for video differences"
    )
    frequency_range: Optional[str] = Field(
        None, description="Frequency range for audio differences"
    )

    # Description
    description: Optional[str] = Field(
        None, max_length=500, description="Human-readable description"
    )
    difference_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional difference metadata"
    )


class DifferenceTimestampCreate(DifferenceTimestampBase):
    """Schema for creating difference timestamps"""

    job_id: int = Field(..., description="Associated comparison job ID")


class DifferenceTimestampUpdate(BaseModel):
    """Schema for updating difference timestamps"""

    severity: Optional[SeverityLevel] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    description: Optional[str] = Field(None, max_length=500)
    difference_metadata: Optional[Dict[str, Any]] = None


class DifferenceTimestampResponse(DifferenceTimestampBase):
    """Schema for difference timestamp responses"""

    id: int
    job_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---- Combined Results Responses ----
class DetailedComparisonResults(BaseModel):
    """Combined detailed results for a comparison job"""

    job_id: int
    job_status: JobStatusEnum

    # Basic results
    overall_similarity: Optional[float] = None
    is_match: Optional[bool] = None
    confidence_score: Optional[float] = None

    # Detailed results
    video_result: Optional[VideoComparisonResultResponse] = None
    audio_result: Optional[AudioComparisonResultResponse] = None
    differences: List[DifferenceTimestampResponse] = []

    # Summary stats
    total_differences: int = 0
    critical_differences: int = 0
    high_differences: int = 0
    medium_differences: int = 0
    low_differences: int = 0

    model_config = ConfigDict(from_attributes=True)


class ResultsSummary(BaseModel):
    """Summary of results across multiple jobs"""

    total_jobs: int
    completed_jobs: int
    average_similarity: Optional[float] = None
    total_differences_found: int
    processing_time_total: float

    # Breakdown by severity
    differences_by_severity: Dict[str, int] = {}
    # Breakdown by type
    differences_by_type: Dict[str, int] = {}


# =============================================================================
# UPLOAD SCHEMAS
# =============================================================================


class FileUploadResponse(BaseModel):
    """Response schema for file upload"""

    success: bool
    message: str
    file_id: Optional[int] = None
    filename: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[FileTypeEnum] = None
    processing_started: Optional[bool] = None


class BulkUploadResponse(BaseModel):
    """Response schema for bulk file upload"""

    success: bool
    message: str
    uploaded_files: List[FileUploadResponse]
    failed_files: List[Dict[str, str]] = []
    total_files: int
    successful_uploads: int
    failed_uploads: int


# =============================================================================
# UTILITY SCHEMAS
# =============================================================================


class HealthCheckResponse(BaseModel):
    """Health check response schema"""

    status: str
    version: str
    environment: str
    upload_dir_exists: bool
    max_concurrent_jobs: int
    timestamp: str


class StatusResponse(BaseModel):
    """API status response schema"""

    api_version: str
    backend_status: str
    configuration: Dict[str, Any]
    services: Dict[str, str]
    integrations: Dict[str, str]
    endpoints: Dict[str, str]


class ErrorResponse(BaseModel):
    """Error response schema"""

    error: str
    message: str
    detail: Optional[str] = None
    timestamp: datetime


# =============================================================================
# INTEGRATION SCHEMAS
# =============================================================================


class CradleIntegrationRequest(BaseModel):
    """Schema for Cradle integration requests"""

    cradle_id: str = Field(..., min_length=1, max_length=100)
    acceptance_file_url: Optional[str] = None
    emission_file_url: Optional[str] = None
    auto_start_comparison: bool = False
    notification_webhook: Optional[str] = None


class DesktopAppMessage(BaseModel):
    """Schema for Desktop App WebSocket messages"""

    action: str
    data: Dict[str, Any]
    timestamp: Optional[datetime] = None
