"""
Audio Service for Audio Comparison
Provides loudness measurement (LUFS), source separation, and voiceover comparison
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

# Lazy load expensive libraries
_pyloudnorm = None
_librosa = None
_soundfile = None
_whisper = None
_mlx_whisper = None


def get_pyloudnorm():
    """Lazy load pyloudnorm"""
    global _pyloudnorm
    if _pyloudnorm is None:
        import pyloudnorm as pyln
        _pyloudnorm = pyln
        logger.info("✅ pyloudnorm loaded")
    return _pyloudnorm


def get_librosa():
    """Lazy load librosa"""
    global _librosa
    if _librosa is None:
        import librosa
        _librosa = librosa
        logger.info("✅ librosa loaded")
    return _librosa


def get_soundfile():
    """Lazy load soundfile"""
    global _soundfile
    if _soundfile is None:
        import soundfile as sf
        _soundfile = sf
        logger.info("✅ soundfile loaded")
    return _soundfile
def get_mlx_whisper():
    """Lazy load mlx_whisper"""
    global _mlx_whisper
    if _mlx_whisper is None:
        import mlx_whisper
        _mlx_whisper = mlx_whisper
        logger.info("✅ mlx_whisper loaded")
    return _mlx_whisper


def extract_audio_from_video(
    video_path: str,
    output_path: Optional[str] = None,
    sample_rate: int = 44100  # Default to 44.1kHz for AI compatibility (Demucs/Whisper)
) -> str:
    """
    Extract audio track from video file using FFmpeg
    
    Args:
        video_path: Path to video file
        output_path: Optional path for output WAV file
        sample_rate: Target sample rate (default 48kHz for broadcast)
    
    Returns:
        Path to extracted WAV file
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    
    # Generate output path if not provided
    if output_path is None:
        output_path = str(video_path.with_suffix('.wav'))
    
    logger.info(f"🎵 Extracting audio from: {video_path.name}")
    
    # FFmpeg command to extract audio - use hardware decoder if available
    cmd = [
        'ffmpeg',
        '-hwaccel', 'auto',  # Auto hardware acceleration
        '-nostdin',
        '-y',
        '-i', str(video_path),
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', str(sample_rate),
        '-ac', '2',
        output_path
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            raise RuntimeError(f"FFmpeg failed: {result.stderr[:500]}")
        
        logger.info(f"✅ Audio extracted to: {output_path}")
        return output_path
        
    except subprocess.TimeoutExpired:
        raise RuntimeError("FFmpeg timeout - audio extraction took too long")


def measure_loudness(audio_path: str) -> Dict[str, Any]:
    """
    Measure loudness of audio file according to ITU-R BS.1770-4
    
    Args:
        audio_path: Path to audio file (WAV preferred)
    
    Returns:
        Dict with loudness metrics:
        - integrated_lufs: Overall loudness
        - true_peak_db: Maximum sample value
        - loudness_range: Dynamic range (LRA)
    """
    sf = get_soundfile()
    pyln = get_pyloudnorm()
    
    logger.info(f"📊 Measuring loudness: {Path(audio_path).name}")
    
    # Load audio
    data, rate = sf.read(audio_path)
    
    # Convert to mono if needed for some measurements
    if len(data.shape) > 1:
        data_mono = np.mean(data, axis=1)
    else:
        data_mono = data
    
    # Create loudness meter (ITU-R BS.1770-4)
    meter = pyln.Meter(rate)
    
    # Integrated loudness (overall)
    integrated_lufs = meter.integrated_loudness(data)
    
    # True peak (maximum sample value in dB)
    if len(data.shape) > 1:
        true_peak = np.max(np.abs(data))
    else:
        true_peak = np.max(np.abs(data_mono))
    true_peak_db = 20 * np.log10(true_peak + 1e-10)  # Convert to dB
    
    # Loudness Range (LRA) - requires longer audio
    # For short clips, we approximate with integrated loudness difference
    duration = len(data_mono) / rate
    
    result = {
        "integrated_lufs": round(float(integrated_lufs), 2),
        "true_peak_db": round(float(true_peak_db), 2),
        "duration_seconds": round(duration, 2),
        "sample_rate": rate,
    }
    
    # Try to compute short-term loudness for LRA
    try:
        # Window-based loudness for LRA approximation
        window_size = int(rate * 0.4)  # 400ms windows
        hop_size = int(rate * 0.1)  # 100ms hop
        
        short_term_loudness = []
        for i in range(0, len(data_mono) - window_size, hop_size):
            window = data_mono[i:i + window_size]
            try:
                window_data = np.column_stack([window, window]) if len(data.shape) > 1 else window.reshape(-1, 1)
                window_data = np.column_stack([window, window])  # Make stereo
                st_lufs = meter.integrated_loudness(window_data)
                if not np.isinf(st_lufs) and not np.isnan(st_lufs):
                    short_term_loudness.append(st_lufs)
            except:
                pass
        
        if short_term_loudness:
            # LRA is roughly the difference between 95th and 10th percentile
            sorted_lufs = sorted(short_term_loudness)
            idx_low = int(len(sorted_lufs) * 0.1)
            idx_high = int(len(sorted_lufs) * 0.95)
            lra = sorted_lufs[idx_high] - sorted_lufs[idx_low]
            result["loudness_range_lu"] = round(float(lra), 2)
    except Exception as e:
        logger.warning(f"Could not compute LRA: {e}")
    
    logger.info(f"✅ Loudness: {integrated_lufs:.1f} LUFS, Peak: {true_peak_db:.1f} dB")
    
    return result


def compare_loudness(
    acceptance_path: str,
    emission_path: str
) -> Dict[str, Any]:
    """
    Compare loudness between acceptance and emission audio
    
    Args:
        acceptance_path: Path to acceptance video/audio
        emission_path: Path to emission video/audio
    
    Returns:
        Comparison results with metrics for both files
    """
    logger.info("🔊 Starting loudness comparison...")
    
    # Extract audio if video files provided
    temp_files = []
    
    try:
        # Check if input is video or audio
        acceptance_ext = Path(acceptance_path).suffix.lower()
        emission_ext = Path(emission_path).suffix.lower()
        
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
        
        # Extract audio from acceptance if video
        if acceptance_ext in video_extensions:
            acceptance_audio = tempfile.mktemp(suffix='_acceptance.wav')
            temp_files.append(acceptance_audio)
            extract_audio_from_video(acceptance_path, acceptance_audio)
        else:
            acceptance_audio = acceptance_path
        
        # Extract audio from emission if video
        if emission_ext in video_extensions:
            emission_audio = tempfile.mktemp(suffix='_emission.wav')
            temp_files.append(emission_audio)
            extract_audio_from_video(emission_path, emission_audio)
        else:
            emission_audio = emission_path
        
        # Measure loudness for both
        acceptance_loudness = measure_loudness(acceptance_audio)
        emission_loudness = measure_loudness(emission_audio)
        
        # Calculate differences
        lufs_diff = emission_loudness["integrated_lufs"] - acceptance_loudness["integrated_lufs"]
        peak_diff = emission_loudness["true_peak_db"] - acceptance_loudness["true_peak_db"]
        
        # Determine if within broadcast tolerances
        # EBU R128: Target -23 LUFS ±1 LU
        # US: -24 LUFS ±2 LU
        lufs_tolerance = 1.0  # ±1 LU tolerance
        is_lufs_match = abs(lufs_diff) <= lufs_tolerance
        
        peak_tolerance = 1.0  # ±1 dB tolerance
        is_peak_match = abs(peak_diff) <= peak_tolerance
        
        result = {
            "acceptance": acceptance_loudness,
            "emission": emission_loudness,
            "comparison": {
                "lufs_difference": round(lufs_diff, 2),
                "peak_difference_db": round(peak_diff, 2),
                "is_lufs_match": is_lufs_match,
                "is_peak_match": is_peak_match,
                "loudness_tolerance": lufs_tolerance,
            },
            "has_loudness_differences": not (is_lufs_match and is_peak_match),
        }
        
        if is_lufs_match and is_peak_match:
            logger.info("✅ Loudness levels match within tolerance")
        else:
            logger.warning(f"⚠️ Loudness difference: {lufs_diff:+.1f} LU, Peak diff: {peak_diff:+.1f} dB")
        
        return result
        
    finally:
        # Cleanup temp files
        import os
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass


def compare_audio_similarity(
    acceptance_path: str,
    emission_path: str
) -> Dict[str, Any]:
    """
    Compare overall audio similarity using MFCC features
    
    This provides a general audio similarity score without
    source separation - useful for quick comparison.
    """
    librosa = get_librosa()
    sf = get_soundfile()
    
    logger.info("🎼 Computing audio similarity...")
    
    temp_files = []
    
    try:
        # Extract audio if needed
        acceptance_ext = Path(acceptance_path).suffix.lower()
        emission_ext = Path(emission_path).suffix.lower()
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
        
        if acceptance_ext in video_extensions:
            acceptance_audio = tempfile.mktemp(suffix='_acceptance.wav')
            temp_files.append(acceptance_audio)
            extract_audio_from_video(acceptance_path, acceptance_audio)
        else:
            acceptance_audio = acceptance_path
            
        if emission_ext in video_extensions:
            emission_audio = tempfile.mktemp(suffix='_emission.wav')
            temp_files.append(emission_audio)
            extract_audio_from_video(emission_path, emission_audio)
        else:
            emission_audio = emission_path
        
        # Load audio files
        y_acc, sr_acc = librosa.load(acceptance_audio, sr=22050, mono=True)
        y_emi, sr_emi = librosa.load(emission_audio, sr=22050, mono=True)
        
        # Extract MFCC features
        mfcc_acc = librosa.feature.mfcc(y=y_acc, sr=sr_acc, n_mfcc=13)
        mfcc_emi = librosa.feature.mfcc(y=y_emi, sr=sr_emi, n_mfcc=13)
        
        # Normalize to same length (use shorter)
        min_frames = min(mfcc_acc.shape[1], mfcc_emi.shape[1])
        mfcc_acc = mfcc_acc[:, :min_frames]
        mfcc_emi = mfcc_emi[:, :min_frames]
        
        # Compute cosine similarity per frame
        from numpy.linalg import norm
        
        similarities = []
        for i in range(min_frames):
            a = mfcc_acc[:, i]
            b = mfcc_emi[:, i]
            sim = np.dot(a, b) / (norm(a) * norm(b) + 1e-10)
            similarities.append(sim)
        
        overall_similarity = float(np.mean(similarities))
        
        # Also compute spectral similarity
        spec_acc = np.abs(librosa.stft(y_acc))
        spec_emi = np.abs(librosa.stft(y_emi))
        
        # Normalize to same size
        min_t = min(spec_acc.shape[1], spec_emi.shape[1])
        spec_acc = spec_acc[:, :min_t]
        spec_emi = spec_emi[:, :min_t]
        
        # Spectral correlation
        spectral_corr = float(np.corrcoef(spec_acc.flatten(), spec_emi.flatten())[0, 1])
        
        result = {
            "mfcc_similarity": round(overall_similarity, 4),
            "spectral_similarity": round(spectral_corr, 4),
            "overall_audio_similarity": round((overall_similarity + spectral_corr) / 2, 4),
            "frames_compared": min_frames,
        }
        
        logger.info(f"✅ Audio similarity: {result['overall_audio_similarity']:.1%}")
        
        return result
        
    finally:
        # Cleanup
        import os
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass


# ==============================================================================
# Phase 2: Source Separation (Demucs)
# ==============================================================================

def separate_sources(
    audio_path: str,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Separate audio into vocals, drums, bass, and other using Demucs CLI
    
    Args:
        audio_path: Path to audio file (WAV)
        output_dir: Optional output directory for separated files
    
    Returns:
        Dict with paths to separated sources and metadata
    """
    import os
    import shutil
    import glob
    
    logger.info(f"🎭 Separating audio sources (CLI): {Path(audio_path).name}")
    
    try:
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="demucs_")
        os.makedirs(output_dir, exist_ok=True)
        
        # Construct Demucs command
        # We use -n htdemucs (fast, high quality)
        # --two-stems=vocals limits output to vocals + other (faster, less disk) -> Actually we want full separation for stats, but 'vocals' is critical.
        # --int24 is better quality? Default output is float32 or int16.
        # -d cpu forces CPU usage.
        
        # Resolve 'demucs' executable path relative to current python interpreter
        # Resolve 'demucs' executable path
        import sys
        import site
        
        possible_paths = [
            Path(sys.executable).parent / "demucs",  # venv/bin/demucs
            Path(site.getuserbase()) / "bin" / "demucs",  # User site bin
            Path.home() / ".local" / "bin" / "demucs",  # Common Linux user bin
            Path.home() / "Library/Python/3.9/bin/demucs", # Common macOS user bin (hardcoded fallback)
        ]
        
        cmd_exec = "demucs" # Default fallback to PATH
        
        for p in possible_paths:
            if p.exists() and os.access(p, os.X_OK):
                cmd_exec = str(p)
                logger.info(f"✅ Found Demucs at: {cmd_exec}")
                break
        
        cmd = [
            cmd_exec,
            "-n", "htdemucs",
            "-d", "mps",  # Metal Performance Shaders (Mac GPU)
            "-o", str(output_dir),
            "--filename", "{track}/{stem}.{ext}", # Organize by track/stem
            str(audio_path)
        ]
        
        # Prepare environment to disable TQDM progress bars
        env = os.environ.copy()
        env["TQDM_DISABLE"] = "1"

        logger.info(f"🚀 Running Demucs: {' '.join(cmd)}")
        
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL, # Prevent TTY read
            env=env, # Disable progress bars
            timeout=600 # 10 minutes max
        )
        
        if process.returncode != 0:
            logger.error(f"Demucs CLI failed: {process.stderr}")
            raise RuntimeError(f"Demucs execution failed: {process.stderr}")
            
        logger.info("✅ Demucs CLI completed successfully")
        
        # Output structure: <output_dir>/htdemucs/<filename>/...
        # We need to find where it saved.
        # The --filename format above puts it in output_dir/htdemucs/<stem>.wav? or output_dir/htdemucs/filename/stem.wav?
        # Default demucs behavior is output_dir / model_name / track_name / stem.wav
        
        # Let's find the files.
        track_name = Path(audio_path).stem
        model_name = "htdemucs"
        result_dir = Path(output_dir) / model_name / track_name
        
        # Handle case where track name might be truncated or normalized by Demucs
        if not result_dir.exists():
            # Try to find any directory inside output_dir/htdemucs
            possible_dirs = list((Path(output_dir) / model_name).glob("*"))
            if possible_dirs:
                result_dir = possible_dirs[0]
            else:
                 raise FileNotFoundError(f"Could not find Demucs output in {Path(output_dir) / model_name}")
        
        result = {
            "source_dir": str(output_dir),
            "sources": {},
            "model": "htdemucs",
            "sample_rate": 44100, # htdemucs default
        }
        
        stems = ["vocals", "drums", "bass", "other"]
        total_energy = 0.0
        
        import librosa
        
        for stem in stems:
            stem_path = result_dir / f"{stem}.wav"
            
            if stem_path.exists():
                # Measure energy for stats
                try:
                    y, sr = librosa.load(str(stem_path), sr=None, mono=True)
                    energy = float(np.mean(y ** 2))
                except Exception:
                    energy = 0.0
                    
                total_energy += energy
                
                result["sources"][stem] = {
                    "path": str(stem_path),
                    "energy": round(energy, 6),
                    "present": energy > 1e-6
                }
            else:
                result["sources"][stem] = {
                    "path": None,
                    "energy": 0.0,
                    "present": False
                }

        # Calculate proportions
        for stem in result["sources"]:
            if total_energy > 0:
                result["sources"][stem]["proportion"] = round(result["sources"][stem]["energy"] / total_energy, 4)
            else:
                result["sources"][stem]["proportion"] = 0.0
                
        # Extract key info
        vocals = result["sources"].get("vocals", {})
        result["summary"] = {
            "vocals_proportion": float(vocals.get("proportion", 0)),
            "music_proportion": round(float(1 - vocals.get("proportion", 0)), 4),
            "has_vocals": bool(vocals.get("present", False)),
        }
        
        logger.info(f"✅ Source separation stats: vocals={result['summary']['vocals_proportion']:.1%}")
        
        return result

    except Exception as e:
        logger.error(f"❌ Source separation failed: {e}")
        return {"error": str(e)}


def compare_voiceovers(
    vocals_path_a: str,
    vocals_path_b: str
) -> Dict[str, Any]:
    """
    Compare two vocal tracks using MFCC features and DTW
    
    Args:
        vocals_path_a: Path to first vocal track (acceptance)
        vocals_path_b: Path to second vocal track (emission)
    
    Returns:
        Comparison metrics including similarity score and timing differences
    """
    librosa = get_librosa()
    
    logger.info("🎤 Comparing voiceovers...")
    
    try:
        # Load vocal tracks
        y_a, sr_a = librosa.load(vocals_path_a, sr=22050, mono=True)
        y_b, sr_b = librosa.load(vocals_path_b, sr=22050, mono=True)
        
        # Extract MFCC features (voice characteristics)
        mfcc_a = librosa.feature.mfcc(y=y_a, sr=sr_a, n_mfcc=13)
        mfcc_b = librosa.feature.mfcc(y=y_b, sr=sr_b, n_mfcc=13)
        
        # Dynamic Time Warping for flexible comparison
        D, wp = librosa.sequence.dtw(mfcc_a, mfcc_b, subseq=True)
        
        # DTW cost (lower = more similar)
        dtw_cost = D[-1, -1]
        
        # Normalize DTW cost to similarity score
        max_cost = np.sqrt(np.sum(mfcc_a**2) + np.sum(mfcc_b**2))
        similarity = 1.0 - min(dtw_cost / (max_cost + 1e-10), 1.0)
        
        # Compute timing offset from warping path
        # Analyze the warping path to find average offset
        path_indices = np.array(wp)
        if len(path_indices) > 0:
            # Average difference between aligned frames
            time_per_frame = 512 / 22050  # hop_length / sr
            frame_offsets = path_indices[:, 0] - path_indices[:, 1]
            avg_offset = np.mean(frame_offsets) * time_per_frame
            max_offset = np.max(np.abs(frame_offsets)) * time_per_frame
        else:
            avg_offset = 0.0
            max_offset = 0.0
        
        # Speech rate comparison (zero crossing rate as proxy)
        zcr_a = float(np.mean(librosa.feature.zero_crossing_rate(y_a)))
        zcr_b = float(np.mean(librosa.feature.zero_crossing_rate(y_b)))
        zcr_diff = abs(zcr_a - zcr_b)
        
        # Spectral centroid (brightness/tone)
        centroid_a = float(np.mean(librosa.feature.spectral_centroid(y=y_a, sr=sr_a)))
        centroid_b = float(np.mean(librosa.feature.spectral_centroid(y=y_b, sr=sr_b)))
        
        result = {
            "voice_similarity": round(float(similarity), 4),
            "dtw_cost": round(float(dtw_cost), 4),
            "timing": {
                "average_offset_seconds": round(float(avg_offset), 3),
                "max_offset_seconds": round(float(max_offset), 3),
                "is_synced": bool(abs(avg_offset) < 0.1),  # Within 100ms
            },
            "characteristics": {
                "acceptance_zcr": round(float(zcr_a), 4),
                "emission_zcr": round(float(zcr_b), 4),
                "acceptance_centroid": round(float(centroid_a), 2),
                "emission_centroid": round(float(centroid_b), 2),
            },
            "is_same_voice": bool(similarity > 0.7),  # Threshold for same speaker
        }
        
        logger.info(f"✅ Voiceover similarity: {similarity:.1%}, offset: {avg_offset:+.2f}s")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Voiceover comparison failed: {e}")
        return {"error": str(e), "voice_similarity": 0.0}



def filter_song_vocals(vocals_path: str, other_stems: Dict[str, str], output_path: str) -> bool:
    """
    Filter out vocals where music energy is significantly higher (likely singing).
    
    Args:
        vocals_path: Path to vocals wav
        other_stems: Dict with paths to 'drums', 'bass', 'other'
        output_path: Path to save filtered vocals
        
    Returns:
        True if filtering was applied/successful
    """
    import logging
    import os
    import numpy as np
    import soundfile as sf
    import librosa
    
    logger = logging.getLogger(__name__)
    logger.info(f"🎻 Filtering song vocals from: {Path(vocals_path).name}")
    
    try:
        # Load vocals
        y_vocals, sr = librosa.load(vocals_path, sr=None, mono=True)
        
        # Load and sum accompaniment
        y_music = np.zeros_like(y_vocals)
        
        for name, path in other_stems.items():
            if path and os.path.exists(path):
                y_stem, _ = librosa.load(path, sr=sr, mono=True)
                # Ensure length matches (padding/trimming might be needed if slight mismatch)
                min_len = min(len(y_music), len(y_stem))
                y_music[:min_len] += y_stem[:min_len]
        
        # Calculate RMS Energy over windows (0.5s)
        frame_length = int(sr * 0.5)
        hop_length = int(sr * 0.25) # 50% overlap for smoother mask
        
        rms_vocals = librosa.feature.rms(y=y_vocals, frame_length=frame_length, hop_length=hop_length)[0]
        rms_music = librosa.feature.rms(y=y_music, frame_length=frame_length, hop_length=hop_length)[0]
        
        # Create mask
        # If Music / Vocals > 2.0 -> Silence it (it's likely a song)
        # We add epsilon to vocal energy to avoid div by zero
        ratio = rms_music / (rms_vocals + 1e-6)
        
        # Threshold: 2.0 (Reverted to aggressive, but protected by Music Dominance Gate)
        mask_frames = ratio < 2.0 
        
        # Interpolate mask to audio sample rate
        mask_samples = np.repeat(mask_frames, hop_length)
        # Pad mask to match audio length
        if len(mask_samples) < len(y_vocals):
            mask_samples = np.pad(mask_samples, (0, len(y_vocals) - len(mask_samples)), 'edge')
        else:
            mask_samples = mask_samples[:len(y_vocals)]
            
        # Apply mask (hard mute)
        # We could do soft attenuation, but for VO recognition, silence is better than noise.
        y_filtered = y_vocals * mask_samples
        
        # Save filtered audio
        sf.write(output_path, y_filtered, sr)
        
        logger.info(f"✅ Saved filtered vocals (Song Removed) to: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Song filtering failed: {e}")
        return False


def compare_audio_full(
    acceptance_path: str,
    emission_path: str,
    do_source_separation: bool = True
) -> Dict[str, Any]:
    """
    Full audio comparison including source separation and voiceover comparison
    
    This is the main function for comprehensive audio analysis.
    """
    import os
    
    logger.info("🔊 Starting full audio comparison...")
    
    temp_dirs = []
    temp_files = []
    
    try:
        # Step 1: Extract audio from videos
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
        
        acceptance_ext = Path(acceptance_path).suffix.lower()
        emission_ext = Path(emission_path).suffix.lower()
        
        if acceptance_ext in video_extensions:
            acceptance_audio = tempfile.mktemp(suffix='_a.wav')
            temp_files.append(acceptance_audio)
            extract_audio_from_video(acceptance_path, acceptance_audio)
        else:
            acceptance_audio = acceptance_path
            
        if emission_ext in video_extensions:
            emission_audio = tempfile.mktemp(suffix='_e.wav')
            temp_files.append(emission_audio)
            extract_audio_from_video(emission_path, emission_audio)
        else:
            emission_audio = emission_path
        
        result = {}
        
        # Step 2: Loudness comparison
        result["loudness"] = compare_loudness(acceptance_audio, emission_audio)
        
        # Step 3: Audio similarity
        result["similarity"] = compare_audio_similarity(acceptance_audio, emission_audio)
        
        # Step 4: Source separation (optional, expensive)
        if do_source_separation:
            # Separate acceptance
            sep_dir_a = tempfile.mkdtemp(prefix="sep_a_")
            temp_dirs.append(sep_dir_a)
            sep_a = separate_sources(acceptance_audio, sep_dir_a)
            
            # Separate emission
            sep_dir_e = tempfile.mkdtemp(prefix="sep_e_")
            temp_dirs.append(sep_dir_e)
            sep_e = separate_sources(emission_audio, sep_dir_e)
            
            result["source_separation"] = {
                "acceptance": sep_a.get("summary"),
                "emission": sep_e.get("summary"),
            }
            
            # Step 5: Voiceover comparison (if both have vocals)
            if (sep_a.get("sources", {}).get("vocals", {}).get("present") and
                sep_e.get("sources", {}).get("vocals", {}).get("present")):
                
                vocals_a = sep_a["sources"]["vocals"]["path"]
                vocals_e = sep_e["sources"]["vocals"]["path"]
                
                result["voiceover"] = compare_voiceovers(vocals_a, vocals_e)
        
        # Compute overall score
        scores = []
        
        if result.get("similarity", {}).get("overall_audio_similarity"):
            scores.append(result["similarity"]["overall_audio_similarity"])
        
        if result.get("voiceover", {}).get("voice_similarity"):
            scores.append(result["voiceover"]["voice_similarity"])
        
        if not result.get("loudness", {}).get("has_loudness_differences"):
            scores.append(1.0)
        else:
            scores.append(0.8)  # Penalty for loudness mismatch
        
        result["overall_score"] = round(float(np.mean(scores)) if scores else 0.0, 4)
        
        logger.info(f"✅ Full audio comparison complete: {result['overall_score']:.1%}")
        
        return result
        
    finally:
        # Cleanup
        import shutil
        for d in temp_dirs:
            if os.path.exists(d):
                try:
                    shutil.rmtree(d)
                except:
                    pass
        for f in temp_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass


# ==============================================================================
# Phase 5: Speech-to-Text (Whisper)
# ==============================================================================

def get_whisper():
    """Lazy load Whisper model"""
    global _whisper
    if _whisper is None:
        import whisper
        _whisper = whisper
        logger.info("✅ Whisper loaded")
    return _whisper


def _detect_and_strip_loop_hallucination(text: str, ngram_size: int = 3, max_repeats: int = 4) -> str:
    """
    Detects Whisper loop hallucinations: repetitive n-gram patterns and Unicode garbage.

    Includes detection for:
    - DETECTOR 0: Unicode garbage — egzotyczne znaki niełacińskie >70% tokenów
      (Whisper halucynuje znakami koreańskimi, syngaleskimi, hebrajskimi przy muzyce bez lektora)
    - DETECTOR 1: Token loop — pojedynczy krótki token (≤4 znaki) stanowi >50% tekstu przy ≥8
      wystąpieniach (np. "כ כ כ כ" lub "removing removing removing removing removing removing")
    - DETECTOR 2: Intra-word syllable loops (e.g., 'te-te-te' or 'tetetete')
    - DETECTOR 3: N-gram word loops (standard) + Single-word excessive repetition
    """
    if not text or len(text) < 10:
        return text

    text_lower = text.lower()
    words = text_lower.split()

    # ── DETECTOR 0: Unicode garbage (egzotyczne znaki) ─────────────────────
    # Whisper na audio muzycznym bez lektora produkuje ciągi znaków z niełacińskich
    # alfabetów: koreańskiego (U+AC00+), syngaleskiego (U+0D80+), hebrajskiego (U+0590+),
    # arabskiego (U+0600+), etc. Jeśli >70% tokenów jest zdominowane przez takie znaki
    # — to jest halucynacja, nie prawdziwy tekst.
    if len(words) >= 3:
        non_latin_tokens = 0
        for word in words:
            # Liczmy znaki spoza Basic Latin + Latin Extended A/B (U+0000–U+024F)
            # Ignorujemy cyfry i znaki interpunkcji ASCII
            total_chars = sum(1 for c in word if not c.isspace())
            non_latin_chars = sum(
                1 for c in word
                if ord(c) > 0x024F and not c.isdigit() and not c.isspace()
            )
            if total_chars > 0 and non_latin_chars / total_chars > 0.6:
                non_latin_tokens += 1

        non_latin_ratio = non_latin_tokens / len(words)
        if non_latin_ratio > 0.7:
            logger.warning(
                f"⚠️ [DETECTOR 0] Unicode garbage hallucination! "
                f"{non_latin_ratio:.1%} tokenów to znaki niełacińskie. "
                f"Próbka: '{text[:80]}'. Discarding."
            )
            return ""

    # ── DETECTOR 1: Token loop (krótkie tokeny w pętli) ────────────────────
    # Łapie pętle krótkich tokenów które nie są wykrywane przez n-gramy.
    # Przykład: "כ כ כ כ כ כ כ כ" (token 1-znakowy, 100% tekstu)
    # lub "removing removing removing..." (już łapane przez detektor 3, ale wcześniej)
    if len(words) >= 8:
        from collections import Counter
        token_counts = Counter(words)
        top_token, top_count = token_counts.most_common(1)[0]
        top_ratio = top_count / len(words)

        if len(top_token) <= 9 and top_ratio > 0.5:
            logger.warning(
                f"⚠️ [DETECTOR 1] Short-token loop hallucination! "
                f"Token '{top_token}' to {top_ratio:.1%} tekstu ({top_count}/{len(words)} wystąpień). "
                f"Discarding."
            )
            return ""

    # ── DETECTOR 2: Intra-word syllable loops (e.g. te-te-te-te) ──────────
    import re
    # Check if any "word" contains too many repetitive fragments or hyphens
    for word in words:
        if len(word) > 10:
            # Check for hyphen-separated repetitions (e.g. te-te-te-te)
            if word.count('-') > 4:
                 logger.warning(f"⚠️ [DETECTOR 2] Syllable loop detected in word: '{word[:50]}...'. Discarding.")
                 return ""

            # Check for non-hyphenated dense repetition (e.g. tetetete, liedliedliedlied)
            # Regex: any 2-6 char sequence repeating at least 3 times after first (4 total)
            if re.search(r'(.{2,6})\1{3,}', word):
                 logger.warning(f"⚠️ [DETECTOR 2] Character loop detected in word: '{word[:50]}...'. Discarding.")
                 return ""

    # ── DETECTOR 3: N-gram and Single-word loops ───────────────────────────
    from collections import Counter

    # Check 1-grams (single word loops)
    if len(words) >= 3:
        one_grams = Counter(words)
        if one_grams:
            mc_word, count = one_grams.most_common(1)[0]
            # Absolute loop for short texts
            if len(words) <= 5 and count == len(words):
                logger.warning(
                    f"⚠️ [DETECTOR 3] Single-word absolute loop! '{mc_word}' repeated {count}x. Discarding."
                )
                return ""
            # Percentage loop for longer texts
            elif len(words) > 5 and count > len(words) * 0.6:
                logger.warning(
                    f"⚠️ [DETECTOR 3] Single-word loop! '{mc_word}' to {count/len(words):.1%} tekstu. Discarding."
                )
                return ""

    if len(words) < 5:
        return text

    # Check N-grams
    if len(words) >= ngram_size * (max_repeats + 1):
        ngrams = [
            " ".join(words[i:i + ngram_size])
            for i in range(len(words) - ngram_size + 1)
        ]
        counts = Counter(ngrams)
        most_common_ngram, most_common_count = counts.most_common(1)[0]

        if most_common_count > max_repeats:
            logger.warning(
                f"⚠️ [DETECTOR 3] N-gram loop! '{most_common_ngram}' "
                f"powtórzony {most_common_count}x. Discarding."
            )
            return ""

    return text


def transcribe_audio(
    audio_path: str,
    language: Optional[str] = None,
    model_name: str = "base"
) -> Dict[str, Any]:
    """
    Transcribe audio to text using MLX-optimized Whisper (Neural Engine)
    
    Args:
        audio_path: Path to audio file (WAV, MP3, etc.)
        language: Optional language code (e.g., 'pl', 'en'). Auto-detect if None.
        model_name: Whisper model size: 'tiny', 'base', 'small', 'medium', 'large'
    
    Returns:
        Dict with transcription text, segments with timestamps, and metadata
    """
    # 1. Get raw result from transcription engine
    try:
        # Prefer MLX for M-series Macs
        try:
            mlx_whisper = get_mlx_whisper()
            import os
            
            # Use full-precision community models for 100% accuracy matching standard Whisper
            model_map = {
                "tiny": "mlx-community/whisper-tiny-mlx",
                "base": "mlx-community/whisper-base-mlx",
                "small": "mlx-community/whisper-small-mlx",
                "medium": "mlx-community/whisper-medium-mlx",
                "large": "mlx-community/whisper-large-v3-mlx"
            }
            
            config_model = os.getenv("WHISPER_MODEL_SIZE", "small")
            target_model_key = config_model if model_name == "base" else model_name
            target_model = model_map.get(target_model_key, "mlx-community/whisper-small-mlx")
            
            logger.info(f"📝 MLX Transcribing (M4): {Path(audio_path).name} using {target_model}")
            
            options = {
                "word_timestamps": True,
                # Anti-hallucination: do NOT feed previous tokens back as context.
                # Without this, Whisper enters a self-reinforcing "loop" and generates
                # repetitive gibberish (e.g. Welsh-like text) on music-only audio.
                "condition_on_previous_text": False,
                # Segments with no-speech probability above this are discarded by the model.
                # Increased to 0.85 because commercials often have heavy BG music that bumps no_speech_prob up.
                "no_speech_threshold": 0.85,
            }
            if language:
                options["language"] = language
                
            result = mlx_whisper.transcribe(str(audio_path), path_or_hf_repo=target_model, **options)
            
        except Exception as mlx_err:
            logger.warning(f"⚠️ MLX Whisper failed: {mlx_err}. Attempting PyTorch MPS fallback...")
            
            # Additional GC before heavy model load
            import gc
            gc.collect()
            
            try:
                whisper = get_whisper()
                import torch
                
                # Determine device
                device = "mps" if torch.backends.mps.is_available() else "cpu"
                logger.info(f"🤖 Loading standard Whisper on {device}: {target_model}")
                
                model = whisper.load_model(target_model, device=device)
                
                options = {
                    "fp16": device == "mps", # FP16 supported on MPS
                    "beam_size": 5,
                    "condition_on_previous_text": False,
                }
                if language:
                    options["language"] = language
                    
                result = model.transcribe(str(audio_path), **options)
            except Exception as torch_err:
                logger.error(f"❌ Both MLX and PyTorch fallback failed: {torch_err}")
                return {"error": f"Transcription engines failed: {mlx_err} | {torch_err}", "text": "", "segments": []}

        # 2. Process engine results (Common Logic)
        segments = []
        db_hallucinations = []
        
        # Fetch active hallucinations from database
        try:
            from models.database import SessionLocal
            from models.models import WhisperHallucination
            with SessionLocal() as db_session:
                db_hallucinations = db_session.query(WhisperHallucination).filter(WhisperHallucination.is_active == True).all()
        except Exception as db_e:
            logger.error(f"Failed to fetch hallucinations from DB: {db_e}")
            
        filtered_text = []
        for seg in result.get("segments", []):
            text = seg["text"].strip()
            text_lower = text.lower()
            text_clean = text_lower.strip('.!?, ')
            
            # Skip segments that are ONLY punctuation (e.g. '!', '...', '🎶')
            if not text_clean:
                logger.warning(f"⚠️ Filtered punctuation-only segment: '{text}'")
                continue
                
            # Database hallucination filter
            is_hallucination = False
            for h in db_hallucinations:
                if h.language and language and h.language != language:
                    continue
                phrase = h.phrase.lower()
                if h.match_type.value == "exact":
                    if text_clean == phrase or text_lower == phrase:
                        is_hallucination = True
                        break
                else: # CONTAINS
                    if phrase in text_lower:
                        is_hallucination = True
                        break
            
            if is_hallucination:
                logger.warning(f"⚠️ Filtered hallucination (DB): '{text}'")
                continue
                
            # Filter out low-confidence segments
            # Tolerating up to 0.85 for commercials
            no_speech_prob = seg.get("no_speech_prob", 0.0)
            if no_speech_prob > 0.85:
                logger.warning(f"⚠️ Filtered low-confidence segment (no_speech_prob={no_speech_prob:.2f}): '{text}'")
                continue
                
            segments.append({
                "start": round(float(seg["start"]), 2),
                "end": round(float(seg["end"]), 2),
                "text": text,
            })
            filtered_text.append(text)
            
        full_text = " ".join(filtered_text)

        # ── Loop hallucination detector ───────────────────────────────────────
        # Even with condition_on_previous_text=False, Whisper can still produce
        # subtle repetition loops. Detect: if any 3-word n-gram repeats > 4x
        # in the full transcript, the entire text is likely a hallucination.
        full_text_before = full_text
        full_text = _detect_and_strip_loop_hallucination(full_text)
        
        # If the detector stripped the hallucinated loop, also clear the segments
        # so they don't pollute the UI timeline.
        if full_text == "" and full_text_before != "":
            segments = []

        transcription = {
            "text": full_text,
            "language": result.get("language", "unknown"),
            "segments": segments,
            "word_count": len(full_text.split()),
        }
        
        logger.info(f"✅ Transcribed: {len(segments)} segments, {transcription['word_count']} words")
        return transcription

    except Exception as e:
        logger.error(f"❌ Transcription failed (Engine/Processing): {e}")
        return {"error": str(e), "text": "", "segments": []}


def normalize_text(text: str) -> str:
    """
    Aggressive text normalization for comparison
    - Lowercase
    - Strip punctuation
    - Remove extra whitespace
    """
    import string
    
    # Lowercase
    text = text.lower()
    
    # Remove punctuation
    text = text.translate(str.maketrans("", "", string.punctuation))
    
    # Normalize whitespace
    text = " ".join(text.split())
    
    return text



def generate_srt(segments: list, output_path: Optional[str] = None) -> str:
    """
    Generate SRT subtitle file from transcription segments
    
    Args:
        segments: List of segments with start, end, text
        output_path: Optional path to save SRT file
    
    Returns:
        SRT content as string
    """
    srt_lines = []
    
    for i, seg in enumerate(segments, 1):
        start = seg["start"]
        end = seg["end"]
        text = seg["text"]
        
        # Convert to SRT time format: HH:MM:SS,mmm
        def format_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds % 1) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
        
        srt_lines.append(str(i))
        srt_lines.append(f"{format_time(start)} --> {format_time(end)}")
        srt_lines.append(text)
        srt_lines.append("")
    
    srt_content = "\n".join(srt_lines)
    
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
        logger.info(f"✅ SRT saved to: {output_path}")
    
    return srt_content


def compare_transcripts(
    transcript_a: Dict[str, Any],
    transcript_b: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Compare two transcriptions and find differences
    
    Args:
        transcript_a: Acceptance transcription
        transcript_b: Emission transcription
    
    Returns:
        Comparison results with text similarity and differences
    """
    import difflib
    
    logger.info("📊 Comparing transcripts...")
    
    raw_text_a = transcript_a.get("text", "")
    raw_text_b = transcript_b.get("text", "")
    
    # Normalize for comparison
    text_a = normalize_text(raw_text_a)
    text_b = normalize_text(raw_text_b)
    
    if text_a != raw_text_a:
        logger.info(f"Normalized A: {text_a[:100]}...")
    if text_b != raw_text_b:
        logger.info(f"Normalized B: {text_b[:100]}...")
    
    # Word-level comparison on NORMALIZED tokens
    words_a = text_a.split()
    words_b = text_b.split()
    
    # Compute similarity ratio
    matcher = difflib.SequenceMatcher(None, words_a, words_b)
    similarity = matcher.ratio()
    
    # Find differences
    differences = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            diff = {
                "type": tag,  # 'replace', 'delete', 'insert'
                "acceptance": " ".join(words_a[i1:i2]) if i1 < i2 else "",
                "emission": " ".join(words_b[j1:j2]) if j1 < j2 else "",
                "position": i1,
            }
            differences.append(diff)
    
    # Segment-level comparison for timing
    segments_a = transcript_a.get("segments", [])
    segments_b = transcript_b.get("segments", [])
    
    segment_diffs = []
    min_segments = min(len(segments_a), len(segments_b))
    
    for i in range(min_segments):
        seg_a = segments_a[i]
        seg_b = segments_b[i]
        
        # Compare segment text (normalized)
        norm_a = normalize_text(seg_a["text"])
        norm_b = normalize_text(seg_b["text"])
        
        if norm_a != norm_b:
            segment_diffs.append({
                "segment_idx": i,
                "time_a": f"{seg_a['start']:.1f}s",
                "time_b": f"{seg_b['start']:.1f}s",
                "text_a": seg_a["text"],
                "text_b": seg_b["text"],
            })
    
    # Check for extra segments
    if len(segments_a) > len(segments_b):
        for i in range(min_segments, len(segments_a)):
            segment_diffs.append({
                "segment_idx": i,
                "time_a": f"{segments_a[i]['start']:.1f}s",
                "time_b": "(missing)",
                "text_a": segments_a[i]["text"],
                "text_b": "",
            })
    elif len(segments_b) > len(segments_a):
        for i in range(min_segments, len(segments_b)):
            segment_diffs.append({
                "segment_idx": i,
                "time_a": "(missing)",
                "time_b": f"{segments_b[i]['start']:.1f}s",
                "text_a": "",
                "text_b": segments_b[i]["text"],
            })
    
    
    result = {
        "text_similarity": round(float(similarity), 4),
        "is_text_match": bool(similarity > 0.95),  # 95% threshold
        "word_count_a": len(words_a),
        "word_count_b": len(words_b),
        "word_differences": differences,  # Return all differences
        "segment_differences": segment_diffs,  # Return all segment differences
        "total_differences": len(differences),
        "acceptance_text": text_a[:500],  # First 500 chars
        "emission_text": text_b[:500],
        "timeline_data": {
            "acceptance_segments": segments_a,
            "emission_segments": segments_b,
        }
    }
    
    
    if similarity > 0.95:
        logger.info(f"✅ Transcripts match: {similarity:.1%}")
    else:
        logger.warning(f"⚠️ Transcript differences: {similarity:.1%}, {len(differences)} word changes")
    
    return result

# ==============================================================================
# Phase 6: Independent File Transcription Pipeline
# ==============================================================================

def transcribe_single_file(
    file_path: str,
    language: Optional[str] = None,
    model_name: str = "base",
    use_source_separation: bool = True,
    filter_song: bool = False,
    label: str = "file"
) -> Dict[str, Any]:
    """
    Process a SINGLE file end-to-end:
    1. Extract audio from video (FFmpeg → WAV 44.1kHz stereo)
    2. Optionally run Demucs CLI → separate vocals
    3. Verify vocals.wav exists and has content
    4. OPTIONAL: Filter out "Song" parts (high music energy)
    5. Transcribe vocals (or mixed audio as fallback) with Whisper
    6. Return structured result
    
    Args:
        file_path: Path to video or audio file
        language: Optional language code for Whisper
        model_name: Whisper model size
        use_source_separation: If True, run Demucs before Whisper
        filter_song: If True, remove segments where music > vocals (remove singing)
        label: Human-readable label for logging
    
    Returns:
        Dict with transcription, segments, language, and separation stats
    """
    import os
    import shutil
    
    logger.info(f"🎬 [{label.upper()}] Starting independent transcription pipeline: {Path(file_path).name}")
    
    temp_files = []
    temp_dirs = []
    
    try:
        # Step 1: Extract audio from video
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext in video_extensions:
            audio_path = tempfile.mktemp(suffix=f'_{label}.wav')
            temp_files.append(audio_path)
            extract_audio_from_video(file_path, audio_path)
            logger.info(f"  [{label.upper()}] Audio extracted: {Path(audio_path).name}")
        else:
            audio_path = file_path
        
        # Step 2: Source separation (Demucs) — extract clean vocals
        vocals_path = audio_path  # fallback: use mixed audio
        separation_stats = None
        
        if use_source_separation:
            logger.info(f"  [{label.upper()}] Running Demucs source separation...")
            sep_dir = tempfile.mkdtemp(prefix=f"demucs_{label}_")
            temp_dirs.append(sep_dir)
            
            sep_result = separate_sources(audio_path, sep_dir)
            
            if "error" in sep_result:
                logger.warning(f"  [{label.upper()}] Demucs failed: {sep_result['error']}. Using mixed audio.")
                separation_stats = {"status": "failed", "error": sep_result["error"]}
            else:
                # Step 3: Verify vocals exist and have content
                vocals_info = sep_result.get("sources", {}).get("vocals", {})
                
                if vocals_info.get("present") and vocals_info.get("path"):
                    vocals_file = vocals_info["path"]
                    
                    if os.path.exists(vocals_file) and os.path.getsize(vocals_file) > 1000:
                        vocals_path = vocals_file
                        logger.info(f"  [{label.upper()}] ✅ Using separated vocals: {Path(vocals_file).name} (energy={vocals_info.get('energy', 0):.6f})")
                        
                        # Apply Song Filter if requested AND Music is dominant
                        if filter_song:
                            # Calculate Music Dominance
                            # vocals_info comes from separate_sources -> stats
                            vocals_energy = vocals_info.get("energy", 0)
                            
                            # Sum other stems energy
                            others_energy = 0.0
                            other_stems = {}
                            for stem in ["drums", "bass", "other"]:
                                stem_info = sep_result.get("sources", {}).get(stem, {})
                                if stem_info.get("path"):
                                    other_stems[stem] = stem_info["path"]
                                    others_energy += stem_info.get("energy", 0)
                            
                            total_energy = vocals_energy + others_energy
                            music_proportion = others_energy / total_energy if total_energy > 0 else 0
                            
                            logger.info(f"  [{label.upper()}] 📊 Music Proportion: {music_proportion:.1%}")
                            
                            # GATE: Only filter if Music is dominant (> 40%)
                            if music_proportion > 0.4:
                                filtered_vocals = str(Path(sep_dir) / "vocals_filtered.wav")
                                if filter_song_vocals(vocals_path, other_stems, filtered_vocals):
                                    vocals_path = filtered_vocals
                                    logger.info(f"  [{label.upper()}] 🕵️‍♂️ Applied Song Filter (Music > 40%)")
                            else:
                                logger.info(f"  [{label.upper()}] 🛡️ Skipped Song Filter (Music < 40%, likely VO)")

                    else:
                        logger.warning(f"  [{label.upper()}] Vocals file missing or empty. Using mixed audio.")
                else:
                    logger.warning(f"  [{label.upper()}] No vocals detected. Using mixed audio.")
                
                separation_stats = {
                    "status": "success",
                    "used_vocals": vocals_path != audio_path,
                    "summary": sep_result.get("summary", {}),
                }
        
        # Step 4: Transcribe with Whisper
        is_using_vocals = vocals_path != audio_path
        logger.info(f"  [{label.upper()}] Transcribing with Whisper (input: {'vocals' if is_using_vocals else 'mixed'})...")
        transcript = transcribe_audio(vocals_path, language=language, model_name=model_name)
        
        # ── RETRY FALLBACK: If vocals yielded empty text, try original mixed audio ──
        if is_using_vocals and not transcript.get("text") and not transcript.get("error"):
            logger.warning(f"  [{label.upper()}] ⚠️ Empty transcript from vocals (possible hallucination or artifacts). Retrying with MIXED audio...")
            transcript = transcribe_audio(audio_path, language=language, model_name=model_name)
            is_using_vocals = False # Mark that we ended up using mixed
        
        if transcript.get("error"):
            logger.error(f"  [{label.upper()}] Whisper failed: {transcript['error']}")
        else:
            logger.info(f"  [{label.upper()}] ✅ Transcribed: {transcript.get('word_count', 0)} words, {len(transcript.get('segments', []))} segments")
        
        # Step 5: Return structured result
        return {
            "transcript": transcript,
            "source_separation": separation_stats,
            "input_file": str(file_path),
            "used_vocals": is_using_vocals,
        }
        
    except Exception as e:
        logger.error(f"  [{label.upper()}] Pipeline failed: {e}")
        return {
            "transcript": {"error": str(e), "text": "", "segments": []},
            "source_separation": {"status": "error", "error": str(e)},
            "input_file": str(file_path),
            "used_vocals": False,
        }
    finally:
        # Cleanup temp files (but keep Demucs dirs alive until we're done)
        for f in temp_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass
        for d in temp_dirs:
            if os.path.exists(d):
                try:
                    shutil.rmtree(d)
                except:
                    pass


def compare_spoken_text(
    acceptance_path: str,
    emission_path: str,
    language: Optional[str] = None,
    model_name: str = "base",
    use_separated_vocals: bool = True,
    filter_song: bool = False,
    audio_similarity_score: Optional[float] = None
) -> Dict[str, Any]:
    """
    Full spoken text comparison pipeline:
    1. Process acceptance file independently (extract → Demucs → [Filter] → Whisper)
    2. Process emission file independently (extract → Demucs → [Filter] → Whisper)
    3. Compare transcriptions
    
    Each file is processed completely independently via transcribe_single_file(),
    eliminating duplicate Demucs runs and ensuring clean separation.
    
    Args:
        acceptance_path: Path to acceptance video/audio
        emission_path: Path to emission video/audio
        language: Optional language code
        model_name: Whisper model size
        use_separated_vocals: If True, use Demucs before Whisper
    
    Returns:
        Complete comparison results with both transcripts and diff
    """
    import gc
    
    # FAST PATH: Skip heavy Demucs+Whisper when audio is near-identical.
    # Demucs is non-deterministic — identical files can yield slightly different vocal
    # separation results, causing Whisper to transcribe a different audio subset → false VO positives.
    # Threshold 0.98 (not 1.0) ensures files with tiny differences still go through STT.
    if audio_similarity_score is not None and audio_similarity_score >= 0.98:
        logger.info(
            f"✅ FAST PATH: Audio similarity {audio_similarity_score:.4f} >= 0.98. "
            f"Skipping Demucs+Whisper to avoid false positives and save ~3 GB RAM."
        )
        return {
            "transcript_acceptance": {"text": "", "segments": [], "word_count": 0},
            "transcript_emission": {"text": "", "segments": [], "word_count": 0},
            "comparison": {
                "text_similarity": 1.0,
                "is_text_match": True,
                "word_count_a": 0,
                "word_count_b": 0,
                "word_differences": [],
                "segment_differences": [],
                "total_differences": 0,
                "acceptance_text": "",
                "emission_text": "",
            },
            "text_similarity": 1.0,
            "is_text_match": True,
            "skipped_reason": (
                f"Audio similarity {audio_similarity_score:.4f} >= 0.98. "
                "STT skipped to avoid false positives from source separation non-determinism."
            ),
            "pipeline_info": {"skipped": True},
            "detected_language": language or "unknown",
            "voiceover": None,
        }
    
    logger.info("🎙️ Starting full spoken text comparison (audio similarity below threshold)...")
    
    # Process acceptance file
    logger.info("=" * 60)
    logger.info("📗 ACCEPTANCE FILE")
    logger.info("=" * 60)
    result_a = transcribe_single_file(
        acceptance_path,
        language=language,
        model_name=model_name,
        use_source_separation=use_separated_vocals,
        filter_song=filter_song,
        label="acceptance"
    )
    
    # Free memory between heavy processing
    gc.collect()
    
    # Process emission file  
    logger.info("=" * 60)
    logger.info("📕 EMISSION FILE")
    logger.info("=" * 60)
    result_b = transcribe_single_file(
        emission_path,
        language=language,
        model_name=model_name,
        use_source_separation=use_separated_vocals,
        filter_song=filter_song,
        label="emission"
    )
    
    gc.collect()
    
    # Compare transcripts
    transcript_a = result_a.get("transcript", {"text": "", "segments": []})
    transcript_b = result_b.get("transcript", {"text": "", "segments": []})
    
    logger.info("📊 Comparing transcripts...")
    comparison = compare_transcripts(transcript_a, transcript_b)
    
    result = {
        "transcript_acceptance": transcript_a,
        "transcript_emission": transcript_b,
        "comparison": comparison,
        "text_similarity": comparison.get("text_similarity", 0),
        "is_text_match": comparison.get("is_text_match", False),
        "pipeline_info": {
            "acceptance_used_vocals": result_a.get("used_vocals", False),
            "emission_used_vocals": result_b.get("used_vocals", False),
            "acceptance_separation": result_a.get("source_separation"),
            "emission_separation": result_b.get("source_separation"),
        },
        "detected_language": transcript_a.get("language") or transcript_b.get("language"),
    }
    
    similarity = result["text_similarity"]
    if similarity > 0.95:
        logger.info(f"✅ Transcripts match: {similarity:.1%}")
    else:
        logger.warning(f"⚠️ Transcript differences: {similarity:.1%}")
    
    return result

