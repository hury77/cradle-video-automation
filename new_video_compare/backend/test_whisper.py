import sys
import logging
from pathlib import Path

# setup minimal config
sys.path.append("/Users/hubert.rycaj/Documents/cradle-video-automation/new_video_compare/backend")

from services.audio_service import transcribe_audio, extract_audio_from_video, separate_sources

logging.basicConfig(level=logging.INFO)

file_path = "uploads/122391_1090017_Favorit_Dishwasher_-_Feature_Assets_260408I6XX_Video_30s_16x9_German_DE_1_b15bf4f1.mp4"

print("1. Extracting audio...")
audio_path = extract_audio_from_video(file_path, "test_audio.wav", start_time=0.0, duration=32.0)

print("2. Transcribing MIXED audio...")
res_mixed = transcribe_audio(audio_path, language="de", model_name="base")
print("MIXED RESULT:", res_mixed.get("text"))

print("3. Running Demucs...")
sep_result = separate_sources(audio_path, "test_demucs")
vocals_path = sep_result["sources"]["vocals"]["path"]

print("4. Transcribing VOCALS audio...")
res_vocals = transcribe_audio(vocals_path, language="de", model_name="base")
print("VOCALS RESULT:", res_vocals.get("text"))
