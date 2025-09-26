"""
New Video Compare - Processing Exceptions
Custom exceptions for video/audio processing
"""


class VideoProcessingError(Exception):
    """Base exception for video processing errors"""

    pass


class FFmpegError(VideoProcessingError):
    """FFmpeg execution errors"""

    pass


class UnsupportedVideoFormatError(VideoProcessingError):
    """Unsupported video format errors"""

    pass


class VideoFileNotFoundError(VideoProcessingError):
    """Video file not found errors"""

    pass


class FrameExtractionError(VideoProcessingError):
    """Frame extraction errors"""

    pass


class ComparisonAlgorithmError(VideoProcessingError):
    """Video comparison algorithm errors"""

    pass


class InsufficientVideoDataError(VideoProcessingError):
    """Insufficient video data for comparison"""

    pass


class VideoResolutionMismatchError(VideoProcessingError):
    """Video resolution mismatch between acceptance and emission files"""

    pass


class ProcessingTimeoutError(VideoProcessingError):
    """Processing timeout errors"""

    pass
