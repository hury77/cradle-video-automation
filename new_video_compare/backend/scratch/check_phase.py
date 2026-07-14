import subprocess
import numpy as np
import soundfile as sf

video_path = "/Users/hubert.rycaj/Documents/cradle-video-automation/new_video_compare/backend/uploads/CD~AMAZON-subject FEET ESCAPE_LG~ITE_CA~None_SZ~30_16x9_PR~Spoticar-SPOTICAR_FM~Video_FF~1088395_emis_edc25946.mp4"
wav_path = "/tmp/test_emission.wav"

# Convert to wav using ffmpeg from venv/bin/ffmpeg? Wait, venv/bin/ffmpeg didn't exist earlier!
import shutil
ffmpeg_path = shutil.which("ffmpeg") or "ffmpeg" # maybe uvicorn env has it?

try:
    subprocess.run([
        "ffmpeg", 
        "-y", "-i", video_path, 
        "-ac", "2", "-ar", "44100", 
        wav_path
    ], check=True, capture_output=True)

    data, rate = sf.read(wav_path)
    if len(data.shape) > 1 and data.shape[1] == 2:
        left = data[:, 0]
        right = data[:, 1]
        
        # Calculate correlation
        corr = np.corrcoef(left, right)[0, 1]
        print(f"L/R Correlation: {corr:.4f}")
        
        # Calculate power
        mono_mix = (left + right) / 2
        mono_power = np.mean(mono_mix**2)
        stereo_power = (np.mean(left**2) + np.mean(right**2)) / 2
        print(f"Mono mix power / Stereo power: {mono_power / (stereo_power + 1e-10):.4f}")
    else:
        print("Not stereo")
except Exception as e:
    print(f"Error: {e}")
