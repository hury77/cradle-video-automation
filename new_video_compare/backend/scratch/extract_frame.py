import subprocess

proxy_path = "uploads/proxies/119422_973016_New dish range PACS (eml_0219)_260123QGMT_Product Video - Modular_40s- 16x9_Hungarian (HU)_ccf3d80e_proxy.mp4"
out_img_path = "/Users/hubert.rycaj/.gemini/antigravity-ide/brain/4bcb4b93-98b6-4ae4-a7af-1d34456e0f54/extracted_frame.png"

# Run ffmpeg to extract frame at 5.0 seconds (to avoid any initial black frames in the video itself)
cmd = [
    "ffmpeg",
    "-y",
    "-ss", "5.0",
    "-i", proxy_path,
    "-vframes", "1",
    out_img_path
]

try:
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    print("✅ Frame successfully extracted!")
    print(result.stdout)
except Exception as e:
    print(f"❌ Error extracting frame: {e}")
    if hasattr(e, 'stderr'):
        print(f"Stderr: {e.stderr}")
