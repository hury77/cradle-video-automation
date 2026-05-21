import subprocess
import json

proxy_path = "uploads/proxies/119422_973016_New dish range PACS (eml_0219)_260123QGMT_Product Video - Modular_40s- 16x9_Hungarian (HU)_ccf3d80e_proxy.mp4"

cmd = [
    "ffprobe",
    "-v", "quiet",
    "-print_format", "json",
    "-show_format",
    "-show_streams",
    proxy_path
]

try:
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    probe_data = json.loads(result.stdout)
    
    print("--- PROXY FILE PROBE ---")
    if "streams" in probe_data:
        for stream in probe_data["streams"]:
            print(f"Type: {stream.get('codec_type')}")
            print(f"  Codec: {stream.get('codec_name')}")
            print(f"  Profile: {stream.get('profile')}")
            print(f"  Width: {stream.get('width')}")
            print(f"  Height: {stream.get('height')}")
            print(f"  Pix Format: {stream.get('pix_fmt')}")
            print(f"  Duration: {stream.get('duration')}")
            print("-" * 20)
    else:
        print("No streams found!")
except Exception as e:
    print(f"Error probing file: {e}")
