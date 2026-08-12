import subprocess
import json
from pathlib import Path

def get_audio_stream_count(video_path):
    cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'stream=index', 
        '-select_streams', 'a', '-of', 'json', str(video_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return len(data.get('streams', []))

def extract_fix(video_path, output_path):
    count = get_audio_stream_count(video_path)
    print(f"Streams: {count}")
    
    # Generic mix filter
    if count > 1:
        # Use amix or amerge
        filter_str = f"amix=inputs={count},dynaudnorm,apad=pad_dur=2.0"
    else:
        filter_str = "dynaudnorm,apad=pad_dur=2.0"
        
    cmd = [
        'ffmpeg', '-y', '-i', str(video_path),
        '-vn', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2',
        '-af', filter_str, str(output_path)
    ]
    subprocess.run(cmd)

video = "uploads/CD~DAZN-408 OFFER_LG~ESE_CA~None_SZ~20s_1920x1080_PR~Peugeot-Peugeot 408_FM~Video_FF~1005947_13f308ab.mxf"
extract_fix(video, "test_fixed.wav")
