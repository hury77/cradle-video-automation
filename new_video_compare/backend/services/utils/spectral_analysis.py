"""
Spectral Analysis Utilities
Advanced frequency domain analysis for audio comparison
"""

import numpy as np
from scipy import signal
from scipy.fft import fft, fftfreq, stft
from typing import Tuple, Dict, List, Optional, Any
import logging
from ..exceptions import VideoProcessingError

logger = logging.getLogger(__name__)


class SpectralAnalyzer:
    """
    Advanced spectral analysis for audio processing
    """

    def __init__(self, sample_rate: int = 44100):
        """
        Initialize spectral analyzer

        Args:
            sample_rate: Audio sample rate in Hz
        """
        self.sample_rate = sample_rate

    def compute_fft(
        self, audio_data: np.ndarray, window: str = "hann"
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute Fast Fourier Transform

        Args:
            audio_data: Input audio data
            window: Window function ('hann', 'hamming', 'blackman', 'none')

        Returns:
            Tuple of (frequencies, magnitudes)
        """
        try:
            # Convert to mono if stereo
            if len(audio_data.shape) == 2:
                mono = np.mean(audio_data.astype(np.float64), axis=1)
            else:
                mono = audio_data.astype(np.float64)

            # Apply window function
            if window != "none":
                if window == "hann":
                    windowed = mono * np.hanning(len(mono))
                elif window == "hamming":
                    windowed = mono * np.hamming(len(mono))
                elif window == "blackman":
                    windowed = mono * np.blackman(len(mono))
                else:
                    windowed = mono
            else:
                windowed = mono

            # Compute FFT
            fft_data = fft(windowed)
            frequencies = fftfreq(len(windowed), 1 / self.sample_rate)

            # Take only positive frequencies
            positive_freq_idx = frequencies >= 0
            frequencies = frequencies[positive_freq_idx]
            magnitudes = np.abs(fft_data[positive_freq_idx])

            return frequencies, magnitudes

        except Exception as e:
            raise VideoProcessingError(f"FFT computation failed: {str(e)}")

    def compute_spectrogram(
        self,
        audio_data: np.ndarray,
        nperseg: int = 1024,
        noverlap: Optional[int] = None,
        window: str = "hann",
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Compute spectrogram using Short-Time Fourier Transform

        Args:
            audio_data: Input audio data
            nperseg: Length of each segment
            noverlap: Number of points to overlap between segments
            window: Window function

        Returns:
            Tuple of (frequencies, times, spectrogram_matrix)
        """
        try:
            # Convert to mono if stereo
            if len(audio_data.shape) == 2:
                mono = np.mean(audio_data.astype(np.float64), axis=1)
            else:
                mono = audio_data.astype(np.float64)

            if noverlap is None:
                noverlap = nperseg // 2

            # Compute STFT
            frequencies, times, stft_matrix = stft(
                mono,
                fs=self.sample_rate,
                window=window,
                nperseg=nperseg,
                noverlap=noverlap,
            )

            # Convert to magnitude spectrogram
            spectrogram = np.abs(stft_matrix)

            return frequencies, times, spectrogram

        except Exception as e:
            raise VideoProcessingError(f"Spectrogram computation failed: {str(e)}")

    def compute_power_spectral_density(
        self, audio_data: np.ndarray, nperseg: int = 1024
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute Power Spectral Density

        Args:
            audio_data: Input audio data
            nperseg: Length of each segment

        Returns:
            Tuple of (frequencies, power_spectral_density)
        """
        try:
            # Convert to mono if stereo
            if len(audio_data.shape) == 2:
                mono = np.mean(audio_data.astype(np.float64), axis=1)
            else:
                mono = audio_data.astype(np.float64)

            # Compute PSD using Welch's method
            frequencies, psd = signal.welch(mono, fs=self.sample_rate, nperseg=nperseg)

            return frequencies, psd

        except Exception as e:
            raise VideoProcessingError(f"PSD computation failed: {str(e)}")

    def compute_mfcc(
        self,
        audio_data: np.ndarray,
        n_mfcc: int = 13,
        n_fft: int = 2048,
        hop_length: int = 512,
        n_mels: int = 40,
    ) -> np.ndarray:
        """
        Compute Mel-Frequency Cepstral Coefficients (MFCC)

        Args:
            audio_data: Input audio data
            n_mfcc: Number of MFCCs to return
            n_fft: FFT window size
            hop_length: Number of samples between successive frames
            n_mels: Number of Mel bands

        Returns:
            MFCC feature matrix
        """
        try:
            # Convert to mono if stereo
            if len(audio_data.shape) == 2:
                mono = np.mean(audio_data.astype(np.float64), axis=1)
            else:
                mono = audio_data.astype(np.float64)

            # Compute mel-scale spectrogram
            mel_spec = self._compute_mel_spectrogram(mono, n_fft, hop_length, n_mels)

            # Convert to log scale
            log_mel_spec = np.log(mel_spec + 1e-10)  # Add small epsilon to avoid log(0)

            # Apply DCT to get MFCCs
            mfccs = self._dct_transform(log_mel_spec, n_mfcc)

            return mfccs

        except Exception as e:
            raise VideoProcessingError(f"MFCC computation failed: {str(e)}")

    def _compute_mel_spectrogram(
        self, audio_data: np.ndarray, n_fft: int, hop_length: int, n_mels: int
    ) -> np.ndarray:
        """
        Compute mel-scale spectrogram

        Args:
            audio_data: Input audio data
            n_fft: FFT window size
            hop_length: Hop length
            n_mels: Number of mel bands

        Returns:
            Mel spectrogram
        """
        # Compute STFT
        frequencies, times, stft_matrix = stft(
            audio_data, fs=self.sample_rate, nperseg=n_fft, noverlap=n_fft - hop_length
        )

        # Convert to power spectrogram
        power_spec = np.abs(stft_matrix) ** 2

        # Create mel filter bank
        mel_filters = self._create_mel_filter_bank(frequencies, n_mels)

        # Apply mel filters
        mel_spec = np.dot(mel_filters, power_spec)

        return mel_spec

    def _create_mel_filter_bank(
        self, frequencies: np.ndarray, n_mels: int
    ) -> np.ndarray:
        """
        Create mel-scale filter bank

        Args:
            frequencies: Frequency bins
            n_mels: Number of mel bands

        Returns:
            Mel filter bank matrix
        """

        # Mel scale conversion functions
        def hz_to_mel(hz):
            return 2595 * np.log10(1 + hz / 700)

        def mel_to_hz(mel):
            return 700 * (10 ** (mel / 2595) - 1)

        # Create mel-spaced frequencies
        mel_min = hz_to_mel(frequencies[0])
        mel_max = hz_to_mel(frequencies[-1])
        mel_points = np.linspace(mel_min, mel_max, n_mels + 2)
        hz_points = mel_to_hz(mel_points)

        # Convert to frequency bin indices
        bin_indices = np.floor(
            (len(frequencies) - 1) * hz_points / frequencies[-1]
        ).astype(int)

        # Create filter bank
        filter_bank = np.zeros((n_mels, len(frequencies)))

        for i in range(1, n_mels + 1):
            left = bin_indices[i - 1]
            center = bin_indices[i]
            right = bin_indices[i + 1]

            # Left slope
            for j in range(left, center):
                if center != left:
                    filter_bank[i - 1, j] = (j - left) / (center - left)

            # Right slope
            for j in range(center, right):
                if right != center:
                    filter_bank[i - 1, j] = (right - j) / (right - center)

        return filter_bank

    def _dct_transform(self, matrix: np.ndarray, n_coeffs: int) -> np.ndarray:
        """
        Apply Discrete Cosine Transform for MFCC computation

        Args:
            matrix: Input matrix (log mel spectrogram)
            n_coeffs: Number of coefficients to return

        Returns:
            DCT coefficients (MFCCs)
        """
        n_bands, n_frames = matrix.shape

        # Create DCT matrix
        dct_matrix = np.zeros((n_coeffs, n_bands))

        for i in range(n_coeffs):
            for j in range(n_bands):
                if i == 0:
                    dct_matrix[i, j] = 1.0 / np.sqrt(n_bands)
                else:
                    dct_matrix[i, j] = np.sqrt(2.0 / n_bands) * np.cos(
                        np.pi * i * (2 * j + 1) / (2 * n_bands)
                    )

        # Apply DCT
        mfccs = np.dot(dct_matrix, matrix)

        return mfccs

    def find_spectral_peaks(
        self,
        frequencies: np.ndarray,
        magnitudes: np.ndarray,
        height: Optional[float] = None,
        distance: int = 10,
    ) -> Tuple[np.ndarray, Dict]:
        """
        Find spectral peaks in frequency domain

        Args:
            frequencies: Frequency array
            magnitudes: Magnitude array
            height: Minimum peak height
            distance: Minimum distance between peaks

        Returns:
            Tuple of (peak_frequencies, peak_properties)
        """
        try:
            # Find peaks
            peaks, properties = signal.find_peaks(
                magnitudes, height=height, distance=distance
            )

            peak_frequencies = frequencies[peaks]
            peak_magnitudes = magnitudes[peaks]

            # Sort by magnitude (strongest first)
            sorted_indices = np.argsort(peak_magnitudes)[::-1]
            peak_frequencies = peak_frequencies[sorted_indices]
            peak_magnitudes = peak_magnitudes[sorted_indices]

            peak_info = {
                "frequencies": peak_frequencies,
                "magnitudes": peak_magnitudes,
                "count": len(peak_frequencies),
                "properties": properties,
            }

            return peak_frequencies, peak_info

        except Exception as e:
            raise VideoProcessingError(f"Peak detection failed: {str(e)}")

    def compute_spectral_features(
        self, frequencies: np.ndarray, magnitudes: np.ndarray
    ) -> Dict[str, float]:
        """
        Compute various spectral features

        Args:
            frequencies: Frequency array
            magnitudes: Magnitude array

        Returns:
            Dictionary of spectral features
        """
        try:
            # Normalize magnitudes
            total_power = np.sum(magnitudes)
            if total_power == 0:
                return self._empty_spectral_features()

            normalized_magnitudes = magnitudes / total_power

            # Spectral centroid (center of mass)
            spectral_centroid = np.sum(frequencies * normalized_magnitudes)

            # Spectral spread (variance)
            spectral_spread = np.sqrt(
                np.sum(((frequencies - spectral_centroid) ** 2) * normalized_magnitudes)
            )

            # Spectral skewness (asymmetry)
            if spectral_spread > 0:
                spectral_skewness = np.sum(
                    (((frequencies - spectral_centroid) / spectral_spread) ** 3)
                    * normalized_magnitudes
                )
            else:
                spectral_skewness = 0.0

            # Spectral kurtosis (tailedness)
            if spectral_spread > 0:
                spectral_kurtosis = (
                    np.sum(
                        (((frequencies - spectral_centroid) / spectral_spread) ** 4)
                        * normalized_magnitudes
                    )
                    - 3.0
                )
            else:
                spectral_kurtosis = 0.0

            # Spectral rolloff (95th percentile frequency)
            cumulative_power = np.cumsum(normalized_magnitudes)
            rolloff_index = np.where(cumulative_power >= 0.95)[0]
            spectral_rolloff = (
                frequencies[rolloff_index[0]]
                if len(rolloff_index) > 0
                else frequencies[-1]
            )

            # Spectral flux (measure of changes in spectrum)
            spectral_flux = np.sum(np.diff(magnitudes) ** 2)

            return {
                "centroid": spectral_centroid,
                "spread": spectral_spread,
                "skewness": spectral_skewness,
                "kurtosis": spectral_kurtosis,
                "rolloff": spectral_rolloff,
                "flux": spectral_flux,
                "total_power": total_power,
            }

        except Exception as e:
            logger.warning(f"Spectral features computation failed: {str(e)}")
            return self._empty_spectral_features()

    def _empty_spectral_features(self) -> Dict[str, float]:
        """Return empty spectral features dict"""
        return {
            "centroid": 0.0,
            "spread": 0.0,
            "skewness": 0.0,
            "kurtosis": 0.0,
            "rolloff": 0.0,
            "flux": 0.0,
            "total_power": 0.0,
        }

    def compare_spectrograms(
        self, spec1: np.ndarray, spec2: np.ndarray
    ) -> Dict[str, float]:
        """
        Compare two spectrograms

        Args:
            spec1: First spectrogram
            spec2: Second spectrogram

        Returns:
            Similarity metrics
        """
        try:
            # Ensure same dimensions
            min_freq = min(spec1.shape[0], spec2.shape[0])
            min_time = min(spec1.shape[1], spec2.shape[1])

            spec1_resized = spec1[:min_freq, :min_time]
            spec2_resized = spec2[:min_freq, :min_time]

            # Normalize spectrograms
            spec1_norm = spec1_resized / (np.max(spec1_resized) + 1e-10)
            spec2_norm = spec2_resized / (np.max(spec2_resized) + 1e-10)

            # Correlation coefficient
            correlation = np.corrcoef(spec1_norm.flatten(), spec2_norm.flatten())[0, 1]
            if np.isnan(correlation):
                correlation = 0.0

            # Mean squared error
            mse = np.mean((spec1_norm - spec2_norm) ** 2)

            # Structural similarity (simplified)
            mean1 = np.mean(spec1_norm)
            mean2 = np.mean(spec2_norm)
            var1 = np.var(spec1_norm)
            var2 = np.var(spec2_norm)
            cov = np.mean((spec1_norm - mean1) * (spec2_norm - mean2))

            c1 = (0.01) ** 2
            c2 = (0.03) ** 2

            ssim = ((2 * mean1 * mean2 + c1) * (2 * cov + c2)) / (
                (mean1**2 + mean2**2 + c1) * (var1 + var2 + c2)
            )

            return {
                "correlation": correlation,
                "mse": mse,
                "ssim": ssim,
                "similarity_score": max(0.0, (correlation + ssim) / 2.0),
            }

        except Exception as e:
            logger.warning(f"Spectrogram comparison failed: {str(e)}")
            return {
                "correlation": 0.0,
                "mse": 1.0,
                "ssim": 0.0,
                "similarity_score": 0.0,
            }
