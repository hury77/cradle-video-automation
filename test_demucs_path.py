
import logging
import sys
import os

# Setup logging
logging.basicConfig(level=logging.INFO)

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "new_video_compare/backend"))

from services.audio_service import separate_sources

# We do NOT add the manual PATH hack here. 
# We rely on the new logic in separate_sources to find demucs.

print("🔍 Testing Demucs Discovery...")
# Use a dummy file path (doesn't need to exist for path resolution check, 
# but separate_sources runs demucs immediately, so it might fail on file not found)
# Actually, let's use the real file if possible, or just catch the error.
# The `separate_sources` function logs "Found Demucs at: ..." before running.
# We can check the logs.

audio_path = "new_video_compare/backend/uploads/118468_JEEP_COMPASS_THE_GREAT_PRETENDERS_FEVEREIRO_TVC_30s_PTE_3ebc9640.mp4" # Dummy path
if not os.path.exists(audio_path):
    print(f"⚠️ Warning: File {audio_path} not found, but we just want to see if Demucs is found.")

try:
    separate_sources(audio_path, output_dir="temp_test_demucs")
except Exception as e:
    print(f"Result: {e}")
