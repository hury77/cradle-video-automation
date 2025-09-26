"""
Audio Processor - Main Audio Processing Orchestrator
Coordinates all audio processing operations for video comparison
"""

import os
import tempfile
import numpy as np
from typing import Tuple, Dict, List, Optional, Any, Union
import logging
from .utils.audio_utils import AudioProcessor as AudioUtils
from .utils.spectral_analysis import SpectralAnalyzer
from .algorithms.audio_comparison import AudioComparator
from .exceptions import VideoProcessingError

logger = logging.getLogger(__name__)


class AudioProcessor:
    """
    Main audio processing orchestrator
    Handles complete audio processing workflow for video comparison
    """

    def __init__(
        self,
        sample_rate: int = 44100,
        normalize_loudness: bool = True,
        target_lufs: float = -23.0,
        temp_dir: Optional[str] = None,
    ):
        """
        Initialize audio processor

        Args:
            sample_rate: Target sample rate for audio processing
            normalize_loudness: Whether to normalize audio loudness
            target_lufs: Target loudness level in LUFS
            temp_dir: Temporary directory for audio files
        """
        self.sample_rate = sample_rate
        self.normalize_loudness = normalize_loudness
        self.target_lufs = target_lufs
        self.temp_dir = temp_dir or tempfile.gettempdir()

        # Initialize components
        self.audio_utils = AudioUtils()
        self.spectral_analyzer = SpectralAnalyzer(sample_rate)
        self.audio_comparator = AudioComparator(sample_rate)

        # Processing statistics
        self.stats = {
            "files_processed": 0,
            "comparisons_made": 0,
            "errors_encountered": 0,
            "total_processing_time": 0.0,
        }

        logger.info(
            f"AudioProcessor initialized: sr={sample_rate}, normalize={normalize_loudness}"
        )

    def extract_and_load_audio(
        self, video_path: str, output_path: Optional[str] = None
    ) -> Tuple[np.ndarray, str]:
        """
        Extract and load audio from video file

        Args:
            video_path: Path to video file
            output_path: Optional output audio file path

        Returns:
            Tuple of (audio_data, audio_file_path)

        Raises:
            VideoProcessingError: If extraction or loading fails
        """
        try:
            logger.info(f"Extracting audio from: {video_path}")

            # Extract audio
            audio_path = self.audio_utils.extract_audio(
                video_path, output_path, sample_rate=self.sample_rate, channels=2
            )

            # Load audio data
            audio_data, loaded_sample_rate = self.audio_utils.load_audio_data(
                audio_path
            )

            # Verify sample rate
            if loaded_sample_rate != self.sample_rate:
                logger.warning(
                    f"Sample rate mismatch: expected {self.sample_rate}, got {loaded_sample_rate}"
                )

            # Normalize loudness if enabled
            if self.normalize_loudness:
                audio_data = self.audio_utils.normalize_loudness(
                    audio_data, self.target_lufs
                )
                logger.debug(f"Audio normalized to {self.target_lufs} LUFS")

            self.stats["files_processed"] += 1
            logger.info(f"Audio extracted and loaded: shape={audio_data.shape}")

            return audio_data, audio_path

        except Exception as e:
            self.stats["errors_encountered"] += 1
            raise VideoProcessingError(f"Audio extraction and loading failed: {str(e)}")

    def analyze_audio(
        self,
        audio_data: np.ndarray,
        include_mfcc: bool = True,
        include_spectrogram: bool = True,
    ) -> Dict[str, Any]:
        """
        Comprehensive audio analysis

        Args:
            audio_data: Input audio data
            include_mfcc: Whether to compute MFCC features
            include_spectrogram: Whether to compute spectrogram

        Returns:
            Dictionary with analysis results
        """
        try:
            logger.debug("Starting comprehensive audio analysis")
            analysis_results = {}

            # Basic audio properties
            if len(audio_data.shape) == 2:
                channels, samples = audio_data.shape[1], audio_data.shape[0]
            else:
                channels, samples = 1, len(audio_data)

            duration = samples / self.sample_rate

            analysis_results["basic_properties"] = {
                "channels": channels,
                "samples": samples,
                "duration_seconds": duration,
                "sample_rate": self.sample_rate,
            }

            # RMS analysis
            try:
                rms_values = self.audio_utils.calculate_rms(audio_data)
                analysis_results["rms_analysis"] = {
                    "mean_rms": np.mean(rms_values),
                    "max_rms": np.max(rms_values),
                    "std_rms": np.std(rms_values),
                    "rms_values": rms_values.tolist(),
                }
            except Exception as e:
                logger.warning(f"RMS analysis failed: {str(e)}")
                analysis_results["rms_analysis"] = {"error": str(e)}

            # Waveform data for visualization
            try:
                waveform_data = self.audio_utils.generate_waveform_data(audio_data)
                analysis_results["waveform"] = waveform_data
            except Exception as e:
                logger.warning(f"Waveform generation failed: {str(e)}")
                analysis_results["waveform"] = {"error": str(e)}

            # FFT analysis
            try:
                frequencies, magnitudes = self.spectral_analyzer.compute_fft(audio_data)

                # Find spectral peaks
                peak_freqs, peak_info = self.spectral_analyzer.find_spectral_peaks(
                    frequencies, magnitudes, height=np.max(magnitudes) * 0.1
                )

                # Compute spectral features
                spectral_features = self.spectral_analyzer.compute_spectral_features(
                    frequencies, magnitudes
                )

                analysis_results["spectral_analysis"] = {
                    "spectral_features": spectral_features,
                    "dominant_frequencies": peak_freqs[:10].tolist(),  # Top 10 peaks
                    "peak_info": {
                        "count": peak_info["count"],
                        "frequencies": peak_freqs.tolist(),
                        "magnitudes": peak_info["magnitudes"].tolist(),
                    },
                }

            except Exception as e:
                logger.warning(f"Spectral analysis failed: {str(e)}")
                analysis_results["spectral_analysis"] = {"error": str(e)}

            # MFCC analysis
            if include_mfcc:
                try:
                    mfcc_features = self.spectral_analyzer.compute_mfcc(audio_data)

                    analysis_results["mfcc_analysis"] = {
                        "mfcc_features": mfcc_features.tolist(),
                        "mfcc_shape": mfcc_features.shape,
                        "mfcc_stats": {
                            "mean": np.mean(mfcc_features, axis=1).tolist(),
                            "std": np.std(mfcc_features, axis=1).tolist(),
                            "var": np.var(mfcc_features, axis=1).tolist(),
                        },
                    }

                except Exception as e:
                    logger.warning(f"MFCC analysis failed: {str(e)}")
                    analysis_results["mfcc_analysis"] = {"error": str(e)}

            # Spectrogram analysis
            if include_spectrogram:
                try:
                    freq_spec, time_spec, spectrogram = (
                        self.spectral_analyzer.compute_spectrogram(audio_data)
                    )

                    analysis_results["spectrogram_analysis"] = {
                        "shape": spectrogram.shape,
                        "frequency_range": [freq_spec[0], freq_spec[-1]],
                        "time_range": [time_spec[0], time_spec[-1]],
                        "max_magnitude": np.max(spectrogram),
                        "mean_magnitude": np.mean(spectrogram),
                    }

                    # Store spectrogram data (limited size for API)
                    if spectrogram.size < 100000:  # Only store if reasonable size
                        analysis_results["spectrogram_analysis"]["data"] = {
                            "frequencies": freq_spec.tolist(),
                            "times": time_spec.tolist(),
                            "spectrogram": spectrogram.tolist(),
                        }

                except Exception as e:
                    logger.warning(f"Spectrogram analysis failed: {str(e)}")
                    analysis_results["spectrogram_analysis"] = {"error": str(e)}

            logger.debug("Audio analysis completed successfully")
            return analysis_results

        except Exception as e:
            raise VideoProcessingError(f"Audio analysis failed: {str(e)}")

    def compare_audio_files(
        self,
        video_path1: str,
        video_path2: str,
        sync_audio: bool = True,
        comparison_weights: Optional[Dict[str, float]] = None,
        keep_temp_files: bool = False,
    ) -> Dict[str, Any]:
        """
        Compare audio from two video files

        Args:
            video_path1: Path to first video file
            video_path2: Path to second video file
            sync_audio: Whether to synchronize audio before comparison
            comparison_weights: Optional weights for comparison algorithms
            keep_temp_files: Whether to keep temporary audio files

        Returns:
            Dictionary with comparison results
        """
        try:
            logger.info(
                f"Comparing audio: {os.path.basename(video_path1)} vs {os.path.basename(video_path2)}"
            )

            temp_files = []

            try:
                # Extract and load first audio
                audio_data1, audio_path1 = self.extract_and_load_audio(video_path1)
                temp_files.append(audio_path1)

                # Extract and load second audio
                audio_data2, audio_path2 = self.extract_and_load_audio(video_path2)
                temp_files.append(audio_path2)

                # Get audio info
                audio_info1 = self.audio_utils.get_audio_info(audio_path1)
                audio_info2 = self.audio_utils.get_audio_info(audio_path2)

                # Perform comprehensive comparison
                similarity_score, comparison_metadata = (
                    self.audio_comparator.comprehensive_comparison(
                        audio_data1,
                        audio_data2,
                        sync_audio=sync_audio,
                        weights=comparison_weights,
                    )
                )

                # Analyze both audio tracks
                analysis1 = self.analyze_audio(
                    audio_data1, include_mfcc=False, include_spectrogram=False
                )
                analysis2 = self.analyze_audio(
                    audio_data2, include_mfcc=False, include_spectrogram=False
                )

                # Compile results
                comparison_results = {
                    "similarity_score": similarity_score,
                    "comparison_metadata": comparison_metadata,
                    "audio_info": {"file1": audio_info1, "file2": audio_info2},
                    "audio_analysis": {"file1": analysis1, "file2": analysis2},
                    "processing_info": {
                        "sample_rate": self.sample_rate,
                        "normalization_applied": self.normalize_loudness,
                        "target_lufs": self.target_lufs,
                        "sync_applied": sync_audio,
                    },
                }

                self.stats["comparisons_made"] += 1
                logger.info(
                    f"Audio comparison completed: similarity = {similarity_score:.3f}"
                )

                return comparison_results

            finally:
                # Clean up temporary files
                if not keep_temp_files:
                    for temp_file in temp_files:
                        try:
                            if os.path.exists(temp_file):
                                os.remove(temp_file)
                                logger.debug(f"Removed temp file: {temp_file}")
                        except Exception as e:
                            logger.warning(
                                f"Failed to remove temp file {temp_file}: {str(e)}"
                            )

        except Exception as e:
            self.stats["errors_encountered"] += 1
            raise VideoProcessingError(f"Audio comparison failed: {str(e)}")

    def batch_compare_audio(
        self,
        video_pairs: List[Tuple[str, str]],
        sync_audio: bool = True,
        comparison_weights: Optional[Dict[str, float]] = None,
        parallel: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Compare multiple pairs of audio files

        Args:
            video_pairs: List of (video_path1, video_path2) tuples
            sync_audio: Whether to synchronize audio before comparison
            comparison_weights: Optional weights for comparison algorithms
            parallel: Whether to process in parallel (future implementation)

        Returns:
            List of comparison results
        """
        try:
            logger.info(f"Starting batch audio comparison: {len(video_pairs)} pairs")

            results = []

            for i, (video_path1, video_path2) in enumerate(video_pairs):
                try:
                    logger.info(f"Processing pair {i+1}/{len(video_pairs)}")

                    comparison_result = self.compare_audio_files(
                        video_path1,
                        video_path2,
                        sync_audio=sync_audio,
                        comparison_weights=comparison_weights,
                    )

                    # Add batch metadata
                    comparison_result["batch_info"] = {
                        "pair_index": i,
                        "total_pairs": len(video_pairs),
                        "video_paths": [video_path1, video_path2],
                    }

                    results.append(comparison_result)

                except Exception as e:
                    logger.error(f"Failed to process pair {i+1}: {str(e)}")
                    error_result = {
                        "similarity_score": 0.0,
                        "error": str(e),
                        "batch_info": {
                            "pair_index": i,
                            "total_pairs": len(video_pairs),
                            "video_paths": [video_path1, video_path2],
                        },
                    }
                    results.append(error_result)
                    self.stats["errors_encountered"] += 1

            logger.info(f"Batch audio comparison completed: {len(results)} results")
            return results

        except Exception as e:
            raise VideoProcessingError(f"Batch audio comparison failed: {str(e)}")

    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get processing statistics

        Returns:
            Dictionary with processing statistics
        """
        return {
            "files_processed": self.stats["files_processed"],
            "comparisons_made": self.stats["comparisons_made"],
            "errors_encountered": self.stats["errors_encountered"],
            "error_rate": (
                self.stats["errors_encountered"] / max(1, self.stats["files_processed"])
            )
            * 100,
            "success_rate": (
                (self.stats["files_processed"] - self.stats["errors_encountered"])
                / max(1, self.stats["files_processed"])
            )
            * 100,
            "configuration": {
                "sample_rate": self.sample_rate,
                "normalize_loudness": self.normalize_loudness,
                "target_lufs": self.target_lufs,
                "temp_dir": self.temp_dir,
            },
        }

    def reset_stats(self) -> None:
        """Reset processing statistics"""
        self.stats = {
            "files_processed": 0,
            "comparisons_made": 0,
            "errors_encountered": 0,
            "total_processing_time": 0.0,
        }
        logger.info("Processing statistics reset")

    def cleanup_temp_files(self) -> int:
        """
        Clean up temporary audio files

        Returns:
            Number of files cleaned up
        """
        try:
            cleaned_count = 0

            # Look for audio files in temp directory
            for filename in os.listdir(self.temp_dir):
                if filename.endswith(("_audio.wav", "_audio.mp3", "_temp_audio.wav")):
                    filepath = os.path.join(self.temp_dir, filename)
                    try:
                        os.remove(filepath)
                        cleaned_count += 1
                        logger.debug(f"Cleaned temp audio file: {filename}")
                    except Exception as e:
                        logger.warning(f"Failed to clean {filename}: {str(e)}")

            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} temporary audio files")

            return cleaned_count

        except Exception as e:
            logger.warning(f"Temp file cleanup failed: {str(e)}")
            return 0

    def validate_audio_file(self, video_path: str) -> Dict[str, Any]:
        """
        Validate if video file has processable audio

        Args:
            video_path: Path to video file

        Returns:
            Dictionary with validation results
        """
        try:
            logger.debug(f"Validating audio in: {video_path}")

            # Try to extract basic audio info without full extraction
            temp_audio = None

            try:
                # Extract a small sample (first 5 seconds)
                temp_audio = self.audio_utils.extract_audio(
                    video_path,
                    output_path=os.path.join(
                        self.temp_dir, f"validation_{os.getpid()}.wav"
                    ),
                )

                # Get audio info
                audio_info = self.audio_utils.get_audio_info(temp_audio)

                # Load a small sample
                audio_data, sample_rate = self.audio_utils.load_audio_data(temp_audio)

                validation_result = {
                    "valid": True,
                    "has_audio": True,
                    "audio_info": audio_info,
                    "sample_data_shape": audio_data.shape,
                    "sample_rate": sample_rate,
                    "duration": audio_info.get("duration", 0),
                    "channels": audio_info.get("channels", 0),
                    "codec": audio_info.get("codec_name", "unknown"),
                }

                logger.debug(
                    f"Audio validation successful: {audio_info.get('duration', 0):.2f}s"
                )

            except Exception as e:
                validation_result = {
                    "valid": False,
                    "has_audio": False,
                    "error": str(e),
                    "audio_info": {},
                    "sample_data_shape": None,
                }

                logger.warning(f"Audio validation failed: {str(e)}")

            finally:
                # Clean up temp file
                if temp_audio and os.path.exists(temp_audio):
                    try:
                        os.remove(temp_audio)
                    except Exception:
                        pass

            return validation_result

        except Exception as e:
            return {
                "valid": False,
                "has_audio": False,
                "error": f"Validation error: {str(e)}",
                "audio_info": {},
                "sample_data_shape": None,
            }
