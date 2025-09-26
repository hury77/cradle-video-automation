"""
New Video Compare - SSIM Algorithm
Structural Similarity Index for video frame comparison
"""

import cv2
import numpy as np
import logging
from typing import Tuple, Dict, Any
from dataclasses import dataclass
from skimage.metrics import structural_similarity as compare_ssim

logger = logging.getLogger(__name__)


@dataclass
class SSIMResult:
    """SSIM comparison result"""

    ssim_score: float  # Overall SSIM score (0-1)
    ssim_luminance: float  # Luminance component
    ssim_contrast: float  # Contrast component
    ssim_structure: float  # Structure component
    difference_image: np.ndarray  # Visual difference map
    processing_time: float  # Time taken for comparison


class SSIMAlgorithm:
    """
    Structural Similarity Index algorithm for frame comparison

    SSIM measures perceptual similarity between images by comparing:
    - Luminance: brightness similarity
    - Contrast: contrast similarity
    - Structure: structural similarity
    """

    def __init__(
        self,
        window_size: int = 11,
        k1: float = 0.01,
        k2: float = 0.03,
        multichannel: bool = True,
    ):
        """
        Initialize SSIM algorithm

        Args:
            window_size: Size of sliding window (must be odd)
            k1, k2: Algorithm parameters (stability constants)
            multichannel: Whether to process color channels separately
        """
        self.window_size = window_size
        self.k1 = k1
        self.k2 = k2
        self.multichannel = multichannel

        logger.info(f"🔍 SSIM initialized: window={window_size}, k1={k1}, k2={k2}")

    def compare_frames(self, frame1: np.ndarray, frame2: np.ndarray) -> SSIMResult:
        """
        Compare two frames using SSIM algorithm

        Args:
            frame1: First frame (reference/acceptance)
            frame2: Second frame (comparison/emission)

        Returns:
            SSIMResult with detailed comparison metrics
        """
        import time

        start_time = time.time()

        logger.debug("🔍 Starting SSIM comparison...")

        # Ensure frames have same dimensions
        frame1, frame2 = self._normalize_frames(frame1, frame2)

        # Convert to appropriate format for SSIM
        if self.multichannel and len(frame1.shape) == 3:
            # Color image comparison
            ssim_score, difference_image = self._compare_color_frames(frame1, frame2)

            # Calculate component scores for color images
            gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
            luminance, contrast, structure = self._calculate_components(gray1, gray2)

        else:
            # Grayscale comparison
            if len(frame1.shape) == 3:
                frame1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
                frame2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)

            ssim_score, difference_image = self._compare_grayscale_frames(
                frame1, frame2
            )
            luminance, contrast, structure = self._calculate_components(frame1, frame2)

        processing_time = time.time() - start_time

        result = SSIMResult(
            ssim_score=float(ssim_score),
            ssim_luminance=float(luminance),
            ssim_contrast=float(contrast),
            ssim_structure=float(structure),
            difference_image=difference_image,
            processing_time=processing_time,
        )

        logger.debug(
            f"✅ SSIM complete: score={ssim_score:.4f}, time={processing_time:.3f}s"
        )

        return result

    def _normalize_frames(
        self, frame1: np.ndarray, frame2: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Ensure frames have the same dimensions"""
        if frame1.shape != frame2.shape:
            # Resize to minimum common dimensions
            min_height = min(frame1.shape[0], frame2.shape[0])
            min_width = min(frame1.shape[1], frame2.shape[1])

            frame1 = cv2.resize(
                frame1, (min_width, min_height), interpolation=cv2.INTER_AREA
            )
            frame2 = cv2.resize(
                frame2, (min_width, min_height), interpolation=cv2.INTER_AREA
            )

            logger.debug(f"Frames resized to {min_width}x{min_height}")

        return frame1, frame2

    def _compare_color_frames(
        self, frame1: np.ndarray, frame2: np.ndarray
    ) -> Tuple[float, np.ndarray]:
        """Compare color frames using SSIM"""
        try:
            # Use scikit-image SSIM for multichannel comparison
            ssim_score, difference_image = compare_ssim(
                frame1,
                frame2,
                win_size=self.window_size,
                K1=self.k1,
                K2=self.k2,
                multichannel=True,
                full=True,
                data_range=255,
            )

            # Convert difference image to 8-bit for visualization
            diff_image_8bit = ((1 - difference_image) * 255).astype(np.uint8)

            return ssim_score, diff_image_8bit

        except Exception as e:
            logger.error(f"Color SSIM comparison failed: {e}")
            # Fallback to grayscale
            gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
            return self._compare_grayscale_frames(gray1, gray2)

    def _compare_grayscale_frames(
        self, frame1: np.ndarray, frame2: np.ndarray
    ) -> Tuple[float, np.ndarray]:
        """Compare grayscale frames using SSIM"""
        try:
            ssim_score, difference_image = compare_ssim(
                frame1,
                frame2,
                win_size=self.window_size,
                K1=self.k1,
                K2=self.k2,
                full=True,
                data_range=255,
            )

            # Convert difference image to 8-bit
            diff_image_8bit = ((1 - difference_image) * 255).astype(np.uint8)

            return ssim_score, diff_image_8bit

        except Exception as e:
            logger.error(f"Grayscale SSIM comparison failed: {e}")
            # Return zero similarity and empty difference image
            return 0.0, np.zeros_like(frame1, dtype=np.uint8)

    def _calculate_components(
        self, frame1: np.ndarray, frame2: np.ndarray
    ) -> Tuple[float, float, float]:
        """Calculate individual SSIM components (luminance, contrast, structure)"""
        try:
            # Convert to float
            img1 = frame1.astype(np.float64)
            img2 = frame2.astype(np.float64)

            # Calculate means
            mu1 = np.mean(img1)
            mu2 = np.mean(img2)

            # Calculate variances and covariance
            sigma1_sq = np.var(img1)
            sigma2_sq = np.var(img2)
            sigma12 = np.mean((img1 - mu1) * (img2 - mu2))

            # SSIM constants
            c1 = (self.k1 * 255) ** 2
            c2 = (self.k2 * 255) ** 2
            c3 = c2 / 2

            # Calculate components
            luminance = (2 * mu1 * mu2 + c1) / (mu1**2 + mu2**2 + c1)
            contrast = (2 * np.sqrt(sigma1_sq) * np.sqrt(sigma2_sq) + c2) / (
                sigma1_sq + sigma2_sq + c2
            )
            structure = (sigma12 + c3) / (np.sqrt(sigma1_sq) * np.sqrt(sigma2_sq) + c3)

            return luminance, contrast, structure

        except Exception as e:
            logger.error(f"SSIM component calculation failed: {e}")
            return 0.0, 0.0, 0.0

    def compare_batch(self, frames1: list, frames2: list) -> list:
        """
        Compare multiple frame pairs using SSIM

        Args:
            frames1: List of reference frames
            frames2: List of comparison frames

        Returns:
            List of SSIMResult objects
        """
        if len(frames1) != len(frames2):
            raise ValueError("Frame lists must have the same length")

        results = []

        logger.info(f"�� Starting batch SSIM comparison: {len(frames1)} frame pairs")

        for i, (frame1, frame2) in enumerate(zip(frames1, frames2)):
            try:
                result = self.compare_frames(frame1, frame2)
                results.append(result)

                if (i + 1) % 50 == 0:
                    avg_ssim = np.mean([r.ssim_score for r in results[-50:]])
                    logger.info(
                        f"Progress: {i + 1}/{len(frames1)}, avg SSIM: {avg_ssim:.4f}"
                    )

            except Exception as e:
                logger.error(f"Frame pair {i} comparison failed: {e}")
                # Add zero result for failed comparison
                results.append(
                    SSIMResult(
                        ssim_score=0.0,
                        ssim_luminance=0.0,
                        ssim_contrast=0.0,
                        ssim_structure=0.0,
                        difference_image=np.zeros((100, 100), dtype=np.uint8),
                        processing_time=0.0,
                    )
                )

        avg_ssim = np.mean([r.ssim_score for r in results])
        logger.info(f"✅ Batch SSIM complete: avg score={avg_ssim:.4f}")

        return results

    def get_algorithm_info(self) -> Dict[str, Any]:
        """Get algorithm configuration info"""
        return {
            "name": "SSIM",
            "full_name": "Structural Similarity Index",
            "version": "1.0",
            "parameters": {
                "window_size": self.window_size,
                "k1": self.k1,
                "k2": self.k2,
                "multichannel": self.multichannel,
            },
            "description": "Measures perceptual similarity by comparing luminance, contrast, and structure",
            "score_range": "0.0 (completely different) to 1.0 (identical)",
            "optimal_threshold": 0.95,
        }
