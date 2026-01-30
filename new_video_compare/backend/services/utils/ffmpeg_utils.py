"""
New Video Compare - FFmpeg Utilities
FFmpeg wrapper for video processing operations
"""

import subprocess
import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from ..exceptions import (
    FFmpegError,
    VideoFileNotFoundError,
    UnsupportedVideoFormatError,
)


logger = logging.getLogger(__name__)


@dataclass
class VideoMetadata:
    """Video metadata extracted from FFmpeg"""

    filename: str
    duration: float
    width: int
    height: int
    fps: float
    bitrate: Optional[int]
    codec: str
    audio_codec: Optional[str]
    audio_channels: Optional[int]
    audio_sample_rate: Optional[int]
    format_name: str
    file_size: int


class FFmpegUtils:
    """FFmpeg utilities for video processing"""

    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        """
        Initialize FFmpeg utilities

        Args:
            ffmpeg_path: Path to ffmpeg executable
            ffprobe_path: Path to ffprobe executable
        """
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path

        # Validate FFmpeg installation
        self._validate_ffmpeg()

    def _validate_ffmpeg(self) -> None:
        """Validate FFmpeg installation"""
        try:
            # Check ffmpeg
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise FFmpegError(f"FFmpeg not found at: {self.ffmpeg_path}")

            # Check ffprobe
            result = subprocess.run(
                [self.ffprobe_path, "-version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise FFmpegError(f"FFprobe not found at: {self.ffprobe_path}")

            logger.info("✅ FFmpeg validation successful")

        except subprocess.TimeoutExpired:
            raise FFmpegError("FFmpeg validation timeout")
        except FileNotFoundError:
            raise FFmpegError(
                f"FFmpeg not found. Please install FFmpeg and ensure it's in PATH or provide correct path.\n"
                f"FFmpeg path: {self.ffmpeg_path}\n"
                f"FFprobe path: {self.ffprobe_path}"
            )
        except Exception as e:
            raise FFmpegError(f"FFmpeg validation failed: {e}")

    def get_video_metadata(self, video_path: str) -> VideoMetadata:
        """
        Extract video metadata using ffprobe

        Args:
            video_path: Path to video file

        Returns:
            VideoMetadata object with video information

        Raises:
            VideoFileNotFoundError: If video file doesn't exist
            FFmpegError: If ffprobe fails
        """
        video_path = Path(video_path)

        if not video_path.exists():
            raise VideoFileNotFoundError(f"Video file not found: {video_path}")

        logger.info(f"📊 Extracting metadata from: {video_path.name}")

        try:
            # FFprobe command for JSON metadata
            cmd = [
                self.ffprobe_path,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(video_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                raise FFmpegError(f"FFprobe failed: {result.stderr}")

            # Parse JSON output
            probe_data = json.loads(result.stdout)

            # Extract video stream
            video_stream = None
            audio_stream = None

            for stream in probe_data.get("streams", []):
                if stream.get("codec_type") == "video" and video_stream is None:
                    video_stream = stream
                elif stream.get("codec_type") == "audio" and audio_stream is None:
                    audio_stream = stream

            if not video_stream:
                raise UnsupportedVideoFormatError(
                    f"No video stream found in: {video_path}"
                )

            # Extract format info
            format_info = probe_data.get("format", {})

            # Build metadata object
            metadata = VideoMetadata(
                filename=video_path.name,
                duration=float(format_info.get("duration", 0)),
                width=int(video_stream.get("width", 0)),
                height=int(video_stream.get("height", 0)),
                fps=self._extract_fps(video_stream),
                bitrate=(
                    int(format_info.get("bit_rate", 0))
                    if format_info.get("bit_rate")
                    else None
                ),
                codec=video_stream.get("codec_name", "unknown"),
                audio_codec=audio_stream.get("codec_name") if audio_stream else None,
                audio_channels=(
                    int(audio_stream.get("channels", 0)) if audio_stream else None
                ),
                audio_sample_rate=(
                    int(audio_stream.get("sample_rate", 0)) if audio_stream else None
                ),
                format_name=format_info.get("format_name", "unknown"),
                file_size=int(format_info.get("size", 0)),
            )

            logger.info(
                f"✅ Metadata extracted: {metadata.width}x{metadata.height} @ {metadata.fps}fps"
            )
            return metadata

        except json.JSONDecodeError as e:
            raise FFmpegError(f"Failed to parse ffprobe output: {e}")
        except subprocess.TimeoutExpired:
            raise FFmpegError("FFprobe timeout")
        except Exception as e:
            raise FFmpegError(f"Metadata extraction failed: {e}")

    def _extract_fps(self, video_stream: Dict[str, Any]) -> float:
        """Extract FPS from video stream info"""
        # Try different FPS fields
        fps_fields = ["r_frame_rate", "avg_frame_rate"]

        for field in fps_fields:
            fps_str = video_stream.get(field)
            if fps_str and fps_str != "0/0":
                try:
                    # Handle fraction format (e.g., "30000/1001")
                    if "/" in fps_str:
                        num, den = fps_str.split("/")
                        return float(num) / float(den)
                    else:
                        return float(fps_str)
                except (ValueError, ZeroDivisionError):
                    continue

        return 25.0  # Default fallback FPS

    def extract_frames(
        self,
        video_path: str,
        output_dir: str,
        frame_rate: Optional[float] = None,
        start_time: Optional[float] = None,
        duration: Optional[float] = None,
        quality: int = 2,
    ) -> List[str]:
        """
        Extract frames from video using FFmpeg

        Args:
            video_path: Path to input video
            output_dir: Directory to save frames
            frame_rate: Extract frames at this rate (fps). If None, extract all frames
            start_time: Start extraction at this time (seconds)
            duration: Extract for this duration (seconds)
            quality: JPEG quality (1-31, lower = better quality)

        Returns:
            List of extracted frame file paths

        Raises:
            FFmpegError: If frame extraction fails
        """
        video_path = Path(video_path)
        output_dir = Path(output_dir)

        if not video_path.exists():
            raise VideoFileNotFoundError(f"Video file not found: {video_path}")

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build output pattern
        output_pattern = output_dir / f"{video_path.stem}_frame_%06d.jpg"

        logger.info(f"🎬 Extracting frames from: {video_path.name}")
        logger.info(f"📁 Output directory: {output_dir}")

        try:
            # Build FFmpeg command with -nostdin to prevent background process freezing
            cmd = [self.ffmpeg_path, "-nostdin", "-i", str(video_path)]

            # Add time range if specified
            if start_time is not None:
                cmd.extend(["-ss", str(start_time)])
            if duration is not None:
                cmd.extend(["-t", str(duration)])

            # Add frame rate if specified
            if frame_rate is not None:
                cmd.extend(["-vf", f"fps={frame_rate}"])

            # Output settings
            cmd.extend(
                [
                    "-q:v",
                    str(quality),  # JPEG quality
                    "-y",  # Overwrite output files
                    str(output_pattern),
                ]
            )

            logger.debug(f"FFmpeg command: {' '.join(cmd)}")

            # Execute FFmpeg
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                raise FFmpegError(f"Frame extraction failed: {result.stderr}")

            # Find extracted frames
            frame_files = sorted(output_dir.glob(f"{video_path.stem}_frame_*.jpg"))
            frame_paths = [str(f) for f in frame_files]

            logger.info(f"✅ Extracted {len(frame_paths)} frames")
            return frame_paths

        except subprocess.TimeoutExpired:
            raise FFmpegError("Frame extraction timeout")
        except Exception as e:
            raise FFmpegError(f"Frame extraction failed: {e}")

    def extract_audio(
        self, video_path: str, output_path: str, format: str = "wav"
    ) -> str:
        """
        Extract audio track from video

        Args:
            video_path: Path to input video
            output_path: Path to output audio file
            format: Audio format (wav, mp3, aac)

        Returns:
            Path to extracted audio file

        Raises:
            FFmpegError: If audio extraction fails
        """
        video_path = Path(video_path)
        output_path = Path(output_path)

        if not video_path.exists():
            raise VideoFileNotFoundError(f"Video file not found: {video_path}")

        # Create output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"🎵 Extracting audio from: {video_path.name}")

        try:
            cmd = [
                self.ffmpeg_path,
                "-nostdin",
                "-i",
                str(video_path),
                "-vn",  # No video
                "-acodec",
                "pcm_s16le" if format == "wav" else "copy",
                "-y",  # Overwrite
                str(output_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                raise FFmpegError(f"Audio extraction failed: {result.stderr}")

            logger.info(f"✅ Audio extracted to: {output_path}")
            return str(output_path)

        except subprocess.TimeoutExpired:
            raise FFmpegError("Audio extraction timeout")
        except Exception as e:
            raise FFmpegError(f"Audio extraction failed: {e}")

    def get_frame_count(self, video_path: str) -> int:
        """
        Get total frame count of video

        Args:
            video_path: Path to video file

        Returns:
            Total number of frames
        """
        try:
            cmd = [
                self.ffprobe_path,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-count_packets",
                "-show_entries",
                "stream=nb_read_packets",
                "-csv=p=0",
                str(video_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                # Fallback method
                metadata = self.get_video_metadata(video_path)
                return int(metadata.duration * metadata.fps)

            return int(result.stdout.strip())

        except Exception as e:
            logger.warning(
                f"Frame count extraction failed: {e}, using metadata fallback"
            )
            metadata = self.get_video_metadata(video_path)
            return int(metadata.duration * metadata.fps)
