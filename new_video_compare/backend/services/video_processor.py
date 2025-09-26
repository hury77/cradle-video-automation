"""
New Video Compare - Video Processor
Main video processing and comparison engine
"""

import os
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from .utils.ffmpeg_utils import FFmpegUtils, VideoMetadata
from .utils.video_utils import VideoUtils, VideoInfo
from .utils.frame_utils import FrameUtils
from .exceptions import (
    VideoProcessingError,
    VideoFileNotFoundError,
    VideoResolutionMismatchError,
    ProcessingTimeoutError,
    InsufficientVideoDataError,
)


logger = logging.getLogger(__name__)


@dataclass
class ProcessingJob:
    """Video processing job configuration"""

    job_id: int
    acceptance_file_path: str
    emission_file_path: str
    output_dir: str
    processing_config: Dict[str, Any]
    created_at: datetime


@dataclass
class ProcessingResult:
    """Video processing results"""

    job_id: int
    processing_time: float
    total_frames_analyzed: int
    frames_with_differences: int
    overall_similarity: float
    frame_analysis_complete: bool
    error_message: Optional[str] = None

    # Technical metrics
    acceptance_metadata: Optional[VideoMetadata] = None
    emission_metadata: Optional[VideoMetadata] = None

    # Analysis details
    frame_similarities: List[float] = None
    difference_timestamps: List[float] = None


class VideoProcessor:
    """
    Main video processing engine
    Handles video comparison workflow from start to finish
    """

    def __init__(
        self,
        temp_dir: Optional[str] = None,
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe",
    ):
        """
        Initialize Video Processor

        Args:
            temp_dir: Temporary directory for processing files
            ffmpeg_path: Path to ffmpeg executable
            ffprobe_path: Path to ffprobe executable
        """
        self.temp_dir = (
            Path(temp_dir)
            if temp_dir
            else Path(tempfile.gettempdir()) / "new_video_compare"
        )
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Initialize utilities
        self.ffmpeg = FFmpegUtils(ffmpeg_path, ffprobe_path)
        self.video_utils = VideoUtils(self.ffmpeg)
        self.frame_utils = FrameUtils()

        # Processing state
        self.current_job: Optional[ProcessingJob] = None
        self.is_processing = False

        logger.info(f"🎬 VideoProcessor initialized")
        logger.info(f"📁 Temp directory: {self.temp_dir}")

    def process_comparison(
        self,
        job_id: int,
        acceptance_file: str,
        emission_file: str,
        processing_config: Optional[Dict[str, Any]] = None,
    ) -> ProcessingResult:
        """
        Main video comparison processing method

        Args:
            job_id: Unique job identifier
            acceptance_file: Path to acceptance video file
            emission_file: Path to emission video file
            processing_config: Processing configuration options

        Returns:
            ProcessingResult with comparison results

        Raises:
            VideoProcessingError: If processing fails
        """
        start_time = datetime.now(timezone.utc)
        processing_start = start_time.timestamp()

        logger.info(f"🚀 Starting video comparison job {job_id}")
        logger.info(f"📄 Acceptance: {Path(acceptance_file).name}")
        logger.info(f"📄 Emission: {Path(emission_file).name}")

        # Set processing state
        self.is_processing = True
        self.current_job = ProcessingJob(
            job_id=job_id,
            acceptance_file_path=acceptance_file,
            emission_file_path=emission_file,
            output_dir=str(self.temp_dir / f"job_{job_id}"),
            processing_config=processing_config or {},
            created_at=start_time,
        )

        try:
            # Step 1: Validate input files
            logger.info("📋 Step 1: Validating input files...")
            acceptance_info, emission_info = self._validate_input_files(
                acceptance_file, emission_file
            )

            # Step 2: Check compatibility
            logger.info("🔄 Step 2: Checking video compatibility...")
            compatibility = self._check_compatibility(acceptance_info, emission_info)

            # Step 3: Prepare processing environment
            logger.info("🛠️ Step 3: Preparing processing environment...")
            job_temp_dir = self._prepare_processing_environment(job_id)

            # Step 4: Extract frames for analysis
            logger.info("🎬 Step 4: Extracting frames...")
            acceptance_frames, emission_frames = self._extract_frames_for_analysis(
                acceptance_file, emission_file, job_temp_dir, processing_config
            )

            # Step 5: Perform frame-by-frame comparison
            logger.info("🔍 Step 5: Performing frame comparison...")
            comparison_results = self._compare_frames(
                acceptance_frames, emission_frames
            )

            # Step 6: Generate final results
            logger.info("📊 Step 6: Generating results...")
            processing_time = datetime.now(timezone.utc).timestamp() - processing_start

            result = ProcessingResult(
                job_id=job_id,
                processing_time=processing_time,
                total_frames_analyzed=len(acceptance_frames),
                frames_with_differences=comparison_results["frames_with_differences"],
                overall_similarity=comparison_results["overall_similarity"],
                frame_analysis_complete=True,
                acceptance_metadata=acceptance_info.metadata,
                emission_metadata=emission_info.metadata,
                frame_similarities=comparison_results["frame_similarities"],
                difference_timestamps=comparison_results["difference_timestamps"],
            )

            logger.info(f"✅ Processing complete: {processing_time:.2f}s")
            logger.info(f"📊 Overall similarity: {result.overall_similarity:.3f}")
            logger.info(f"🔍 Frames analyzed: {result.total_frames_analyzed}")
            logger.info(f"⚠️ Differences found: {result.frames_with_differences}")

            return result

        except Exception as e:
            processing_time = datetime.now(timezone.utc).timestamp() - processing_start
            error_message = f"Processing failed: {str(e)}"

            logger.error(f"❌ {error_message}")

            # Return error result
            return ProcessingResult(
                job_id=job_id,
                processing_time=processing_time,
                total_frames_analyzed=0,
                frames_with_differences=0,
                overall_similarity=0.0,
                frame_analysis_complete=False,
                error_message=error_message,
            )

        finally:
            # Cleanup
            self.is_processing = False
            self.current_job = None
            self._cleanup_processing_files(job_id)

    def _validate_input_files(
        self, acceptance_file: str, emission_file: str
    ) -> Tuple[VideoInfo, VideoInfo]:
        """Validate both input video files"""
        logger.debug("Validating acceptance file...")
        acceptance_info = self.video_utils.validate_video_file(acceptance_file)

        if not acceptance_info.is_valid:
            raise VideoProcessingError(
                f"Acceptance file validation failed: {', '.join(acceptance_info.validation_errors)}"
            )

        logger.debug("Validating emission file...")
        emission_info = self.video_utils.validate_video_file(emission_file)

        if not emission_info.is_valid:
            raise VideoProcessingError(
                f"Emission file validation failed: {', '.join(emission_info.validation_errors)}"
            )

        return acceptance_info, emission_info

    def _check_compatibility(
        self, acceptance_info: VideoInfo, emission_info: VideoInfo
    ) -> Dict[str, Any]:
        """Check if videos are compatible for comparison"""
        compatibility = self.video_utils.compare_video_compatibility(
            acceptance_info.file_path, emission_info.file_path
        )

        if not compatibility["compatible"]:
            error_msgs = compatibility.get("errors", [])
            raise VideoResolutionMismatchError(
                f"Videos are not compatible for comparison: {', '.join(error_msgs)}"
            )

        # Log warnings
        warnings = compatibility.get("warnings", [])
        for warning in warnings:
            logger.warning(f"⚠️ Compatibility warning: {warning}")

        return compatibility

    def _prepare_processing_environment(self, job_id: int) -> Path:
        """Prepare temporary directory for processing"""
        job_temp_dir = self.temp_dir / f"job_{job_id}"

        # Clean up if exists
        if job_temp_dir.exists():
            shutil.rmtree(job_temp_dir)

        # Create fresh directories
        job_temp_dir.mkdir(parents=True)
        (job_temp_dir / "acceptance_frames").mkdir()
        (job_temp_dir / "emission_frames").mkdir()
        (job_temp_dir / "results").mkdir()

        logger.debug(f"Created processing environment: {job_temp_dir}")
        return job_temp_dir

    def _extract_frames_for_analysis(
        self,
        acceptance_file: str,
        emission_file: str,
        job_temp_dir: Path,
        processing_config: Dict[str, Any],
    ) -> Tuple[List[str], List[str]]:
        """Extract frames from both videos for analysis"""

        # Get processing configuration
        frame_rate = processing_config.get(
            "analysis_fps", 1.0
        )  # 1 frame per second default
        max_frames = processing_config.get("max_frames", 300)  # Max 5 minutes at 1fps
        start_time = processing_config.get("start_time", 0)  # Start from beginning

        logger.info(
            f"🎬 Extraction config: {frame_rate}fps, max {max_frames} frames, start at {start_time}s"
        )

        # Extract acceptance frames
        logger.debug("Extracting acceptance frames...")
        acceptance_frame_dir = job_temp_dir / "acceptance_frames"
        acceptance_frames = self.ffmpeg.extract_frames(
            video_path=acceptance_file,
            output_dir=str(acceptance_frame_dir),
            frame_rate=frame_rate,
            start_time=start_time if start_time > 0 else None,
        )

        # Limit frames if needed
        if len(acceptance_frames) > max_frames:
            acceptance_frames = acceptance_frames[:max_frames]
            logger.info(f"⚠️ Limited acceptance frames to {max_frames}")

        # Extract emission frames (same number as acceptance)
        logger.debug("Extracting emission frames...")
        emission_frame_dir = job_temp_dir / "emission_frames"
        emission_frames = self.ffmpeg.extract_frames(
            video_path=emission_file,
            output_dir=str(emission_frame_dir),
            frame_rate=frame_rate,
            start_time=start_time if start_time > 0 else None,
        )

        # Match frame count
        min_frames = min(len(acceptance_frames), len(emission_frames), max_frames)
        acceptance_frames = acceptance_frames[:min_frames]
        emission_frames = emission_frames[:min_frames]

        logger.info(f"✅ Extracted {len(acceptance_frames)} frame pairs for analysis")

        return acceptance_frames, emission_frames

    def _compare_frames(
        self, acceptance_frames: List[str], emission_frames: List[str]
    ) -> Dict[str, Any]:
        """
        Compare frames using basic MSE algorithm
        (This will be enhanced with advanced algorithms in later steps)
        """
        if len(acceptance_frames) != len(emission_frames):
            raise InsufficientVideoDataError("Frame count mismatch between videos")

        frame_similarities = []
        difference_timestamps = []
        frames_with_differences = 0

        similarity_threshold = 0.95  # 95% similarity threshold

        logger.info(f"🔍 Comparing {len(acceptance_frames)} frame pairs...")

        for i, (acc_frame_path, em_frame_path) in enumerate(
            zip(acceptance_frames, emission_frames)
        ):
            try:
                # Load frames
                acc_frame = self.frame_utils.load_frame(acc_frame_path)
                em_frame = self.frame_utils.load_frame(em_frame_path)

                # Calculate frame difference (MSE)
                mse = self.frame_utils.calculate_frame_difference(acc_frame, em_frame)

                # Convert MSE to similarity score (0-1)
                # This is a simple conversion - will be improved with advanced algorithms
                max_possible_mse = 255.0**2 * 3  # Max MSE for RGB
                similarity = 1.0 - min(mse / max_possible_mse, 1.0)

                frame_similarities.append(similarity)

                # Check if frame has significant difference
                if similarity < similarity_threshold:
                    frames_with_differences += 1
                    # Calculate timestamp (assuming 1fps extraction)
                    timestamp = float(i)
                    difference_timestamps.append(timestamp)

                    logger.debug(
                        f"Frame {i}: similarity={similarity:.3f}, diff at {timestamp}s"
                    )

                # Progress logging
                if (i + 1) % 50 == 0:
                    logger.info(f"Progress: {i + 1}/{len(acceptance_frames)} frames")

            except Exception as e:
                logger.warning(f"Frame comparison failed for frame {i}: {e}")
                frame_similarities.append(0.0)  # Assume different if comparison fails
                frames_with_differences += 1

        # Calculate overall similarity
        overall_similarity = (
            sum(frame_similarities) / len(frame_similarities)
            if frame_similarities
            else 0.0
        )

        return {
            "overall_similarity": overall_similarity,
            "frame_similarities": frame_similarities,
            "frames_with_differences": frames_with_differences,
            "difference_timestamps": difference_timestamps,
            "total_frames": len(acceptance_frames),
        }

    def _cleanup_processing_files(self, job_id: int) -> None:
        """Clean up temporary processing files"""
        job_temp_dir = self.temp_dir / f"job_{job_id}"

        if job_temp_dir.exists():
            try:
                shutil.rmtree(job_temp_dir)
                logger.debug(f"🧹 Cleaned up processing files for job {job_id}")
            except Exception as e:
                logger.warning(f"Cleanup failed for job {job_id}: {e}")

    def get_processing_status(self) -> Dict[str, Any]:
        """Get current processing status"""
        return {
            "is_processing": self.is_processing,
            "current_job_id": self.current_job.job_id if self.current_job else None,
            "temp_dir": str(self.temp_dir),
            "temp_dir_size_mb": self._get_directory_size(self.temp_dir),
        }

    def _get_directory_size(self, directory: Path) -> float:
        """Get directory size in MB"""
        try:
            total_size = sum(
                f.stat().st_size for f in directory.rglob("*") if f.is_file()
            )
            return round(total_size / 1024 / 1024, 2)
        except Exception:
            return 0.0

    def cleanup_all_temp_files(self) -> int:
        """Clean up all temporary files"""
        deleted_count = 0

        if self.temp_dir.exists():
            try:
                for item in self.temp_dir.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item)
                        deleted_count += 1
                    elif item.is_file():
                        item.unlink()
                        deleted_count += 1

                logger.info(f"🧹 Cleaned up {deleted_count} temporary items")

            except Exception as e:
                logger.error(f"Cleanup failed: {e}")

        return deleted_count
