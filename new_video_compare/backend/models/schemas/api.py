from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from .enums import FileTypeEnum, FileFormatEnum
from .files import FileResponse
from .jobs import ComparisonJobResponse
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
