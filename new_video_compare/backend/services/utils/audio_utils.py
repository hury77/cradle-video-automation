"""
Audio Processing Utilities
Handles audio extraction, analysis, and basic processing
"""

import subprocess
import numpy as np
import json
import os
import tempfile
from typing import Tuple, Dict, List, Optional, Any
import logging
from ..exceptions import VideoProcessingError

logger = logging.getLogger(__name__)


class AudioProcessor:
    """
    Audio processing utilities using FFmpeg and numpy
    """

    def __init__(self):
        """
        Initialize audio processor
        """
        # FFmpeg commands are executed directly via subprocess
        pass

    def extract_audio(
        self,
        video_path: str,
        output_path: Optional[str] = None,
        sample_rate: int = 44100,
        channels: int = 2,
    ) -> str:
        """
        Extract audio from video file

        Args:
            video_path: Path to input video file
            output_path: Optional output audio file path
            sample_rate: Audio sample rate (Hz)
            channels: Number of audio channels

        Returns:
            Path to extracted audio file

        Raises:
            VideoProcessingError: If audio extraction fails
        """
        try:
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Video file not found: {video_path}")

            # Generate output path if not provided
            if output_path is None:
                base_name = os.path.splitext(os.path.basename(video_path))[0]
                output_path = os.path.join(
                    tempfile.gettempdir(), f"{base_name}_audio.wav"
                )

            # FFmpeg command for audio extraction
            cmd = [
                "ffmpeg",
                "-nostdin",
                "-y",  # Overwrite output
                "-i",
                video_path,
                "-vn",  # No video
                "-ar",
                str(sample_rate),  # Sample rate
                "-ac",
                str(channels),  # Channels
                "-acodec",
                "pcm_s16le",  # PCM 16-bit little-endian
                output_path,
            ]

            # Execute FFmpeg command
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                raise subprocess.CalledProcessError(
                    result.returncode, cmd, result.stderr
                )

            if not os.path.exists(output_path):
                raise FileNotFoundError(
                    f"Audio extraction failed - output not created: {output_path}"
                )

            logger.info(f"Audio extracted successfully: {output_path}")
            return output_path

        except subprocess.TimeoutExpired:
            raise VideoProcessingError("Audio extraction timed out after 5 minutes")
        except subprocess.CalledProcessError as e:
            raise VideoProcessingError(f"FFmpeg audio extraction failed: {e.stderr}")
        except Exception as e:
            raise VideoProcessingError(f"Audio extraction failed: {str(e)}")

    def load_audio_data(self, audio_path: str) -> Tuple[np.ndarray, int]:
        """
        Load audio data as numpy array

        Args:
            audio_path: Path to audio file

        Returns:
            Tuple of (audio_data, sample_rate)

        Raises:
            VideoProcessingError: If loading fails
        """
        try:
            # Use FFmpeg to convert audio to raw PCM data
            cmd = [
                "ffmpeg",
                "-nostdin",
                "-y",
                "-i",
                audio_path,
                "-f",
                "s16le",  # 16-bit signed little-endian
                "-acodec",
                "pcm_s16le",
                "-ar",
                "44100",  # Standard sample rate
                "-ac",
                "2",  # Stereo
                "pipe:1",  # Output to stdout
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=60)

            if result.returncode != 0:
                raise subprocess.CalledProcessError(
                    result.returncode, cmd, result.stderr
                )

            # Convert bytes to numpy array
            audio_data = np.frombuffer(result.stdout, dtype=np.int16)

            # Reshape to stereo (2 channels) if data length allows
            if len(audio_data) % 2 == 0:
                audio_data = audio_data.reshape(-1, 2)

            sample_rate = 44100  # We forced this in FFmpeg command

            logger.info(
                f"Audio data loaded: shape={audio_data.shape}, sr={sample_rate}"
            )
            return audio_data, sample_rate

        except subprocess.TimeoutExpired:
            raise VideoProcessingError("Audio loading timed out")
        except subprocess.CalledProcessError as e:
            raise VideoProcessingError(f"Audio loading failed: {e.stderr}")
        except Exception as e:
            raise VideoProcessingError(f"Audio data loading failed: {str(e)}")

    def get_audio_info(self, audio_path: str) -> Dict[str, Any]:
        """
        Get detailed audio file information

        Args:
            audio_path: Path to audio file

        Returns:
            Dictionary with audio information

        Raises:
            VideoProcessingError: If info extraction fails
        """
        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                audio_path,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                raise subprocess.CalledProcessError(
                    result.returncode, cmd, result.stderr
                )

            info = json.loads(result.stdout)

            # Find audio stream
            audio_stream = None
            for stream in info.get("streams", []):
                if stream.get("codec_type") == "audio":
                    audio_stream = stream
                    break

            if not audio_stream:
                raise ValueError("No audio stream found in file")

            # Extract relevant information
            audio_info = {
                "duration": float(info.get("format", {}).get("duration", 0)),
                "bit_rate": int(info.get("format", {}).get("bit_rate", 0)),
                "size": int(info.get("format", {}).get("size", 0)),
                "format_name": info.get("format", {}).get("format_name", ""),
                "sample_rate": int(audio_stream.get("sample_rate", 0)),
                "channels": int(audio_stream.get("channels", 0)),
                "channel_layout": audio_stream.get("channel_layout", ""),
                "codec_name": audio_stream.get("codec_name", ""),
                "codec_long_name": audio_stream.get("codec_long_name", ""),
                "bits_per_sample": int(audio_stream.get("bits_per_sample", 0)),
            }

            return audio_info

        except subprocess.TimeoutExpired:
            raise VideoProcessingError("Audio info extraction timed out")
        except subprocess.CalledProcessError as e:
            raise VideoProcessingError(f"Audio info extraction failed: {e.stderr}")
        except json.JSONDecodeError as e:
            raise VideoProcessingError(f"Failed to parse audio info JSON: {str(e)}")
        except Exception as e:
            raise VideoProcessingError(f"Audio info extraction failed: {str(e)}")

    def normalize_loudness(
        self, audio_data: np.ndarray, target_lufs: float = -23.0
    ) -> np.ndarray:
        """
        Normalize audio loudness to target LUFS

        Args:
            audio_data: Input audio data
            target_lufs: Target loudness in LUFS

        Returns:
            Normalized audio data
        """
        try:
            # Simple RMS-based normalization (approximation of LUFS)
            if len(audio_data.shape) == 2:
                # Stereo - use both channels
                rms = np.sqrt(np.mean(audio_data.astype(np.float64) ** 2))
            else:
                # Mono
                rms = np.sqrt(np.mean(audio_data.astype(np.float64) ** 2))

            if rms == 0:
                return audio_data

            # Convert target LUFS to linear scale (approximation)
            # LUFS ≈ 20 * log10(RMS) for digital audio
            target_rms = 10 ** (target_lufs / 20.0) * 32767  # Scale for 16-bit

            # Calculate gain factor
            gain = target_rms / rms

            # Apply gain with clipping protection
            normalized = audio_data.astype(np.float64) * gain
            normalized = np.clip(normalized, -32767, 32767)

            return normalized.astype(np.int16)

        except Exception as e:
            logger.warning(f"Loudness normalization failed: {str(e)}")
            return audio_data

    def calculate_rms(
        self, audio_data: np.ndarray, window_size: int = 1024
    ) -> np.ndarray:
        """
        Calculate RMS (Root Mean Square) values for audio analysis

        Args:
            audio_data: Input audio data
            window_size: Size of analysis window

        Returns:
            RMS values array
        """
        try:
            # Convert to mono if stereo
            if len(audio_data.shape) == 2:
                mono = np.mean(audio_data.astype(np.float64), axis=1)
            else:
                mono = audio_data.astype(np.float64)

            # Calculate RMS for each window
            rms_values = []
            for i in range(0, len(mono) - window_size + 1, window_size):
                window = mono[i : i + window_size]
                rms = np.sqrt(np.mean(window**2))
                rms_values.append(rms)

            return np.array(rms_values)

        except Exception as e:
            raise VideoProcessingError(f"RMS calculation failed: {str(e)}")

    def generate_waveform_data(
        self, audio_data: np.ndarray, target_points: int = 1000
    ) -> Dict[str, np.ndarray]:
        """
        Generate waveform data for visualization

        Args:
            audio_data: Input audio data
            target_points: Number of points for waveform visualization

        Returns:
            Dictionary with waveform data
        """
        try:
            # Convert to mono if stereo
            if len(audio_data.shape) == 2:
                mono = np.mean(audio_data.astype(np.float64), axis=1)
                left = audio_data[:, 0].astype(np.float64)
                right = audio_data[:, 1].astype(np.float64)
            else:
                mono = audio_data.astype(np.float64)
                left = mono
                right = mono

            # Downsample for visualization
            if len(mono) > target_points:
                step = len(mono) // target_points
                mono_viz = mono[::step][:target_points]
                left_viz = left[::step][:target_points]
                right_viz = right[::step][:target_points]
            else:
                mono_viz = mono
                left_viz = left
                right_viz = right

            # Normalize to -1 to 1 range
            mono_viz = mono_viz / 32767.0
            left_viz = left_viz / 32767.0
            right_viz = right_viz / 32767.0

            return {
                "mono": mono_viz,
                "left": left_viz,
                "right": right_viz,
                "sample_count": len(mono),
                "visualization_points": len(mono_viz),
            }

        except Exception as e:
            raise VideoProcessingError(f"Waveform generation failed: {str(e)}")
