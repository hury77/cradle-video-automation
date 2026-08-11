from enum import Enum
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
    GIF = "gif"
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
    VO_TRANSCRIPT = "vo_transcript"


class SensitivityLevel(str, Enum):
    """Sensitivity level for comparison thresholds"""
    LOW = "low"      # High tolerance - quick check
    MEDIUM = "medium"  # Recommended - Standard comparison
    HIGH = "high"    # Critical QA - near-perfect match
    AUTOMATION = "automation" # Strict thresholds for autonomous mode


class DecisionVerdictEnum(str, Enum):
    """QA decision verdict"""
    APPROVE = "approve"
    REJECT = "reject"
    REVIEW = "review"


class HallucinationMatchTypeEnum(str, Enum):
    """How to match whisper hallucinations"""
    EXACT = "exact"
    CONTAINS = "contains"




# =============================================================================
