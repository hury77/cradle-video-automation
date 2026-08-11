import pytest
import threading
import time
import shutil
import subprocess
from pathlib import Path

from services.audio_service import transcribe_single_file

@pytest.mark.integration
@pytest.mark.slow
def test_whisper_concurrency(tmp_path):
    # Graceful skip if ffmpeg is not available
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not found in PATH. Skipping Whisper integration test.")
        
    # Generate a dummy 1-second silent MP4 file using ffmpeg
    dummy_video_path = tmp_path / "dummy_silence.mp4"
    try:
        subprocess.run([
            "ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
            "-t", "1", "-c:a", "aac", "-y", str(dummy_video_path)
        ], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        pytest.skip(f"Failed to generate dummy audio with ffmpeg: {e.stderr.decode('utf-8')}")
        
    # Ensure file exists
    assert dummy_video_path.exists(), "Dummy video file was not created."

    # Thread result storage
    results = {}
    exceptions = {}

    def run_transcription(label):
        try:
            # We set use_source_separation=False to speed up the test and focus strictly on Whisper concurrency
            result = transcribe_single_file(
                str(dummy_video_path),
                language="sv",  # arbitrary language
                model_name="tiny",  # Use tiny model for quick load and test
                use_source_separation=False,
                label=label
            )
            results[label] = result
        except Exception as e:
            exceptions[label] = e

    # Start two concurrent threads running the transcription pipeline on the same system
    t1 = threading.Thread(target=run_transcription, args=("thread-A",), name="Thread-A")
    t2 = threading.Thread(target=run_transcription, args=("thread-B",), name="Thread-B")

    t1.start()
    
    # Wait 500ms before starting Thread-B to simulate overlapping concurrent requests
    time.sleep(0.5)
    t2.start()

    # Wait for both to finish
    t1.join()
    t2.join()

    # Hard assertions: no exceptions should have been raised in threads
    assert "thread-A" not in exceptions, f"Thread-A raised exception: {exceptions['thread-A']}"
    assert "thread-B" not in exceptions, f"Thread-B raised exception: {exceptions['thread-B']}"
    
    # Check if we got valid result dicts back
    assert "thread-A" in results, "Thread-A did not return a result"
    assert "thread-B" in results, "Thread-B did not return a result"
    
    assert isinstance(results["thread-A"], dict)
    assert isinstance(results["thread-B"], dict)
    
    # We do not assert exact word count since the audio is silent, but we assert the structure is valid
    assert "transcript" in results["thread-A"]
    assert "transcript" in results["thread-B"]
