import sys
import os

# Mock the loop detector call logic
def mock_transcription_logic(full_text, segments, detector_func):
    full_text_before = full_text
    full_text = detector_func(full_text)
    
    if full_text_before and not full_text:
        segments = []
        
    return full_text, segments

# Import detector
sys.path.append(os.path.join(os.getcwd(), "new_video_compare/backend"))
from services.audio_service import _detect_and_strip_loop_hallucination

def test():
    print("--- VERIFYING SEGMENTS CLEANUP LOGIC ---")
    
    text = "serious serious serious serious serious serious serious serious serious"
    segments = [{"start": 0, "end": 10, "text": text}]
    
    # 1. Test the detector itself first
    stripped_text = _detect_and_strip_loop_hallucination(text)
    print(f"Detector result: '{stripped_text}'")
    
    # 2. Test the integration logic (segments clearing)
    final_text, final_segments = mock_transcription_logic(text, segments, _detect_and_strip_loop_hallucination)
    
    print(f"Final text: '{final_text}'")
    print(f"Final segments count: {len(final_segments)}")
    
    if not final_text and len(final_segments) == 0:
        print("✅ SUCCESS: Both text and segments are cleared.")
    else:
        print("❌ FAILURE: Segments were not cleared.")

if __name__ == "__main__":
    test()
