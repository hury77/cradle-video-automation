"""
Perceptual Hash Algorithm for Video Comparison
Generates and compares perceptual hashes of video frames
"""

import cv2
import numpy as np
from typing import Tuple, List, Optional
import logging
from ..utils.exceptions import VideoProcessingError

logger = logging.getLogger(__name__)


class PerceptualHashComparator:
    """
    Perceptual Hash-based frame comparison
    Uses dHash (difference hash) algorithm for robust comparison
    """

    def __init__(self, hash_size: int = 8):
        """
        Initialize perceptual hash comparator

        Args:
            hash_size: Size of hash matrix (default 8x8 = 64-bit hash)
        """
        self.hash_size = hash_size
        self.hash_bits = hash_size * hash_size

    def compute_hash(self, frame: np.ndarray) -> str:
        """
        Compute perceptual hash for a frame

        Args:
            frame: Input frame (BGR or grayscale)

        Returns:
            Hexadecimal hash string

        Raises:
            VideoProcessingError: If hash computation fails
        """
        try:
            # Convert to grayscale if needed
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame

            # Resize to (hash_size + 1) x hash_size for difference calculation
            resized = cv2.resize(gray, (self.hash_size + 1, self.hash_size))

            # Calculate horizontal differences
            diff = resized[:, 1:] > resized[:, :-1]

            # Convert boolean array to hash string
            hash_bits = diff.flatten()
            hash_int = sum(2**i for i, bit in enumerate(hash_bits) if bit)

            # Convert to hexadecimal string
            hex_length = (self.hash_bits + 3) // 4  # Round up to hex digits
            hash_hex = f"{hash_int:0{hex_length}x}"

            return hash_hex

        except Exception as e:
            raise VideoProcessingError(f"Failed to compute perceptual hash: {str(e)}")

    def compare_hashes(self, hash1: str, hash2: str) -> float:
        """
        Compare two perceptual hashes using Hamming distance

        Args:
            hash1: First hash string
            hash2: Second hash string

        Returns:
            Similarity score (0.0 = completely different, 1.0 = identical)

        Raises:
            VideoProcessingError: If comparison fails
        """
        try:
            if len(hash1) != len(hash2):
                raise ValueError("Hash lengths must be equal")

            # Convert hex strings to integers
            int1 = int(hash1, 16)
            int2 = int(hash2, 16)

            # Calculate Hamming distance (XOR and count bits)
            xor_result = int1 ^ int2
            hamming_distance = bin(xor_result).count("1")

            # Convert to similarity score
            max_distance = self.hash_bits
            similarity = 1.0 - (hamming_distance / max_distance)

            return similarity

        except Exception as e:
            raise VideoProcessingError(f"Failed to compare hashes: {str(e)}")

    def compare_frames(
        self, frame1: np.ndarray, frame2: np.ndarray
    ) -> Tuple[float, dict]:
        """
        Compare two frames using perceptual hashing

        Args:
            frame1: First frame
            frame2: Second frame

        Returns:
            Tuple of (similarity_score, metadata)

        Raises:
            VideoProcessingError: If comparison fails
        """
        try:
            # Compute hashes
            hash1 = self.compute_hash(frame1)
            hash2 = self.compute_hash(frame2)

            # Compare hashes
            similarity = self.compare_hashes(hash1, hash2)

            # Additional metadata
            metadata = {
                "hash1": hash1,
                "hash2": hash2,
                "hash_size": self.hash_size,
                "hash_bits": self.hash_bits,
                "hamming_distance": int((1.0 - similarity) * self.hash_bits),
                "algorithm": "perceptual_hash",
            }

            return similarity, metadata

        except Exception as e:
            raise VideoProcessingError(f"Frame comparison failed: {str(e)}")

    def batch_compare(
        self, frames1: List[np.ndarray], frames2: List[np.ndarray]
    ) -> List[Tuple[float, dict]]:
        """
        Compare multiple frame pairs efficiently

        Args:
            frames1: List of first frames
            frames2: List of second frames

        Returns:
            List of (similarity, metadata) tuples

        Raises:
            VideoProcessingError: If batch comparison fails
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
                    # Add failed result
                    results.append(
                        (
                            0.0,
                            {
                                "frame_index": i,
                                "error": str(e),
                                "algorithm": "perceptual_hash",
                            },
                        )
                    )

            return results

        except Exception as e:
            raise VideoProcessingError(f"Batch comparison failed: {str(e)}")


class AdvancedPerceptualHash(PerceptualHashComparator):
    """
    Advanced perceptual hash with multiple hash types
    Combines dHash, aHash, and pHash for better accuracy
    """

    def __init__(self, hash_size: int = 8):
        super().__init__(hash_size)

    def compute_dhash(self, frame: np.ndarray) -> str:
        """Difference hash (horizontal differences)"""
        return super().compute_hash(frame)

    def compute_ahash(self, frame: np.ndarray) -> str:
        """
        Average hash - compare pixels to average brightness

        Args:
            frame: Input frame

        Returns:
            Average hash string
        """
        try:
            # Convert to grayscale
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame

            # Resize to hash_size x hash_size
            resized = cv2.resize(gray, (self.hash_size, self.hash_size))

            # Calculate average brightness
            avg_brightness = np.mean(resized)

            # Compare each pixel to average
            hash_bits = resized > avg_brightness

            # Convert to hex string
            hash_bits_flat = hash_bits.flatten()
            hash_int = sum(2**i for i, bit in enumerate(hash_bits_flat) if bit)

            hex_length = (self.hash_bits + 3) // 4
            hash_hex = f"{hash_int:0{hex_length}x}"

            return hash_hex

        except Exception as e:
            raise VideoProcessingError(f"Failed to compute average hash: {str(e)}")

    def compute_phash(self, frame: np.ndarray) -> str:
        """
        Perceptual hash using DCT (Discrete Cosine Transform)

        Args:
            frame: Input frame

        Returns:
            Perceptual hash string
        """
        try:
            # Convert to grayscale
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame

            # Resize to 32x32 (larger for DCT)
            resized = cv2.resize(gray, (32, 32))
            resized = np.float32(resized)

            # Apply DCT
            dct = cv2.dct(resized)

            # Take top-left hash_size x hash_size region (low frequencies)
            dct_low = dct[: self.hash_size, : self.hash_size]

            # Calculate median (excluding DC component)
            dct_flat = dct_low.flatten()
            median = np.median(dct_flat[1:])  # Skip DC component

            # Compare to median
            hash_bits = dct_flat > median

            # Convert to hex string
            hash_int = sum(2**i for i, bit in enumerate(hash_bits) if bit)

            hex_length = (self.hash_bits + 3) // 4
            hash_hex = f"{hash_int:0{hex_length}x}"

            return hash_hex

        except Exception as e:
            raise VideoProcessingError(f"Failed to compute perceptual hash: {str(e)}")

    def compute_combined_hash(self, frame: np.ndarray) -> dict:
        """
        Compute all three hash types

        Args:
            frame: Input frame

        Returns:
            Dictionary with all hash types
        """
        try:
            return {
                "dhash": self.compute_dhash(frame),
                "ahash": self.compute_ahash(frame),
                "phash": self.compute_phash(frame),
            }

        except Exception as e:
            raise VideoProcessingError(f"Failed to compute combined hash: {str(e)}")

    def compare_combined_hashes(
        self, hashes1: dict, hashes2: dict, weights: Optional[dict] = None
    ) -> float:
        """
        Compare combined hashes with optional weighting

        Args:
            hashes1: First frame hashes
            hashes2: Second frame hashes
            weights: Optional weights for each hash type

        Returns:
            Weighted similarity score
        """
        if weights is None:
            weights = {"dhash": 0.4, "ahash": 0.3, "phash": 0.3}

        total_similarity = 0.0
        total_weight = 0.0

        for hash_type in ["dhash", "ahash", "phash"]:
            if hash_type in hashes1 and hash_type in hashes2:
                similarity = self.compare_hashes(hashes1[hash_type], hashes2[hash_type])
                weight = weights.get(hash_type, 1.0)

                total_similarity += similarity * weight
                total_weight += weight

        return total_similarity / total_weight if total_weight > 0 else 0.0

    def compare_frames_advanced(
        self, frame1: np.ndarray, frame2: np.ndarray
    ) -> Tuple[float, dict]:
        """
        Advanced frame comparison using multiple hash types

        Args:
            frame1: First frame
            frame2: Second frame

        Returns:
            Tuple of (similarity_score, metadata)
        """
        try:
            # Compute all hash types
            hashes1 = self.compute_combined_hash(frame1)
            hashes2 = self.compute_combined_hash(frame2)

            # Individual similarities
            dhash_sim = self.compare_hashes(hashes1["dhash"], hashes2["dhash"])
            ahash_sim = self.compare_hashes(hashes1["ahash"], hashes2["ahash"])
            phash_sim = self.compare_hashes(hashes1["phash"], hashes2["phash"])

            # Combined similarity
            combined_sim = self.compare_combined_hashes(hashes1, hashes2)

            metadata = {
                "hashes1": hashes1,
                "hashes2": hashes2,
                "dhash_similarity": dhash_sim,
                "ahash_similarity": ahash_sim,
                "phash_similarity": phash_sim,
                "combined_similarity": combined_sim,
                "algorithm": "advanced_perceptual_hash",
            }

            return combined_sim, metadata

        except Exception as e:
            raise VideoProcessingError(f"Advanced frame comparison failed: {str(e)}")
