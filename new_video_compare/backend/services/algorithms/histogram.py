"""
New Video Compare - Histogram Algorithm
Color histogram comparison for video frame analysis
"""

import cv2
import numpy as np
import logging
from typing import Tuple, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HistogramResult:
    """Histogram comparison result"""
    correlation_score: float      # Correlation coefficient (0-1)
    chi_squared_score: float      # Chi-squared distance (lower = more similar)
    intersection_score: float     # Histogram intersection (0-1)
    bhattacharyya_score: float    # Bhattacharyya distance (0-1)
    combined_score: float         # Weighted combination of all metrics
    color_channel_scores: Dict[str, float]  # Per-channel scores
    processing_time: float        # Processing time


class HistogramAlgorithm:
    """
    Color histogram comparison algorithm
    
    Analyzes color distribution differences between frames using multiple metrics:
    - Correlation: Linear relationship between histograms
    - Chi-squared: Statistical difference measure  
    - Intersection: Overlap between histograms
    - Bhattacharyya: Probabilistic distance measure
    """
    
    def __init__(self,
                 bins: int = 256,
                 color_space: str = "BGR",
                 normalize: bool = True,
                 weights: Dict[str, float] = None):
        """
        Initialize Histogram algorithm
        
        Args:
            bins: Number of histogram bins per channel
            color_space: Color space for analysis (BGR, HSV, LAB)
            normalize: Whether to normalize histograms
            weights: Weights for combining different metrics
        """
        self.bins = bins
        self.color_space = color_space.upper()
        self.normalize = normalize
        
        # Default weights for combining metrics
        self.weights = weights or {
            "correlation": 0.3,
            "chi_squared": 0.2,
            "intersection": 0.3,
            "bhattacharyya": 0.2
        }
        
        # Histogram ranges for different color spaces
        self.ranges = {
            "BGR": [0, 256, 0, 256, 0, 256],
            "HSV": [0, 180, 0, 256, 0, 256],  # H: 0-179, S,V: 0-255
            "LAB": [0, 256, 0, 256, 0, 256]
        }
        
        logger.info(f"📊 Histogram initialized: {bins} bins, {color_space} color space")
    
    def compare_frames(self, frame1: np.ndarray, frame2: np.ndarray) -> HistogramResult:
        """
        Compare two frames using histogram analysis
        
        Args:
            frame1: First frame (reference/acceptance)
            frame2: Second frame (comparison/emission)
            
        Returns:
            HistogramResult with detailed metrics
        """
        import time
        start_time = time.time()
        
        logger.debug("📊 Starting histogram comparison...")
        
        # Ensure frames have same dimensions
        frame1, frame2 = self._normalize_frames(frame1, frame2)
        
        # Convert to target color space
        frame1_converted = self._convert_color_space(frame1)
        frame2_converted = self._convert_color_space(frame2)
        
        # Calculate histograms
        hist1 = self._calculate_histogram(frame1_converted)
        hist2 = self._calculate_histogram(frame2_converted) 
        
        # Compare using multiple metrics
        correlation = self._calculate_correlation(hist1, hist2)
        chi_squared = self._calculate_chi_squared(hist1, hist2)
        intersection = self._calculate_intersection(hist1, hist2)
        bhattacharyya = self._calculate_bhattacharyya(hist1, hist2)
        
        # Calculate per-channel scores if multichannel
        channel_scores = self._calculate_channel_scores(frame1_converted, frame2_converted)
        
        # Combine metrics into final score
        combined_score = self._combine_scores(correlation, chi_squared, intersection, bhattacharyya)
        
        processing_time = time.time() - start_time
        
        result = HistogramResult(
            correlation_score=float(correlation),
            chi_squared_score=float(chi_squared),
            intersection_score=float(intersection),
            bhattacharyya_score=float(bhattacharyya),
            combined_score=float(combined_score),
            color_channel_scores=channel_scores,
            processing_time=processing_time
        )
        
        logger.debug(f"✅ Histogram complete: combined={combined_score:.4f}, time={processing_time:.3f}s")
        
        return result
    
    def _normalize_frames(self, frame1: np.ndarray, frame2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Ensure frames have the same dimensions"""
        if frame1.shape != frame2.shape:
            min_height = min(frame1.shape[0], frame2.shape[0])
            min_width = min(frame1.shape[1], frame2.shape[1])
            
            frame1 = cv2.resize(frame1, (min_width, min_height), interpolation=cv2.INTER_AREA)
            frame2 = cv2.resize(frame2, (min_width, min_height), interpolation=cv2.INTER_AREA)
        
        return frame1, frame2
    
    def _convert_color_space(self, frame: np.ndarray) -> np.ndarray:
        """Convert frame to target color space"""
        if self.color_space == "BGR":
            return frame
        elif self.color_space == "HSV":
            return cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        elif self.color_space == "LAB":
            return cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        else:
            logger.warning(f"Unknown color space {self.color_space}, using BGR")
            return frame
    
    def _calculate_histogram(self, frame: np.ndarray) -> np.ndarray:
        """Calculate multi-channel histogram"""
        if len(frame.shape) == 2:
            # Grayscale
            hist = cv2.calcHist([frame], [0], None, [self.bins], [0, 256])
        else:
            # Multi-channel
            ranges = self.ranges.get(self.color_space, [0, 256] * 3)
            
            if self.color_space == "HSV":
                hist = cv2.calcHist([frame], [0, 1, 2], None, 
                                  [180, self.bins, self.bins], 
                                  [0, 180, 0, 256, 0, 256])
            else:
                hist = cv2.calcHist([frame], [0, 1, 2], None, 
                                  [self.bins, self.bins, self.bins], 
                                  ranges)
        
        # Normalize if requested
        if self.normalize:
            hist = cv2.normalize(hist, hist).flatten()
        else:
            hist = hist.flatten()
        
        return hist
    
    def _calculate_correlation(self, hist1: np.ndarray, hist2: np.ndarray) -> float:
        """Calculate correlation coefficient between histograms"""
        try:
            correlation = cv2.compareHist(hist1.reshape(-1, 1), hist2.reshape(-1, 1), cv2.HISTCMP_CORREL)
            # Ensure correlation is between 0 and 1
            return max(0.0, float(correlation))
        except:
            return 0.0
    
    def _calculate_chi_squared(self, hist1: np.ndarray, hist2: np.ndarray) -> float:
        """Calculate chi-squared distance (converted to similarity score)"""
        try:
            chi_squared = cv2.compareHist(hist1.reshape(-1, 1), hist2.reshape(-1, 1), cv2.HISTCMP_CHISQR)
            # Convert distance to similarity (lower distance = higher similarity)
            # Use exponential decay to convert to 0-1 range
            similarity = np.exp(-chi_squared / 1000.0)  # Adjust divisor based on typical values
            return float(similarity)
        except:
            return 0.0
    
    def _calculate_intersection(self, hist1: np.ndarray, hist2: np.ndarray) -> float:
        """Calculate histogram intersection"""
        try:
            intersection = cv2.compareHist(hist1.reshape(-1, 1), hist2.reshape(-1, 1), cv2.HISTCMP_INTERSECT)
            # Normalize by the sum of smaller histogram
            if self.normalize:
                return float(intersection)  # Already normalized
            else:
                min_sum = min(np.sum(hist1), np.sum(hist2))
                return float(intersection / min_sum) if min_sum > 0 else 0.0
        except:
            return 0.0
    
    def _calculate_bhattacharyya(self, hist1: np.ndarray, hist2: np.ndarray) -> float:
        """Calculate Bhattacharyya distance (converted to similarity)"""
        try:
            bhattacharyya = cv2.compareHist(hist1.reshape(-1, 1), hist2.reshape(-1, 1), cv2.HISTCMP_BHATTACHARYYA)
            # Convert distance to similarity
            similarity = 1.0 - min(bhattacharyya, 1.0)
            return float(similarity)
        except:
            return 0.0
    
    def _calculate_channel_scores(self, frame1: np.ndarray, frame2: np.ndarray) -> Dict[str, float]:
        """Calculate per-channel histogram similarity scores"""
        channel_scores = {}
        
        if len(frame1.shape) == 2:
            # Grayscale
            hist1 = cv2.calcHist([frame1], [0], None, [self.bins], [0, 256])
            hist2 = cv2.calcHist([frame2], [0], None, [self.bins], [0, 256])
            
            if self.normalize:
                hist1 = cv2.normalize(hist1, hist1).flatten()
                hist2 = cv2.normalize(hist2, hist2).flatten()
            
            correlation = self._calculate_correlation(hist1, hist2)
            channel_scores["gray"] = correlation
            
        else:
            # Multi-channel
            channel_names = {
                "BGR": ["blue", "green", "red"],
                "HSV": ["hue", "saturation", "value"],
                "LAB": ["lightness", "a", "b"]
            }.get(self.color_space, ["ch0", "ch1", "ch2"])
            
            for i, channel_name in enumerate(channel_names):
                try:
                    # Extract single channel
                    ch1 = frame1[:, :, i]
                    ch2 = frame2[:, :, i]
                    
                    # Calculate histogram for this channel
                    range_max = 180 if self.color_space == "HSV" and i == 0 else 256
                    hist1 = cv2.calcHist([ch1], [0], None, [self.bins], [0, range_max])
                    hist2 = cv2.calcHist([ch2], [0], None, [self.bins], [0, range_max])
                    
                    if self.normalize:
                        hist1 = cv2.normalize(hist1, hist1).flatten()
                        hist2 = cv2.normalize(hist2, hist2).flatten()
                    
                    # Calculate correlation for this channel
                    correlation = self._calculate_correlation(hist1, hist2)
                    channel_scores[channel_name] = correlation
                    
                except Exception as e:
                    logger.warning(f"Channel {channel_name} scoring failed: {e}")
                    channel_scores[channel_name] = 0.0
        
        return channel_scores
    
    def _combine_scores(self, correlation: float, chi_squared: float, 
                       intersection: float, bhattacharyya: float) -> float:
        """Combine multiple histogram metrics into single score"""
        combined = (
            self.weights["correlation"] * correlation +
            self.weights["chi_squared"] * chi_squared +
            self.weights["intersection"] * intersection +
            self.weights["bhattacharyya"] * bhattacharyya
        )
        
        return max(0.0, min(1.0, combined))  # Clamp to 0-1 range
    
    def compare_batch(self, frames1: List[np.ndarray], frames2: List[np.ndarray]) -> List[HistogramResult]:
        """Compare multiple frame pairs using histogram analysis"""
        if len(frames1) != len(frames2):
            raise ValueError("Frame lists must have the same length")
        
        results = []
        logger.info(f"📊 Starting batch histogram comparison: {len(frames1)} frame pairs")
        
        for i, (frame1, frame2) in enumerate(zip(frames1, frames2)):
            try:
                result = self.compare_frames(frame1, frame2)
                results.append(result)
                
                if (i + 1) % 50 == 0:
                    avg_score = np.mean([r.combined_score for r in results[-50:]])
                    logger.info(f"Progress: {i + 1}/{len(frames1)}, avg histogram: {avg_score:.4f}")
                    
            except Exception as e:
                logger.error(f"Frame pair {i} histogram comparison failed: {e}")
                results.append(HistogramResult(
                    correlation_score=0.0,
                    chi_squared_score=0.0,
                    intersection_score=0.0,
                    bhattacharyya_score=0.0,
                    combined_score=0.0,
                    color_channel_scores={},
                    processing_time=0.0
                ))
        
        avg_score = np.mean([r.combined_score for r in results])
        logger.info(f"✅ Batch histogram complete: avg score={avg_score:.4f}")
        
        return results
    
    def get_algorithm_info(self) -> Dict[str, Any]:
        """Get algorithm configuration info"""
        return {
            "name": "Histogram",
            "full_name": "Color Histogram Comparison",
            "version": "1.0",
            "parameters": {
                "bins": self.bins,
                "color_space": self.color_space,
                "normalize": self.normalize,
                "weights": self.weights
            },
            "metrics": [
                "correlation", "chi_squared", "intersection", "bhattacharyya"
            ],
            "description": "Compares color distribution between frames using multiple histogram metrics",
            "score_range": "0.0 (completely different) to 1.0 (identical)",
            "optimal_threshold": 0.85
        }
