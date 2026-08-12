from services.exceptions import (
    VideoProcessingError,
    FFmpegError,
    AudioVADError,
    UnsupportedVideoFormatError,
    VideoFileNotFoundError,
    FrameExtractionError,
    ComparisonAlgorithmError,
    InsufficientVideoDataError,
    VideoResolutionMismatchError,
    ProcessingTimeoutError,
    AudioAnalysisError,
    TranscriptionError
)

def test_all_subclasses_inherit_from_video_processing_error():
    assert issubclass(FFmpegError, VideoProcessingError)
    assert issubclass(AudioVADError, VideoProcessingError)
    assert issubclass(UnsupportedVideoFormatError, VideoProcessingError)
    assert issubclass(VideoFileNotFoundError, VideoProcessingError)
    assert issubclass(FrameExtractionError, VideoProcessingError)
    assert issubclass(ComparisonAlgorithmError, VideoProcessingError)
    assert issubclass(InsufficientVideoDataError, VideoProcessingError)
    assert issubclass(VideoResolutionMismatchError, VideoProcessingError)
    assert issubclass(ProcessingTimeoutError, VideoProcessingError)
    assert issubclass(AudioAnalysisError, VideoProcessingError)
    assert issubclass(TranscriptionError, VideoProcessingError)
