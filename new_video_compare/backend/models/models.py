"""
New Video Compare - SQLAlchemy Models
Database models for files, comparisons, and results
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Text,
    Float,
    ForeignKey,
    JSON,
    Enum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from .database import Base

# =============================================================================
# ENUMS
# =============================================================================


class FileType(enum.Enum):
    """File type enumeration"""

    ACCEPTANCE = "acceptance"
    EMISSION = "emission"
    UNKNOWN = "unknown"


class FileFormat(enum.Enum):
    """Supported file formats"""

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


class JobStatus(enum.Enum):
    """Comparison job status"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ComparisonType(enum.Enum):
    """Type of comparison"""

    VIDEO_ONLY = "video_only"
    AUDIO_ONLY = "audio_only"
    FULL = "full"  # Both video and audio


# =============================================================================
# MODELS
# =============================================================================


class File(Base):
    """File model - represents uploaded video/audio files"""

    __tablename__ = "files"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # File identification
    filename = Column(String(255), nullable=False, index=True)
    original_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False, unique=True)
    file_type = Column(Enum(FileType), nullable=False, index=True)
    file_format = Column(Enum(FileFormat), nullable=False)

    # File metadata
    file_size = Column(Integer, nullable=False)  # bytes
    duration = Column(Float, nullable=True)  # seconds
    width = Column(Integer, nullable=True)  # video width
    height = Column(Integer, nullable=True)  # video height
    fps = Column(Float, nullable=True)  # frames per second
    bitrate = Column(Integer, nullable=True)  # bits per second
    codec = Column(String(50), nullable=True)

    # Audio metadata (for audio files or video with audio)
    audio_channels = Column(Integer, nullable=True)
    audio_sample_rate = Column(Integer, nullable=True)
    audio_bitrate = Column(Integer, nullable=True)
    audio_codec = Column(String(50), nullable=True)

    # Integration fields
    cradle_id = Column(String(100), nullable=True, index=True)  # From Cradle system
    external_id = Column(String(100), nullable=True, index=True)  # External system ID

    # Processing status
    is_processed = Column(Boolean, default=False, index=True)
    processing_error = Column(Text, nullable=True)

    # Additional metadata (JSON field for flexible data)
    file_metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    acceptance_jobs = relationship(
        "ComparisonJob",
        foreign_keys="ComparisonJob.acceptance_file_id",
        back_populates="acceptance_file",
    )
    emission_jobs = relationship(
        "ComparisonJob",
        foreign_keys="ComparisonJob.emission_file_id",
        back_populates="emission_file",
    )

    def __repr__(self):
        return f"<File(id={self.id}, filename='{self.filename}', type={self.file_type.value})>"


class ComparisonJob(Base):
    """Comparison job model - represents video/audio comparison tasks"""

    __tablename__ = "comparison_jobs"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Job identification
    job_name = Column(String(200), nullable=False)
    job_description = Column(Text, nullable=True)

    # File references
    acceptance_file_id = Column(
        Integer, ForeignKey("files.id"), nullable=False, index=True
    )
    emission_file_id = Column(
        Integer, ForeignKey("files.id"), nullable=False, index=True
    )

    # Job configuration
    comparison_type = Column(
        Enum(ComparisonType), nullable=False, default=ComparisonType.FULL
    )

    # Processing settings (JSON for flexibility)
    processing_config = Column(JSON, nullable=True)

    # Job status
    status = Column(
        Enum(JobStatus), nullable=False, default=JobStatus.PENDING, index=True
    )
    progress = Column(Float, default=0.0)  # 0-100%
    error_message = Column(Text, nullable=True)

    # Processing times
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    processing_duration = Column(Float, nullable=True)  # seconds

    # Integration fields
    cradle_id = Column(String(100), nullable=True, index=True)
    external_job_id = Column(String(100), nullable=True, index=True)

    # User/system identification
    created_by = Column(String(100), nullable=True)  # User ID or system name

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    acceptance_file = relationship(
        "File", foreign_keys=[acceptance_file_id], back_populates="acceptance_jobs"
    )
    emission_file = relationship(
        "File", foreign_keys=[emission_file_id], back_populates="emission_jobs"
    )
    results = relationship(
        "ComparisonResult", back_populates="job", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<ComparisonJob(id={self.id}, name='{self.job_name}', status={self.status.value})>"


class ComparisonResult(Base):
    """Comparison result model - stores analysis results"""

    __tablename__ = "comparison_results"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Job reference
    job_id = Column(
        Integer, ForeignKey("comparison_jobs.id"), nullable=False, index=True
    )

    # Overall results
    overall_similarity = Column(
        Float, nullable=True
    )  # 0-1 (0 = completely different, 1 = identical)
    is_match = Column(Boolean, nullable=True)  # Final decision
    confidence_score = Column(Float, nullable=True)  # 0-1

    # Video analysis results
    video_similarity = Column(Float, nullable=True)
    video_differences_count = Column(Integer, nullable=True)
    video_analysis_data = Column(JSON, nullable=True)  # Detailed video analysis

    # Audio analysis results
    audio_similarity = Column(Float, nullable=True)
    audio_differences_count = Column(Integer, nullable=True)
    audio_analysis_data = Column(JSON, nullable=True)  # Detailed audio analysis

    # Difference highlights (for UI navigation)
    difference_timestamps = Column(
        JSON, nullable=True
    )  # Array of timestamps with differences

    # Report data
    report_summary = Column(Text, nullable=True)
    report_data = Column(JSON, nullable=True)  # Full report data

    # Export paths
    report_pdf_path = Column(String(500), nullable=True)
    report_html_path = Column(String(500), nullable=True)
    report_json_path = Column(String(500), nullable=True)

    # Processing metadata
    analysis_duration = Column(Float, nullable=True)  # seconds
    algorithms_used = Column(JSON, nullable=True)  # List of algorithms

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    job = relationship("ComparisonJob", back_populates="results")

    def __repr__(self):
        return f"<ComparisonResult(id={self.id}, job_id={self.job_id}, similarity={self.overall_similarity})>"


# =============================================================================
# INDEXES AND CONSTRAINTS
# =============================================================================

# Additional indexes will be created here if needed
# For now, the indexes are defined in column definitions above
