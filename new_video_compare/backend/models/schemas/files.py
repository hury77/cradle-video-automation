from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from .enums import FileTypeEnum, FileFormatEnum
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
