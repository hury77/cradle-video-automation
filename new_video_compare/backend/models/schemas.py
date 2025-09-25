"""
New Video Compare - Pydantic Schemas
API request/response models and validation
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

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
    
    class Config:
        from_attributes = True

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
    processing_config: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = Field(None, max_length=100)
    
    @validator('acceptance_file_id', 'emission_file_id')
    def validate_file_ids(cls, v):
        if v <= 0:
            raise ValueError('File ID must be positive')
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
    
    class Config:
        from_attributes = True

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
    
    class Config:
        from_attributes = True

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
