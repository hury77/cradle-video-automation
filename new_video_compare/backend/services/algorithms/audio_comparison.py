"""
Audio Comparison Algorithms
Advanced algorithms for comparing audio tracks from video files
"""

import numpy as np
from scipy import signal
from scipy.stats import pearsonr
from typing import Tuple, Dict, List, Optional, Any
import logging
from ..utils.spectral_analysis import SpectralAnalyzer
from ..utils.audio_utils import AudioProcessor
from ..exceptions import VideoProcessingError

logger = logging.getLogger(__name__)


class AudioComparator:
    """
    Main audio comparison engine with multiple algorithms
    """

    def __init__(self, sample_rate: int = 44100):
        """
        Initialize audio comparator

        Args:
            sample_rate: Audio sample rate in Hz
        """
        self.sample_rate = sample_rate
        self.spectral_analyzer = SpectralAnalyzer(sample_rate)
        self.audio_processor = AudioProcessor()

    def cross_correlation_sync(
        self, audio1: np.ndarray, audio2: np.ndarray, max_offset: Optional[int] = None
    ) -> Tuple[int, float, Dict]:
        """
        Find synchronization offset using cross-correlation

        Args:
            audio1: First audio track
            audio2: Second audio track
            max_offset: Maximum offset to search (samples)

        Returns:
            Tuple of (best_offset, correlation_strength, metadata)
        """
        try:
            # Convert to mono if stereo
            if len(audio1.shape) == 2:
                mono1 = np.mean(audio1.astype(np.float64), axis=1)
            else:
                mono1 = audio1.astype(np.float64)

            if len(audio2.shape) == 2:
                mono2 = np.mean(audio2.astype(np.float64), axis=1)
            else:
                mono2 = audio2.astype(np.float64)

            # Normalize audio
            mono1 = mono1 / (np.max(np.abs(mono1)) + 1e-10)
            mono2 = mono2 / (np.max(np.abs(mono2)) + 1e-10)

            # Limit search range if specified
            if max_offset is None:
                max_offset = min(len(mono1), len(mono2)) // 4

            # Compute cross-correlation
            correlation = signal.correlate(mono1, mono2, mode="full")

            # Find valid correlation range
            correlation_center = len(correlation) // 2
            start_idx = max(0, correlation_center - max_offset)
            end_idx = min(len(correlation), correlation_center + max_offset + 1)

            valid_correlation = correlation[start_idx:end_idx]
            valid_lags = np.arange(
                start_idx - correlation_center, end_idx - correlation_center
            )

            # Find best offset
            best_idx = np.argmax(np.abs(valid_correlation))
            best_offset = valid_lags[best_idx]
            correlation_strength = valid_correlation[best_idx]

            # Normalize correlation strength
            max_possible_corr = min(len(mono1), len(mono2))
            normalized_strength = correlation_strength / max_possible_corr

            metadata = {
                "best_offset": best_offset,
                "correlation_strength": correlation_strength,
                "normalized_strength": normalized_strength,
                "max_offset_searched": max_offset,
                "time_offset_seconds": best_offset / self.sample_rate,
                "search_range_seconds": max_offset / self.sample_rate,
                "algorithm": "cross_correlation",
            }

            return best_offset, normalized_strength, metadata

        except Exception as e:
            raise VideoProcessingError(f"Cross-correlation sync failed: {str(e)}")

    def spectral_similarity(
        self, audio1: np.ndarray, audio2: np.ndarray
    ) -> Tuple[float, Dict]:
        """
        Compare audio using spectral analysis

        Args:
            audio1: First audio track
            audio2: Second audio track

        Returns:
            Tuple of (similarity_score, metadata)
        """
        try:
            # Compute FFT for both tracks
            freq1, mag1 = self.spectral_analyzer.compute_fft(audio1)
            freq2, mag2 = self.spectral_analyzer.compute_fft(audio2)

            # Ensure same frequency range
            min_freq_bins = min(len(freq1), len(freq2))
            mag1_aligned = mag1[:min_freq_bins]
            mag2_aligned = mag2[:min_freq_bins]
            freq_aligned = freq1[:min_freq_bins]

            # Normalize magnitudes
            mag1_norm = mag1_aligned / (np.sum(mag1_aligned) + 1e-10)
            mag2_norm = mag2_aligned / (np.sum(mag2_aligned) + 1e-10)

            # Compute spectral features
            features1 = self.spectral_analyzer.compute_spectral_features(
                freq_aligned, mag1_aligned
            )
            features2 = self.spectral_analyzer.compute_spectral_features(
                freq_aligned, mag2_aligned
            )

            # Correlation between magnitude spectra
            spectrum_correlation, _ = pearsonr(mag1_norm, mag2_norm)
            if np.isnan(spectrum_correlation):
                spectrum_correlation = 0.0

            # Feature similarity
            feature_similarities = {}
            feature_weights = {
                "centroid": 0.25,
                "spread": 0.20,
                "rolloff": 0.20,
                "skewness": 0.15,
                "kurtosis": 0.10,
                "flux": 0.10,
            }

            weighted_feature_sim = 0.0
            total_weight = 0.0

            for feature, weight in feature_weights.items():
                if feature in features1 and feature in features2:
                    val1 = features1[feature]
                    val2 = features2[feature]

                    if val1 == 0 and val2 == 0:
                        feature_sim = 1.0
                    elif val1 == 0 or val2 == 0:
                        feature_sim = 0.0
                    else:
                        # Normalized similarity
                        diff = abs(val1 - val2)
                        max_val = max(abs(val1), abs(val2))
                        feature_sim = max(0.0, 1.0 - diff / max_val)

                    feature_similarities[feature] = feature_sim
                    weighted_feature_sim += feature_sim * weight
                    total_weight += weight

            feature_similarity = (
                weighted_feature_sim / total_weight if total_weight > 0 else 0.0
            )

            # Combined spectral similarity
            spectral_weight = 0.6
            feature_weight = 0.4

            combined_similarity = (
                spectral_weight * max(0.0, spectrum_correlation)
                + feature_weight * feature_similarity
            )

            metadata = {
                "spectrum_correlation": spectrum_correlation,
                "feature_similarity": feature_similarity,
                "feature_similarities": feature_similarities,
                "features1": features1,
                "features2": features2,
                "combined_similarity": combined_similarity,
                "frequency_bins": min_freq_bins,
                "algorithm": "spectral_similarity",
            }

            return combined_similarity, metadata

        except Exception as e:
            raise VideoProcessingError(
                f"Spectral similarity computation failed: {str(e)}"
            )

    def mfcc_similarity(
        self, audio1: np.ndarray, audio2: np.ndarray, n_mfcc: int = 13
    ) -> Tuple[float, Dict]:
        """
        Compare audio using MFCC features

        Args:
            audio1: First audio track
            audio2: Second audio track
            n_mfcc: Number of MFCC coefficients

        Returns:
            Tuple of (similarity_score, metadata)
        """
        try:
            # Compute MFCCs
            mfcc1 = self.spectral_analyzer.compute_mfcc(audio1, n_mfcc=n_mfcc)
            mfcc2 = self.spectral_analyzer.compute_mfcc(audio2, n_mfcc=n_mfcc)

            # Align temporal dimensions
            min_time_frames = min(mfcc1.shape[1], mfcc2.shape[1])
            mfcc1_aligned = mfcc1[:, :min_time_frames]
            mfcc2_aligned = mfcc2[:, :min_time_frames]

            # Compute similarity for each MFCC coefficient
            coefficient_similarities = []

            for i in range(n_mfcc):
                coeff1 = mfcc1_aligned[i, :]
                coeff2 = mfcc2_aligned[i, :]

                # Correlation between coefficients over time
                if len(coeff1) > 1 and len(coeff2) > 1:
                    corr, _ = pearsonr(coeff1, coeff2)
                    if np.isnan(corr):
                        corr = 0.0
                else:
                    corr = 1.0 if np.allclose(coeff1, coeff2) else 0.0

                coefficient_similarities.append(max(0.0, corr))

            # Compute statistical similarity of MFCC distributions
            mfcc1_stats = {
                "mean": np.mean(mfcc1_aligned, axis=1),
                "std": np.std(mfcc1_aligned, axis=1),
                "var": np.var(mfcc1_aligned, axis=1),
            }

            mfcc2_stats = {
                "mean": np.mean(mfcc2_aligned, axis=1),
                "std": np.std(mfcc2_aligned, axis=1),
                "var": np.var(mfcc2_aligned, axis=1),
            }

            # Statistical similarity
            mean_similarity = np.mean(
                [
                    max(0.0, 1.0 - abs(m1 - m2) / (max(abs(m1), abs(m2)) + 1e-10))
                    for m1, m2 in zip(mfcc1_stats["mean"], mfcc2_stats["mean"])
                ]
            )

            std_similarity = np.mean(
                [
                    max(0.0, 1.0 - abs(s1 - s2) / (max(s1, s2) + 1e-10))
                    for s1, s2 in zip(mfcc1_stats["std"], mfcc2_stats["std"])
                ]
            )

            # Weighted combination
            temporal_weight = 0.6  # Correlation over time
            statistical_weight = 0.4  # Statistical similarity

            temporal_similarity = np.mean(coefficient_similarities)
            statistical_similarity = (mean_similarity + std_similarity) / 2.0

            combined_similarity = (
                temporal_weight * temporal_similarity
                + statistical_weight * statistical_similarity
            )

            metadata = {
                "temporal_similarity": temporal_similarity,
                "statistical_similarity": statistical_similarity,
                "mean_similarity": mean_similarity,
                "std_similarity": std_similarity,
                "coefficient_similarities": coefficient_similarities,
                "mfcc1_stats": mfcc1_stats,
                "mfcc2_stats": mfcc2_stats,
                "time_frames": min_time_frames,
                "n_mfcc": n_mfcc,
                "algorithm": "mfcc_similarity",
            }

            return combined_similarity, metadata

        except Exception as e:
            raise VideoProcessingError(f"MFCC similarity computation failed: {str(e)}")

    def perceptual_similarity(
        self, audio1: np.ndarray, audio2: np.ndarray
    ) -> Tuple[float, Dict]:
        """
        Compare audio using perceptual weighting

        Args:
            audio1: First audio track
            audio2: Second audio track

        Returns:
            Tuple of (similarity_score, metadata)
        """
        try:
            # Compute spectrograms
            freq1, time1, spec1 = self.spectral_analyzer.compute_spectrogram(audio1)
            freq2, time2, spec2 = self.spectral_analyzer.compute_spectrogram(audio2)

            # Align spectrograms
            min_freq_bins = min(spec1.shape[0], spec2.shape[0])
            min_time_bins = min(spec1.shape[1], spec2.shape[1])

            spec1_aligned = spec1[:min_freq_bins, :min_time_bins]
            spec2_aligned = spec2[:min_freq_bins, :min_time_bins]
            freq_aligned = freq1[:min_freq_bins]

            # Apply perceptual weighting (A-weighting approximation)
            perceptual_weights = self._compute_perceptual_weights(freq_aligned)

            # Weight spectrograms
            weighted_spec1 = spec1_aligned * perceptual_weights[:, np.newaxis]
            weighted_spec2 = spec2_aligned * perceptual_weights[:, np.newaxis]

            # Compare weighted spectrograms
            spectrogram_metrics = self.spectral_analyzer.compare_spectrograms(
                weighted_spec1, weighted_spec2
            )

            # Compute perceptual loudness difference
            loudness1 = self._compute_perceptual_loudness(weighted_spec1, freq_aligned)
            loudness2 = self._compute_perceptual_loudness(weighted_spec2, freq_aligned)

            loudness_similarity = max(
                0.0,
                1.0 - abs(loudness1 - loudness2) / (max(loudness1, loudness2) + 1e-10),
            )

            # Critical band analysis
            critical_band_sim = self._compare_critical_bands(
                spec1_aligned, spec2_aligned, freq_aligned
            )

            # Combined perceptual similarity
            spectrogram_weight = 0.4
            loudness_weight = 0.3
            critical_band_weight = 0.3

            perceptual_similarity = (
                spectrogram_weight * spectrogram_metrics["similarity_score"]
                + loudness_weight * loudness_similarity
                + critical_band_weight * critical_band_sim
            )

            metadata = {
                "perceptual_similarity": perceptual_similarity,
                "spectrogram_metrics": spectrogram_metrics,
                "loudness_similarity": loudness_similarity,
                "critical_band_similarity": critical_band_sim,
                "loudness1": loudness1,
                "loudness2": loudness2,
                "frequency_bins": min_freq_bins,
                "time_bins": min_time_bins,
                "algorithm": "perceptual_similarity",
            }

            return perceptual_similarity, metadata

        except Exception as e:
            raise VideoProcessingError(
                f"Perceptual similarity computation failed: {str(e)}"
            )

    def _compute_perceptual_weights(self, frequencies: np.ndarray) -> np.ndarray:
        """
        Compute A-weighting-like perceptual weights

        Args:
            frequencies: Frequency array

        Returns:
            Perceptual weights array
        """
        # Simplified A-weighting formula
        f = frequencies + 1e-10  # Avoid division by zero

        # A-weighting approximation
        c1 = 12194.217**2
        c2 = 20.598997**2
        c3 = 107.65265**2
        c4 = 737.86223**2

        numerator = c1 * f**4
        denominator = (f**2 + c2) * np.sqrt((f**2 + c3) * (f**2 + c4)) * (f**2 + c1)

        a_weight_linear = numerator / denominator

        # Normalize to 0-1 range
        a_weight_normalized = a_weight_linear / np.max(a_weight_linear)

        return a_weight_normalized

    def _compute_perceptual_loudness(
        self, spectrogram: np.ndarray, frequencies: np.ndarray
    ) -> float:
        """
        Compute perceptual loudness from spectrogram

        Args:
            spectrogram: Input spectrogram
            frequencies: Frequency array

        Returns:
            Perceptual loudness value
        """
        # Simple loudness model based on RMS with frequency weighting
        power_spectrum = np.mean(spectrogram**2, axis=1)  # Average over time

        # Weight by frequency (emphasize mid frequencies)
        weights = self._compute_perceptual_weights(frequencies)
        weighted_power = power_spectrum * weights

        # Compute loudness (log scale)
        total_power = np.sum(weighted_power)
        loudness = 10 * np.log10(total_power + 1e-10)

        return loudness

    def _compare_critical_bands(
        self, spec1: np.ndarray, spec2: np.ndarray, frequencies: np.ndarray
    ) -> float:
        """
        Compare spectrograms using critical band analysis

        Args:
            spec1: First spectrogram
            spec2: Second spectrogram
            frequencies: Frequency array

        Returns:
            Critical band similarity score
        """
        # Define critical band centers (Bark scale approximation)
        critical_bands = [
            50,
            150,
            250,
            350,
            450,
            570,
            700,
            840,
            1000,
            1170,
            1370,
            1600,
            1850,
            2150,
            2500,
            2900,
            3400,
            4000,
            4800,
            5800,
            7000,
            8500,
            10500,
            13500,
        ]

        band_similarities = []

        for i, center_freq in enumerate(critical_bands):
            if center_freq > frequencies[-1]:
                break

            # Find frequency range for this band
            if i == 0:
                low_freq = 0
            else:
                low_freq = (critical_bands[i - 1] + center_freq) / 2

            if i == len(critical_bands) - 1:
                high_freq = frequencies[-1]
            else:
                high_freq = (center_freq + critical_bands[i + 1]) / 2

            # Find frequency bin indices
            low_idx = np.searchsorted(frequencies, low_freq)
            high_idx = np.searchsorted(frequencies, high_freq)

            if high_idx > low_idx:
                # Extract band energy
                band1 = np.mean(spec1[low_idx:high_idx, :])
                band2 = np.mean(spec2[low_idx:high_idx, :])

                # Compute similarity
                if band1 == 0 and band2 == 0:
                    band_sim = 1.0
                elif band1 == 0 or band2 == 0:
                    band_sim = 0.0
                else:
                    band_sim = min(band1, band2) / max(band1, band2)

                band_similarities.append(band_sim)

        return np.mean(band_similarities) if band_similarities else 0.0

    def comprehensive_comparison(
        self,
        audio1: np.ndarray,
        audio2: np.ndarray,
        sync_audio: bool = True,
        weights: Optional[Dict[str, float]] = None,
    ) -> Tuple[float, Dict]:
        """
        Comprehensive audio comparison using all algorithms

        Args:
            audio1: First audio track
            audio2: Second audio track
            sync_audio: Whether to synchronize audio before comparison
            weights: Optional weights for different algorithms

        Returns:
            Tuple of (overall_similarity, comprehensive_metadata)
        """
        try:
            if weights is None:
                weights = {
                    "spectral": 0.3,
                    "mfcc": 0.25,
                    "perceptual": 0.25,
                    "sync_quality": 0.2,
                }

            results = {}
            synchronized_audio1 = audio1
            synchronized_audio2 = audio2

            # Synchronization
            if sync_audio:
                try:
                    offset, sync_strength, sync_metadata = self.cross_correlation_sync(
                        audio1, audio2
                    )
                    results["synchronization"] = {
                        "offset": offset,
                        "strength": sync_strength,
                        "metadata": sync_metadata,
                    }

                    # Apply synchronization offset
                    if offset > 0:
                        synchronized_audio1 = audio1[offset:]
                        synchronized_audio2 = audio2[: len(synchronized_audio1)]
                    elif offset < 0:
                        synchronized_audio2 = audio2[-offset:]
                        synchronized_audio1 = audio1[: len(synchronized_audio2)]

                except Exception as e:
                    logger.warning(f"Audio synchronization failed: {str(e)}")
                    results["synchronization"] = {"error": str(e), "strength": 0.0}
                    sync_strength = 0.0
            else:
                sync_strength = 1.0  # Assume perfect sync if not checking

            # Run comparison algorithms
            try:
                spectral_sim, spectral_meta = self.spectral_similarity(
                    synchronized_audio1, synchronized_audio2
                )
                results["spectral"] = {
                    "similarity": spectral_sim,
                    "metadata": spectral_meta,
                }
            except Exception as e:
                logger.warning(f"Spectral comparison failed: {str(e)}")
                results["spectral"] = {"similarity": 0.0, "error": str(e)}
                spectral_sim = 0.0

            try:
                mfcc_sim, mfcc_meta = self.mfcc_similarity(
                    synchronized_audio1, synchronized_audio2
                )
                results["mfcc"] = {"similarity": mfcc_sim, "metadata": mfcc_meta}
            except Exception as e:
                logger.warning(f"MFCC comparison failed: {str(e)}")
                results["mfcc"] = {"similarity": 0.0, "error": str(e)}
                mfcc_sim = 0.0

            try:
                perceptual_sim, perceptual_meta = self.perceptual_similarity(
                    synchronized_audio1, synchronized_audio2
                )
                results["perceptual"] = {
                    "similarity": perceptual_sim,
                    "metadata": perceptual_meta,
                }
            except Exception as e:
                logger.warning(f"Perceptual comparison failed: {str(e)}")
                results["perceptual"] = {"similarity": 0.0, "error": str(e)}
                perceptual_sim = 0.0

            # Compute weighted overall similarity
            overall_similarity = (
                weights["spectral"] * spectral_sim
                + weights["mfcc"] * mfcc_sim
                + weights["perceptual"] * perceptual_sim
                + weights["sync_quality"] * sync_strength
            )

            comprehensive_metadata = {
                "overall_similarity": overall_similarity,
                "individual_results": results,
                "weights_used": weights,
                "synchronization_applied": sync_audio,
                "algorithm": "comprehensive_audio_comparison",
            }

            return overall_similarity, comprehensive_metadata

        except Exception as e:
            raise VideoProcessingError(
                f"Comprehensive audio comparison failed: {str(e)}"
            )
