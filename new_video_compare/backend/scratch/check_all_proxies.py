import sqlite3
import subprocess
import json
import os
from PIL import Image
import numpy as np

db_path = "new_video_compare.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get the last 10 MOV files that are processed
cursor.execute("""
    SELECT id, filename, is_processed, codec, file_metadata
    FROM files 
    WHERE filename LIKE '%.mov' AND is_processed = 1
    ORDER BY id DESC 
    LIMIT 10
""")

rows = cursor.fetchall()
print("--- PROXY STATUS ANALYSIS ---")
for row in rows:
    f_id, fname, processed, codec, meta = row
    stem = os.path.splitext(fname)[0]
    proxy_name = f"{stem}_proxy.mp4"
    proxy_path = os.path.join("uploads", "proxies", proxy_name)
    
    if not os.path.exists(proxy_path):
        print(f"ID {f_id} ({fname}): Proxy file does not exist on disk at {proxy_path}")
        continue
        
    # Extract a frame
    tmp_img = f"scratch/tmp_frame_{f_id}.png"
    cmd = ["ffmpeg", "-y", "-ss", "5.0", "-i", proxy_path, "-vframes", "1", tmp_img]
    
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        img = Image.open(tmp_img)
        gray = img.convert('L')
        gray_data = np.array(gray)
        
        total = gray_data.size
        black = np.sum(gray_data <= 10)
        pct_black = (black / total) * 100
        avg_brightness = np.mean(gray_data)
        
        is_black = pct_black > 99.5
        status_str = "💀 BLACK SCREEN" if is_black else "🎉 OK (HAS CONTENT)"
        
        print(f"ID {f_id} | {proxy_name} | {status_str} | Black: {pct_black:.2f}% | Avg Bright: {avg_brightness:.2f}")
        
        # Clean up
        if os.path.exists(tmp_img):
            os.remove(tmp_img)
            
    except Exception as e:
        print(f"ID {f_id} | Error processing: {e}")
        if os.path.exists(tmp_img):
            os.remove(tmp_img)

conn.close()
