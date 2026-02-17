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
from datetime import datetime, timezone
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
    AUTOMATION = "automation"  # Sequential: Video HIGH → gc → Full Audio (Demucs+Whisper) → 1 job


class SensitivityLevel(enum.Enum):
    """Sensitivity level for comparison thresholds"""
    
    LOW = "low"      # High tolerance - quick check, SSIM >= 0.85
    MEDIUM = "medium"  # Recommended - SSIM >= 0.92
    HIGH = "high"    # Critical QA - SSIM >= 0.98


class DifferenceType(enum.Enum):
    """Types of differences found in comparison"""

    VIDEO_FRAME = "video_frame"
    AUDIO_LEVEL = "audio_level"
    AUDIO_SPECTRAL = "audio_spectral"
    SYNC_ISSUE = "sync_issue"
    CONTENT_MISSING = "content_missing"
    QUALITY_DEGRADATION = "quality_degradation"


class SeverityLevel(enum.Enum):
    """Severity levels for differences"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


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
    sensitivity_level = Column(
        Enum(SensitivityLevel), nullable=False, default=SensitivityLevel.MEDIUM
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

    # NEW: Detailed results relationships
    video_result = relationship(
        "VideoComparisonResult",
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan",
    )
    audio_result = relationship(
        "AudioComparisonResult",
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan",
    )
    differences = relationship(
        "DifferenceTimestamp", back_populates="job", cascade="all, delete-orphan"
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
# NEW: DETAILED RESULTS MODELS
# =============================================================================


class VideoComparisonResult(Base):
    """Detailed video comparison results"""

    __tablename__ = "video_comparison_results"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(
        Integer,
        ForeignKey("comparison_jobs.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Overall metrics
    similarity_score = Column(Float, nullable=False)  # 0.0 - 1.0
    total_frames = Column(Integer, nullable=False)
    different_frames = Column(Integer, nullable=False)

    # Technical details
    resolution = Column(String(20), nullable=True)  # "1920x1080"
    fps = Column(Float, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Analysis metrics
    ssim_score = Column(Float, nullable=True)  # Structural similarity
    histogram_similarity = Column(Float, nullable=True)  # Color histogram
    perceptual_hash_distance = Column(Float, nullable=True)  # pHash distance
    edge_similarity = Column(Float, nullable=True)  # Edge detection similarity

    # Processing info
    algorithm_used = Column(String(100), default="SSIM+Histogram")
    processing_time_seconds = Column(Float, nullable=True)
    frames_per_second_processed = Column(Float, nullable=True)

    # Frame analysis data (JSON for detailed info)
    frame_analysis_data = Column(JSON, nullable=True)

    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationship
    job = relationship("ComparisonJob", back_populates="video_result")

    def __repr__(self):
        return f"<VideoComparisonResult(job_id={self.job_id}, similarity={self.similarity_score:.3f})>"


class AudioComparisonResult(Base):
    """Detailed audio comparison results"""

    __tablename__ = "audio_comparison_results"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(
        Integer,
        ForeignKey("comparison_jobs.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Overall metrics
    similarity_score = Column(Float, nullable=False)  # 0.0 - 1.0
    sync_offset_ms = Column(
        Float, nullable=True
    )  # Audio sync difference in milliseconds

    # Audio technical details
    sample_rate = Column(Integer, nullable=True)  # 44100, 48000 etc.
    channels = Column(Integer, nullable=True)  # 1=mono, 2=stereo
    duration_seconds = Column(Float, nullable=True)

    # Analysis results
    rms_difference = Column(Float, nullable=True)  # RMS volume difference
    peak_difference = Column(Float, nullable=True)  # Peak level difference
    spectral_similarity = Column(Float, nullable=True)  # Frequency domain similarity
    mfcc_similarity = Column(
        Float, nullable=True
    )  # Mel-frequency cepstral coefficients
    cross_correlation = Column(Float, nullable=True)  # Time domain correlation

    # Loudness analysis (EBU R128 standard)
    lufs_difference = Column(
        Float, nullable=True
    )  # Loudness Units Full Scale difference
    lra_difference = Column(Float, nullable=True)  # Loudness Range difference

    # Processing info
    processing_time_seconds = Column(Float, nullable=True)
    algorithm_used = Column(String(100), default="FFT+MFCC+CrossCorr")
    window_size_ms = Column(Integer, default=1000)  # Analysis window size

    # Detailed analysis data (JSON)
    audio_analysis_data = Column(JSON, nullable=True)

    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationship
    job = relationship("ComparisonJob", back_populates="audio_result")

    def __repr__(self):
        return f"<AudioComparisonResult(job_id={self.job_id}, similarity={self.similarity_score:.3f})>"


class DifferenceTimestamp(Base):
    """Timestamps where differences were detected"""

    __tablename__ = "difference_timestamps"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(
        Integer, ForeignKey("comparison_jobs.id"), nullable=False, index=True
    )

    # Timestamp info
    timestamp_seconds = Column(Float, nullable=False, index=True)
    duration_seconds = Column(Float, default=1.0)  # Duration of the difference

    # Difference details
    difference_type = Column(Enum(DifferenceType), nullable=False, index=True)
    severity = Column(Enum(SeverityLevel), nullable=False, index=True)
    confidence = Column(Float, default=1.0)  # 0.0 - 1.0

    # Metrics for this timestamp
    similarity_score = Column(
        Float, nullable=True
    )  # Local similarity at this timestamp
    metric_value = Column(
        Float, nullable=True
    )  # Specific metric value (depends on type)

    # Visual/Audio bounds (for UI highlighting)
    frame_number = Column(Integer, nullable=True)  # For video differences
    frequency_range = Column(String(50), nullable=True)  # "20Hz-20kHz" for audio

    # Description and metadata
    description = Column(Text, nullable=True)
    difference_metadata = Column(
        JSON, nullable=True
    )  # Additional difference-specific data

    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationship
    job = relationship("ComparisonJob", back_populates="differences")

    def __repr__(self):
        return f"<DifferenceTimestamp(job_id={self.job_id}, time={self.timestamp_seconds}s, type={self.difference_type.value})>"


# =============================================================================
# INDEXES AND CONSTRAINTS
# =============================================================================

# Additional indexes will be created here if needed
# For now, the indexes are defined in column definitions above
