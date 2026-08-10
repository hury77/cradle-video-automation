import os
import sys
import numpy as np
import soundfile as sf
import tempfile
import pytest

# Add backend to path so we can import services
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../new_video_compare/backend')))

from services.audio_service import apply_vad_filter

def test_apply_vad_filter_length_and_muting():
    # 1. Create a dummy audio file (16kHz)
    sr = 16000
    duration_sec = 2.0
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    
    # Create "speech" (a 440Hz sine wave) from 0.5s to 1.5s
    audio_data = np.zeros_like(t)
    speech_start = int(0.5 * sr)
    speech_end = int(1.5 * sr)
    
    # Add a loud sine wave
    audio_data[speech_start:speech_end] = 0.5 * np.sin(2 * np.pi * 440 * t[speech_start:speech_end])
    
    # Save to temp file
    input_wav = tempfile.mktemp(suffix='.wav')
    output_wav = tempfile.mktemp(suffix='.wav')
    
    sf.write(input_wav, audio_data, sr)
    
    try:
        # 2. Apply VAD filter
        # We set threshold low and pad low to accurately test muting
        result = apply_vad_filter(
            input_wav, 
            output_wav, 
            threshold=0.3,
            min_silence_duration_ms=100,
            speech_pad_ms=50
        )
        
        assert result is True, "VAD filter should return True on success"
        
        # 3. Verify output
        out_data, out_sr = sf.read(output_wav)
        
        # Check A: Exact same length
        assert len(out_data) == len(audio_data), f"Length mismatch! Expected {len(audio_data)}, got {len(out_data)}"
        assert out_sr == sr, f"Sample rate mismatch! Expected {sr}, got {out_sr}"
        
        # Check B: Silence is actually zeroed
        # Because we added 50ms padding (0.05s * 16000 = 800 samples), 
        # the speech segment according to VAD will be roughly (speech_start - 800) to (speech_end + 800)
        # So anything before 0.3s and after 1.7s should be mathematically ZERO.
        
        test_zero_start = out_data[:int(0.2 * sr)]
        test_zero_end = out_data[int(1.8 * sr):]
        
        assert np.all(test_zero_start == 0.0), "Leading silence was not properly muted!"
        assert np.all(test_zero_end == 0.0), "Trailing silence was not properly muted!"
        
        print("✅ test_apply_vad_filter_length_and_muting PASSED")
        
    finally:
        # Cleanup
        if os.path.exists(input_wav):
            os.remove(input_wav)
        if os.path.exists(output_wav):
            os.remove(output_wav)

if __name__ == "__main__":
    test_apply_vad_filter_length_and_muting()
