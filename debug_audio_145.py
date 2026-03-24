
import logging
import sys
import os
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("DebugAudio145")

# Add backend to path to use services
sys.path.append(os.path.join(os.getcwd(), "new_video_compare/backend"))

# Fix Demucs PATH
os.environ["PATH"] += os.pathsep + "/Users/hubert.rycaj/Library/Python/3.9/bin"

from services.audio_service import extract_audio_from_video, separate_sources, transcribe_audio, get_whisper

# Define file paths
FILE_PATH = "new_video_compare/backend/uploads/118468_JEEP_COMPASS_THE_GREAT_PRETENDERS_FEVEREIRO_TVC_30s_PTE_3ebc9640.mov"

if not os.path.exists(FILE_PATH):
    print(f"❌ File not found: {FILE_PATH}")
    exit(1)

print(f"🔍 Analyzing: {FILE_PATH}")

# 1. Extract Audio
print("\n🎵 Extracting Audio...")
audio_path = extract_audio_from_video(FILE_PATH)
print(f"✅ Extracted to: {audio_path}")

# 2. Run Whisper on Original (Auto Detect)
print("\n📝 Running Whisper on Original Audio (Auto Detect)...")
try:
    transcription = transcribe_audio(audio_path)
    print(f"Detected Language: {transcription['language']}")
    print(f"Text: {transcription['text']}")
except Exception as e:
    print(f"❌ Whisper Failed: {e}")

# 3. Run Demucs
print("\n🎭 Running Demucs Separation...")
demucs_result = separate_sources(audio_path)

if "sources" in demucs_result:
    vocals_path = demucs_result["sources"]["vocals"]["path"]
    music_proportion = demucs_result["summary"]["music_proportion"]
    vocals_proportion = demucs_result["summary"]["vocals_proportion"]
    
    print(f"Vocals Path: {vocals_path}")
    print(f"Music Proportion: {music_proportion:.1%}")
    print(f"Vocals Proportion: {vocals_proportion:.1%}")
    
    if vocals_path and os.path.exists(vocals_path):
        # 4. Run Whisper on Vocals
        print("\n📝 Running Whisper on Vocals Track...")
        try:
            transcription_vocals = transcribe_audio(vocals_path)
            print(f"Vocals Language: {transcription_vocals['language']}")
            print(f"Vocals Text: {transcription_vocals['text']}")
        except Exception as e:
            print(f"❌ Whisper on Vocals Failed: {e}")
            
        # 5. Experiment: Force English
        print("\n🇬🇧 Forcing English on Vocals...")
        try:
            transcription_en = transcribe_audio(vocals_path, language="en")
            print(f"Text (EN): {transcription_en['text']}")
        except Exception as e:
            print(f"❌ Whisper EN Failed: {e}")

else:
    print("❌ Demucs failed to separate sources")
    print(demucs_result)

print("\n✅ Debug Complete")
