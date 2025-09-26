"""
New Video Compare - Video Utilities
High-level video file operations and validation
"""

import os
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict

from .ffmpeg_utils import FFmpegUtils, VideoMetadata
from ..exceptions import (
    VideoFileNotFoundError, 
    UnsupportedVideoFormatError,
    VideoResolutionMismatchError,
    InsufficientVideoDataError
)


logger = logging.getLogger(__name__)


@dataclass
class VideoInfo:
    """Extended video information"""
    file_path: str
    metadata: VideoMetadata
    file_hash: str
    is_valid: bool
    validation_errors: List[str]


class VideoUtils:
    """High-level video utilities"""
    
    # Supported video formats
    SUPPORTED_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.mxf', '.prores'}
    SUPPORTED_CODECS = {'h264', 'h265', 'prores', 'dnxhd', 'mpeg2video'}
    
    def __init__(self, ffmpeg_utils: Optional[FFmpegUtils] = None):
        """
        Initialize VideoUtils
        
        Args:
            ffmpeg_utils: FFmpeg utilities instance
        """
        self.ffmpeg = ffmpeg_utils or FFmpegUtils()
    
    def validate_video_file(self, video_path: str) -> VideoInfo:
        """
        Comprehensive video file validation
        
        Args:
            video_path: Path to video file
            
        Returns:
            VideoInfo with validation results
        """
        video_path = Path(video_path)
        errors = []
        is_valid = True
        metadata = None
        file_hash = None
        
        logger.info(f"🔍 Validating video file: {video_path.name}")
        
        try:
            # Check file existence
            if not video_path.exists():
                errors.append(f"File does not exist: {video_path}")
                is_valid = False
                raise VideoFileNotFoundError(f"Video file not found: {video_path}")
            
            # Check file extension
            if video_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                errors.append(f"Unsupported file extension: {video_path.suffix}")
                is_valid = False
            
            # Check file size
            file_size = video_path.stat().st_size
            if file_size == 0:
                errors.append("File is empty")
                is_valid = False
            elif file_size < 1024:  # Less than 1KB
                errors.append("File is too small to be a valid video")
                is_valid = False
            
            # Get file hash
            file_hash = self.calculate_file_hash(str(video_path))
            
            # Extract metadata
            metadata = self.ffmpeg.get_video_metadata(str(video_path))
            
            # Validate video properties
            if metadata.duration <= 0:
                errors.append("Invalid video duration")
                is_valid = False
            
            if metadata.width <= 0 or metadata.height <= 0:
                errors.append("Invalid video resolution")
                is_valid = False
            
            if metadata.fps <= 0:
                errors.append("Invalid frame rate")
                is_valid = False
            
            # Check codec support
            if metadata.codec.lower() not in self.SUPPORTED_CODECS:
                errors.append(f"Unsupported video codec: {metadata.codec}")
                # Not marking as invalid - we might still be able to process it
            
            # Minimum duration check (1 second)
            if metadata.duration < 1.0:
                errors.append("Video too short (minimum 1 second required)")
                is_valid = False
            
            # Maximum duration check (4 hours)
            if metadata.duration > 14400:  # 4 hours
                errors.append("Video too long (maximum 4 hours supported)")
                is_valid = False
            
            # Resolution checks
            if metadata.width > 7680 or metadata.height > 4320:  # 8K limit
                errors.append("Resolution too high (maximum 8K supported)")
                is_valid = False
            
            if metadata.width < 320 or metadata.height < 240:  # Minimum resolution
                errors.append("Resolution too low (minimum 320x240 required)")
                is_valid = False
            
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
            is_valid = False
        
        # Create VideoInfo object
        video_info = VideoInfo(
            file_path=str(video_path),
            metadata=metadata,
            file_hash=file_hash,
            is_valid=is_valid,
            validation_errors=errors
        )
        
        if is_valid:
            logger.info(f"✅ Video validation successful: {video_path.name}")
        else:
            logger.warning(f"⚠️ Video validation failed: {video_path.name} - {errors}")
        
        return video_info
    
    def calculate_file_hash(self, file_path: str, algorithm: str = "sha256") -> str:
        """
        Calculate file hash for integrity verification
        
        Args:
            file_path: Path to file
            algorithm: Hash algorithm (md5, sha1, sha256)
            
        Returns:
            File hash as hex string
        """
        hash_func = hashlib.new(algorithm)
        
        try:
            with open(file_path, 'rb') as f:
                # Read in chunks to handle large files
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_func.update(chunk)
            
            return hash_func.hexdigest()
            
        except Exception as e:
            logger.error(f"Hash calculation failed for {file_path}: {e}")
            return ""
    
    def compare_video_compatibility(self, video1_path: str, video2_path: str) -> Dict[str, Any]:
        """
        Check if two videos are compatible for comparison
        
        Args:
            video1_path: Path to first video (acceptance)
            video2_path: Path to second video (emission)
            
        Returns:
            Compatibility analysis results
            
        Raises:
            VideoResolutionMismatchError: If videos have incompatible properties
        """
        logger.info(f"🔄 Checking compatibility between videos")
        
        # Validate both videos
        video1_info = self.validate_video_file(video1_path)
        video2_info = self.validate_video_file(video2_path)
        
        compatibility = {
            "compatible": True,
            "warnings": [],
            "errors": [],
            "video1_info": asdict(video1_info) if video1_info.metadata else None,
            "video2_info": asdict(video2_info) if video2_info.metadata else None,
            "resolution_match": False,
            "fps_match": False,
            "duration_match": False,
            "codec_match": False
        }
        
        # Check if videos are valid
        if not video1_info.is_valid:
            compatibility["errors"].extend([f"Video 1: {e}" for e in video1_info.validation_errors])
            compatibility["compatible"] = False
        
        if not video2_info.is_valid:
            compatibility["errors"].extend([f"Video 2: {e}" for e in video2_info.validation_errors])
            compatibility["compatible"] = False
        
        if not compatibility["compatible"]:
            return compatibility
        
        meta1 = video1_info.metadata
        meta2 = video2_info.metadata
        
        # Resolution comparison
        if meta1.width == meta2.width and meta1.height == meta2.height:
            compatibility["resolution_match"] = True
        else:
            compatibility["warnings"].append(
                f"Resolution mismatch: {meta1.width}x{meta1.height} vs {meta2.width}x{meta2.height}"
            )
            # Different resolutions can still be compared, but with scaling
            
        # FPS comparison
        fps_diff = abs(meta1.fps - meta2.fps)
        if fps_diff < 0.1:  # Allow small FPS differences
            compatibility["fps_match"] = True
        else:
            compatibility["warnings"].append(
                f"FPS mismatch: {meta1.fps} vs {meta2.fps}"
            )
        
        # Duration comparison
        duration_diff = abs(meta1.duration - meta2.duration)
        if duration_diff < 1.0:  # Allow 1 second difference
            compatibility["duration_match"] = True
        else:
            compatibility["warnings"].append(
                f"Duration mismatch: {meta1.duration}s vs {meta2.duration}s"
            )
            # Different durations are OK, we'll compare the shorter length
        
        # Codec comparison
        if meta1.codec.lower() == meta2.codec.lower():
            compatibility["codec_match"] = True
        else:
            compatibility["warnings"].append(
                f"Codec mismatch: {meta1.codec} vs {meta2.codec}"
            )
        
        # Severe incompatibilities that prevent comparison
        if abs(meta1.width - meta2.width) > meta1.width * 0.5:  # >50% size difference
            compatibility["errors"].append("Videos have drastically different resolutions")
            compatibility["compatible"] = False
        
        if duration_diff > min(meta1.duration, meta2.duration) * 0.5:  # >50% duration difference
            compatibility["errors"].append("Videos have drastically different durations")
            compatibility["compatible"] = False
        
        logger.info(f"✅ Compatibility check complete: {'Compatible' if compatibility['compatible'] else 'Incompatible'}")
        
        return compatibility
    
    def get_video_summary(self, video_path: str) -> Dict[str, Any]:
        """
        Get comprehensive video summary
        
        Args:
            video_path: Path to video file
            
        Returns:
            Video summary dictionary
        """
        video_info = self.validate_video_file(video_path)
        
        if not video_info.metadata:
            return {"error": "Could not extract video metadata"}
        
        metadata = video_info.metadata
        
        return {
            "filename": metadata.filename,
            "file_path": video_path,
            "file_hash": video_info.file_hash,
            "is_valid": video_info.is_valid,
            "validation_errors": video_info.validation_errors,
            "technical_info": {
                "duration": metadata.duration,
                "resolution": f"{metadata.width}x{metadata.height}",
                "fps": metadata.fps,
                "codec": metadata.codec,
                "bitrate": metadata.bitrate,
                "format": metadata.format_name,
                "file_size": metadata.file_size,
                "file_size_mb": round(metadata.file_size / 1024 / 1024, 2)
            },
            "audio_info": {
                "has_audio": metadata.audio_codec is not None,
                "codec": metadata.audio_codec,
                "channels": metadata.audio_channels,
                "sample_rate": metadata.audio_sample_rate
            },
            "analysis_readiness": {
                "ready_for_comparison": video_info.is_valid,
                "estimated_frame_count": int(metadata.duration * metadata.fps),
                "processing_complexity": self._estimate_processing_complexity(metadata)
            }
        }
    
    def _estimate_processing_complexity(self, metadata: VideoMetadata) -> str:
        """Estimate processing complexity based on video properties"""
        total_pixels = metadata.width * metadata.height * metadata.duration * metadata.fps
        
        if total_pixels < 100_000_000:  # ~100M pixels
            return "low"
        elif total_pixels < 1_000_000_000:  # ~1B pixels  
            return "medium"
        elif total_pixels < 10_000_000_000:  # ~10B pixels
            return "high"
        else:
            return "very_high"
    
    def cleanup_temp_files(self, directory: str, pattern: str = "*_frame_*.jpg") -> int:
        """
        Clean up temporary files (extracted frames, etc.)
        
        Args:
            directory: Directory to clean
            pattern: File pattern to match
            
        Returns:
            Number of files deleted
        """
        directory = Path(directory)
        deleted_count = 0
        
        if not directory.exists():
            return 0
        
        try:
            for file_path in directory.glob(pattern):
                if file_path.is_file():
                    file_path.unlink()
                    deleted_count += 1
            
            logger.info(f"🧹 Cleaned up {deleted_count} temporary files from {directory}")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
        
        return deleted_count
