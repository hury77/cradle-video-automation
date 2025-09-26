"""
Edge Detection Algorithm for Video Comparison
Detects and compares edges/contours in video frames
"""

import cv2
import numpy as np
from typing import Tuple, List, Dict, Optional
import logging
from ..utils.exceptions import VideoProcessingError

logger = logging.getLogger(__name__)


class EdgeDetectionComparator:
    """
    Edge-based frame comparison using various edge detection methods
    """

    def __init__(
        self,
        edge_method: str = "canny",
        canny_low: int = 50,
        canny_high: int = 150,
        sobel_ksize: int = 3,
        blur_kernel: int = 5,
    ):
        """
        Initialize edge detection comparator

        Args:
            edge_method: Edge detection method ('canny', 'sobel', 'laplacian')
            canny_low: Lower threshold for Canny edge detection
            canny_high: Upper threshold for Canny edge detection
            sobel_ksize: Kernel size for Sobel operator
            blur_kernel: Gaussian blur kernel size for noise reduction
        """
        self.edge_method = edge_method
        self.canny_low = canny_low
        self.canny_high = canny_high
        self.sobel_ksize = sobel_ksize
        self.blur_kernel = blur_kernel

        # Validate parameters
        if edge_method not in ["canny", "sobel", "laplacian"]:
            raise ValueError("edge_method must be 'canny', 'sobel', or 'laplacian'")

    def preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Preprocess frame for edge detection

        Args:
            frame: Input frame

        Returns:
            Preprocessed grayscale frame
        """
        try:
            # Convert to grayscale if needed
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame

            # Apply Gaussian blur to reduce noise
            if self.blur_kernel > 1:
                blurred = cv2.GaussianBlur(
                    gray, (self.blur_kernel, self.blur_kernel), 0
                )
            else:
                blurred = gray

            return blurred

        except Exception as e:
            raise VideoProcessingError(f"Frame preprocessing failed: {str(e)}")

    def detect_edges_canny(self, frame: np.ndarray) -> np.ndarray:
        """
        Detect edges using Canny edge detector

        Args:
            frame: Preprocessed grayscale frame

        Returns:
            Binary edge image
        """
        try:
            edges = cv2.Canny(frame, self.canny_low, self.canny_high)
            return edges

        except Exception as e:
            raise VideoProcessingError(f"Canny edge detection failed: {str(e)}")

    def detect_edges_sobel(self, frame: np.ndarray) -> np.ndarray:
        """
        Detect edges using Sobel operator

        Args:
            frame: Preprocessed grayscale frame

        Returns:
            Edge magnitude image
        """
        try:
            # Calculate gradients in X and Y directions
            grad_x = cv2.Sobel(frame, cv2.CV_64F, 1, 0, ksize=self.sobel_ksize)
            grad_y = cv2.Sobel(frame, cv2.CV_64F, 0, 1, ksize=self.sobel_ksize)

            # Calculate gradient magnitude
            magnitude = np.sqrt(grad_x**2 + grad_y**2)

            # Normalize to 0-255 range
            magnitude = np.uint8(255 * magnitude / np.max(magnitude))

            return magnitude

        except Exception as e:
            raise VideoProcessingError(f"Sobel edge detection failed: {str(e)}")

    def detect_edges_laplacian(self, frame: np.ndarray) -> np.ndarray:
        """
        Detect edges using Laplacian operator

        Args:
            frame: Preprocessed grayscale frame

        Returns:
            Edge image
        """
        try:
            # Apply Laplacian operator
            laplacian = cv2.Laplacian(frame, cv2.CV_64F)

            # Convert to absolute values and normalize
            laplacian = np.absolute(laplacian)
            laplacian = np.uint8(255 * laplacian / np.max(laplacian))

            return laplacian

        except Exception as e:
            raise VideoProcessingError(f"Laplacian edge detection failed: {str(e)}")

    def detect_edges(self, frame: np.ndarray) -> np.ndarray:
        """
        Detect edges using specified method

        Args:
            frame: Input frame

        Returns:
            Edge image
        """
        try:
            # Preprocess frame
            preprocessed = self.preprocess_frame(frame)

            # Apply edge detection
            if self.edge_method == "canny":
                edges = self.detect_edges_canny(preprocessed)
            elif self.edge_method == "sobel":
                edges = self.detect_edges_sobel(preprocessed)
            elif self.edge_method == "laplacian":
                edges = self.detect_edges_laplacian(preprocessed)
            else:
                raise ValueError(f"Unknown edge method: {self.edge_method}")

            return edges

        except Exception as e:
            raise VideoProcessingError(f"Edge detection failed: {str(e)}")

    def calculate_edge_statistics(self, edges: np.ndarray) -> Dict[str, float]:
        """
        Calculate statistical measures of edge image

        Args:
            edges: Binary/grayscale edge image

        Returns:
            Dictionary with edge statistics
        """
        try:
            # Basic statistics
            total_pixels = edges.shape[0] * edges.shape[1]
            edge_pixels = np.count_nonzero(edges)
            edge_density = edge_pixels / total_pixels

            # Edge strength measures
            mean_intensity = np.mean(edges)
            std_intensity = np.std(edges)
            max_intensity = np.max(edges)

            # Edge distribution
            hist, _ = np.histogram(edges.flatten(), bins=32, range=(0, 256))
            hist_normalized = hist / np.sum(hist)
            entropy = -np.sum(hist_normalized * np.log2(hist_normalized + 1e-7))

            return {
                "edge_density": edge_density,
                "edge_pixels": edge_pixels,
                "mean_intensity": mean_intensity,
                "std_intensity": std_intensity,
                "max_intensity": max_intensity,
                "entropy": entropy,
            }

        except Exception as e:
            raise VideoProcessingError(f"Edge statistics calculation failed: {str(e)}")

    def compare_edge_images(
        self, edges1: np.ndarray, edges2: np.ndarray
    ) -> Tuple[float, Dict]:
        """
        Compare two edge images

        Args:
            edges1: First edge image
            edges2: Second edge image

        Returns:
            Tuple of (similarity_score, comparison_metadata)
        """
        try:
            # Ensure same dimensions
            if edges1.shape != edges2.shape:
                # Resize to match smaller dimension
                h = min(edges1.shape[0], edges2.shape[0])
                w = min(edges1.shape[1], edges2.shape[1])
                edges1 = cv2.resize(edges1, (w, h))
                edges2 = cv2.resize(edges2, (w, h))

            # Calculate statistics for both images
            stats1 = self.calculate_edge_statistics(edges1)
            stats2 = self.calculate_edge_statistics(edges2)

            # Structural similarity using normalized cross-correlation
            # Normalize images
            norm1 = edges1.astype(np.float64) / 255.0
            norm2 = edges2.astype(np.float64) / 255.0

            # Calculate cross-correlation
            correlation = np.corrcoef(norm1.flatten(), norm2.flatten())[0, 1]
            if np.isnan(correlation):
                correlation = 0.0

            # Pixel-wise comparison (Intersection over Union for binary edges)
            if self.edge_method == "canny":
                intersection = np.logical_and(edges1, edges2)
                union = np.logical_or(edges1, edges2)
                iou = np.sum(intersection) / (np.sum(union) + 1e-7)
            else:
                # For grayscale edges, use normalized difference
                diff = np.abs(norm1 - norm2)
                iou = 1.0 - np.mean(diff)

            # Statistical similarity
            density_diff = abs(stats1["edge_density"] - stats2["edge_density"])
            entropy_diff = abs(stats1["entropy"] - stats2["entropy"])

            # Combined similarity score
            structural_weight = 0.4
            pixel_weight = 0.4
            statistical_weight = 0.2

            structural_sim = max(0.0, correlation)
            pixel_sim = max(0.0, iou)
            statistical_sim = max(0.0, 1.0 - (density_diff + entropy_diff / 10.0))

            combined_similarity = (
                structural_weight * structural_sim
                + pixel_weight * pixel_sim
                + statistical_weight * statistical_sim
            )

            metadata = {
                "structural_similarity": structural_sim,
                "pixel_similarity": pixel_sim,
                "statistical_similarity": statistical_sim,
                "correlation": correlation,
                "iou": iou,
                "stats1": stats1,
                "stats2": stats2,
                "density_difference": density_diff,
                "entropy_difference": entropy_diff,
                "algorithm": f"edge_detection_{self.edge_method}",
            }

            return combined_similarity, metadata

        except Exception as e:
            raise VideoProcessingError(f"Edge image comparison failed: {str(e)}")

    def compare_frames(
        self, frame1: np.ndarray, frame2: np.ndarray
    ) -> Tuple[float, Dict]:
        """
        Compare two frames using edge detection

        Args:
            frame1: First frame
            frame2: Second frame

        Returns:
            Tuple of (similarity_score, metadata)
        """
        try:
            # Detect edges in both frames
            edges1 = self.detect_edges(frame1)
            edges2 = self.detect_edges(frame2)

            # Compare edge images
            similarity, metadata = self.compare_edge_images(edges1, edges2)

            # Add method information
            metadata.update(
                {
                    "edge_method": self.edge_method,
                    "parameters": {
                        "canny_low": self.canny_low,
                        "canny_high": self.canny_high,
                        "sobel_ksize": self.sobel_ksize,
                        "blur_kernel": self.blur_kernel,
                    },
                }
            )

            return similarity, metadata

        except Exception as e:
            raise VideoProcessingError(f"Frame comparison failed: {str(e)}")

    def batch_compare(
        self, frames1: List[np.ndarray], frames2: List[np.ndarray]
    ) -> List[Tuple[float, Dict]]:
        """
        Compare multiple frame pairs using edge detection

        Args:
            frames1: List of first frames
            frames2: List of second frames

        Returns:
            List of (similarity, metadata) tuples
        """
        try:
            if len(frames1) != len(frames2):
                raise ValueError("Frame lists must have equal length")

            results = []

            for i, (f1, f2) in enumerate(zip(frames1, frames2)):
                try:
                    similarity, metadata = self.compare_frames(f1, f2)
                    metadata["frame_index"] = i
                    results.append((similarity, metadata))

                except Exception as e:
                    logger.warning(f"Failed to compare frame pair {i}: {str(e)}")
                    results.append(
                        (
                            0.0,
                            {
                                "frame_index": i,
                                "error": str(e),
                                "algorithm": f"edge_detection_{self.edge_method}",
                            },
                        )
                    )

            return results

        except Exception as e:
            raise VideoProcessingError(f"Batch comparison failed: {str(e)}")


class MultiEdgeComparator:
    """
    Advanced edge comparator using multiple edge detection methods
    """

    def __init__(self):
        """Initialize multiple edge detectors"""
        self.detectors = {
            "canny": EdgeDetectionComparator("canny", 50, 150),
            "sobel": EdgeDetectionComparator("sobel"),
            "laplacian": EdgeDetectionComparator("laplacian"),
        }

    def compare_frames_multi(
        self,
        frame1: np.ndarray,
        frame2: np.ndarray,
        weights: Optional[Dict[str, float]] = None,
    ) -> Tuple[float, Dict]:
        """
        Compare frames using multiple edge detection methods

        Args:
            frame1: First frame
            frame2: Second frame
            weights: Optional weights for each method

        Returns:
            Tuple of (weighted_similarity, combined_metadata)
        """
        if weights is None:
            weights = {"canny": 0.4, "sobel": 0.4, "laplacian": 0.2}

        results = {}
        total_similarity = 0.0
        total_weight = 0.0

        for method, detector in self.detectors.items():
            try:
                similarity, metadata = detector.compare_frames(frame1, frame2)
                results[method] = {"similarity": similarity, "metadata": metadata}

                weight = weights.get(method, 1.0)
                total_similarity += similarity * weight
                total_weight += weight

            except Exception as e:
                logger.warning(f"Edge method {method} failed: {str(e)}")
                results[method] = {"similarity": 0.0, "error": str(e)}

        combined_similarity = (
            total_similarity / total_weight if total_weight > 0 else 0.0
        )

        combined_metadata = {
            "combined_similarity": combined_similarity,
            "individual_results": results,
            "weights_used": weights,
            "algorithm": "multi_edge_detection",
        }

        return combined_similarity, combined_metadata
