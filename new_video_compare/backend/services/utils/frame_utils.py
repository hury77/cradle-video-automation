"""
New Video Compare - Frame Processing Utilities
Frame extraction, loading, and basic operations
"""

import cv2
import numpy as np
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Iterator
from dataclasses import dataclass

from ..exceptions import FrameExtractionError, VideoFileNotFoundError


logger = logging.getLogger(__name__)


@dataclass
class FrameInfo:
    """Information about a video frame"""

    frame_number: int
    timestamp: float
    width: int
    height: int
    channels: int
    data_type: str


class FrameUtils:
    """Frame processing utilities"""

    def __init__(self):
        """Initialize FrameUtils"""
        # Verify OpenCV installation
        logger.info(f"📷 OpenCV version: {cv2.__version__}")

    def load_frame(self, frame_path: str) -> np.ndarray:
        """
        Load a single frame from file

        Args:
            frame_path: Path to frame image file

        Returns:
            Frame as numpy array (BGR format)

        Raises:
            FrameExtractionError: If frame loading fails
        """
        frame_path = Path(frame_path)

        if not frame_path.exists():
            raise FrameExtractionError(f"Frame file not found: {frame_path}")

        try:
            frame = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)

            if frame is None:
                raise FrameExtractionError(f"Could not load frame: {frame_path}")

            return frame

        except Exception as e:
            raise FrameExtractionError(f"Frame loading error: {e}")

    def load_frames_batch(self, frame_paths: List[str]) -> List[np.ndarray]:
        """
        Load multiple frames efficiently

        Args:
            frame_paths: List of frame file paths

        Returns:
            List of frame arrays
        """
        frames = []

        logger.info(f"📷 Loading {len(frame_paths)} frames")

        for i, frame_path in enumerate(frame_paths):
            try:
                frame = self.load_frame(frame_path)
                frames.append(frame)

                if (i + 1) % 100 == 0:
                    logger.debug(f"Loaded {i + 1}/{len(frame_paths)} frames")

            except FrameExtractionError as e:
                logger.warning(f"Skipping frame {frame_path}: {e}")
                continue

        logger.info(f"✅ Loaded {len(frames)} frames successfully")
        return frames

    def get_frame_info(self, frame: np.ndarray) -> FrameInfo:
        """
        Get information about a frame

        Args:
            frame: Frame as numpy array

        Returns:
            FrameInfo object
        """
        height, width = frame.shape[:2]
        channels = frame.shape[2] if len(frame.shape) == 3 else 1

        return FrameInfo(
            frame_number=-1,  # Will be set by caller if needed
            timestamp=-1.0,  # Will be set by caller if needed
            width=width,
            height=height,
            channels=channels,
            data_type=str(frame.dtype),
        )

    def resize_frame(
        self, frame: np.ndarray, target_size: Tuple[int, int]
    ) -> np.ndarray:
        """
        Resize frame to target size

        Args:
            frame: Input frame
            target_size: (width, height) tuple

        Returns:
            Resized frame
        """
        return cv2.resize(frame, target_size, interpolation=cv2.INTER_AREA)

    def convert_color_space(
        self, frame: np.ndarray, conversion: str = "BGR2RGB"
    ) -> np.ndarray:
        """
        Convert frame color space

        Args:
            frame: Input frame
            conversion: OpenCV color conversion code (e.g., "BGR2RGB", "BGR2GRAY")

        Returns:
            Converted frame
        """
        conversion_code = getattr(cv2, f"COLOR_{conversion}", None)

        if conversion_code is None:
            raise FrameExtractionError(f"Unknown color conversion: {conversion}")

        return cv2.cvtColor(frame, conversion_code)

    def extract_frame_at_timestamp(
        self, video_path: str, timestamp: float
    ) -> np.ndarray:
        """
        Extract a single frame at specific timestamp

        Args:
            video_path: Path to video file
            timestamp: Timestamp in seconds

        Returns:
            Frame at the specified timestamp

        Raises:
            FrameExtractionError: If extraction fails
        """
        video_path = Path(video_path)

        if not video_path.exists():
            raise VideoFileNotFoundError(f"Video file not found: {video_path}")

        try:
            cap = cv2.VideoCapture(str(video_path))

            if not cap.isOpened():
                raise FrameExtractionError(f"Could not open video: {video_path}")

            # Set position to timestamp
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_number = int(timestamp * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

            ret, frame = cap.read()
            cap.release()

            if not ret:
                raise FrameExtractionError(f"Could not extract frame at {timestamp}s")

            return frame

        except Exception as e:
            raise FrameExtractionError(f"Frame extraction failed: {e}")

    def video_frame_iterator(
        self, video_path: str, start_frame: int = 0, max_frames: Optional[int] = None
    ) -> Iterator[Tuple[int, np.ndarray]]:
        """
        Iterator for video frames

        Args:
            video_path: Path to video file
            start_frame: Starting frame number
            max_frames: Maximum number of frames to yield

        Yields:
            Tuple of (frame_number, frame_array)
        """
        video_path = Path(video_path)

        if not video_path.exists():
            raise VideoFileNotFoundError(f"Video file not found: {video_path}")

        cap = None
        try:
            cap = cv2.VideoCapture(str(video_path))

            if not cap.isOpened():
                raise FrameExtractionError(f"Could not open video: {video_path}")

            # Set starting position
            if start_frame > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

            frame_count = 0
            current_frame = start_frame

            while True:
                ret, frame = cap.read()

                if not ret:
                    break

                yield current_frame, frame

                current_frame += 1
                frame_count += 1

                if max_frames and frame_count >= max_frames:
                    break

        except Exception as e:
            raise FrameExtractionError(f"Frame iteration failed: {e}")
        finally:
            if cap is not None:
                cap.release()

    def calculate_frame_difference(
        self, frame1: np.ndarray, frame2: np.ndarray
    ) -> float:
        """
        Calculate simple frame difference (MSE)

        Args:
            frame1: First frame
            frame2: Second frame

        Returns:
            Mean squared error between frames
        """
        if frame1.shape != frame2.shape:
            # Resize to match
            min_height = min(frame1.shape[0], frame2.shape[0])
            min_width = min(frame1.shape[1], frame2.shape[1])
            frame1 = self.resize_frame(frame1, (min_width, min_height))
            frame2 = self.resize_frame(frame2, (min_width, min_height))

        # Convert to float for calculation
        diff = frame1.astype(np.float64) - frame2.astype(np.float64)
        mse = np.mean(diff**2)

        return float(mse)

    def extract_dominant_colors(
        self, frame: np.ndarray, num_colors: int = 5
    ) -> List[Tuple[int, int, int]]:
        """
        Extract dominant colors from frame using K-means clustering

        Args:
            frame: Input frame
            num_colors: Number of dominant colors to extract

        Returns:
            List of RGB color tuples
        """
        try:
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Reshape frame to be a list of pixels
            pixels = frame_rgb.reshape((-1, 3))
            pixels = np.float32(pixels)

            # K-means clustering
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
            _, labels, centers = cv2.kmeans(
                pixels, num_colors, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS
            )

            # Convert centers to integers
            dominant_colors = [tuple(map(int, color)) for color in centers]

            return dominant_colors

        except Exception as e:
            logger.warning(f"Dominant color extraction failed: {e}")
            return [(128, 128, 128)] * num_colors  # Fallback to gray

    def save_frame(
        self, frame: np.ndarray, output_path: str, quality: int = 95
    ) -> bool:
        """
        Save frame to file

        Args:
            frame: Frame to save
            output_path: Output file path
            quality: JPEG quality (0-100)

        Returns:
            True if successful, False otherwise
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Set JPEG quality
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]

            success = cv2.imwrite(str(output_path), frame, encode_params)

            if success:
                logger.debug(f"Frame saved: {output_path}")
            else:
                logger.error(f"Failed to save frame: {output_path}")

            return success

        except Exception as e:
            logger.error(f"Frame save error: {e}")
            return False
