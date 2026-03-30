import sys
import os
import time
import logging
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from services.audio_service import transcribe_audio

# Configure logging to see the "MLX Transcribing" messages
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_m4_stt():
    sample_wav = "/Users/hubert.rycaj/Documents/cradle-video-automation/new_video_compare/backend/uploads/118468_JEEP_COMPASS_THE_GREAT_PRETENDERS_FEVEREIRO_TVC_30s_PTE_3ebc9640.wav"
    
    if not os.path.exists(sample_wav):
        print(f"❌ Sample file not found: {sample_wav}")
        return

    print(f"\n🚀 Testing M4 Acceleration (Neural Engine) on: {Path(sample_wav).name}")
    print("--- Obserwuj Monitor Aktywności (zakładka CPU/ANE) ---")
    
    start_time = time.time()
    
    try:
        # This will use get_mlx_whisper() and the quantized small model
        result = transcribe_audio(sample_wav, model_name="small")
        
        duration = time.time() - start_time
        
        print("\n✅ Transcription Complete!")
        print(f"⏱️  Time taken: {duration:.2f} seconds")
        print(f"📝 Text preview: {result.get('text', '')[:100]}...")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    test_m4_stt()
