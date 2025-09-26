"""
New Video Compare - Services Package
Video and audio processing services
"""

from .video_processor import VideoProcessor
from .exceptions import (
    VideoProcessingError,
    FFmpegError,
    UnsupportedVideoFormatError,
    VideoFileNotFoundError,
    FrameExtractionError,
    ComparisonAlgorithmError,
    InsufficientVideoDataError,
    VideoResolutionMismatchError,
    ProcessingTimeoutError,
)

__all__ = [
    "VideoProcessor",
    "VideoProcessingError",
    "FFmpegError",
    "UnsupportedVideoFormatError",
    "VideoFileNotFoundError",
    "FrameExtractionError",
    "ComparisonAlgorithmError",
    "InsufficientVideoDataError",
    "VideoResolutionMismatchError",
    "ProcessingTimeoutError",
]
