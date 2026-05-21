import threading
import time
import sys
import os

# Add the backend to sys.path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "new_video_compare", "backend"))

from services.audio_service import transcribe_single_file
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(threadName)s - %(name)s - %(levelname)s - %(message)s"
)

# Use a small existing video file from uploads
file_path = "new_video_compare/backend/uploads/260122RGRA_SE_16M6vWS_0893d656.mp4"

def run_transcription(label):
    print(f"[{label}] Thread started, calling transcribe_single_file...")
    try:
        # We set use_source_separation=False to speed up the test and focus strictly on Whisper concurrency
        result = transcribe_single_file(
            file_path,
            language="sv",  # Swedish based on filename SE
            model_name="tiny",  # Use tiny model for quick load and test
            use_source_separation=False,
            label=label
        )
        print(f"[{label}] Finished! Word count: {result.get('transcript', {}).get('word_count', 0)}")
    except Exception as e:
        print(f"[{label}] ERROR: {e}")

# Start two concurrent threads running the transcription pipeline on the same system
t1 = threading.Thread(target=run_transcription, args=("thread-A",), name="Thread-A")
t2 = threading.Thread(target=run_transcription, args=("thread-B",), name="Thread-B")

print("Starting Thread-A...")
t1.start()

# Wait 500ms before starting Thread-B to simulate overlapping concurrent requests
time.sleep(0.5)
print("Starting Thread-B...")
t2.start()

# Wait for both to finish
t1.join()
t2.join()

print("All threads finished successfully!")
