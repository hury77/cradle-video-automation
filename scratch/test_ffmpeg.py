import subprocess
import os
import shutil

video_path = "/Users/hubert.rycaj/Documents/cradle-video-automation/new_video_compare/backend/uploads/AV-EGZO000216-0030_ARPP_334085ad.mp4"
ffmpeg_path = "ffmpeg"

# 1. Test BEFORE -i
dir_before = "/Users/hubert.rycaj/Documents/cradle-video-automation/scratch/test_before"
if os.path.exists(dir_before):
    shutil.rmtree(dir_before)
os.makedirs(dir_before, exist_ok=True)

cmd_before = [
    ffmpeg_path, "-hwaccel", "auto", "-nostdin",
    "-ss", "10.0",
    "-i", video_path,
    "-t", "1.0",
    "-vf", "scale=1280:1280:force_original_aspect_ratio=decrease,fps=1.0",
    "-y", os.path.join(dir_before, "frame_%06d.png")
]
print("Running command with -ss before -i...")
subprocess.run(cmd_before, capture_output=True)
files_before = sorted(os.listdir(dir_before))
print("Before files:", files_before)
if files_before:
    size_before = os.path.getsize(os.path.join(dir_before, files_before[0]))
    print("First frame size (before):", size_before)

# 2. Test AFTER -i
dir_after = "/Users/hubert.rycaj/Documents/cradle-video-automation/scratch/test_after"
if os.path.exists(dir_after):
    shutil.rmtree(dir_after)
os.makedirs(dir_after, exist_ok=True)

cmd_after = [
    ffmpeg_path, "-hwaccel", "auto", "-nostdin",
    "-i", video_path,
    "-ss", "10.0",
    "-t", "1.0",
    "-vf", "scale=1280:1280:force_original_aspect_ratio=decrease,fps=1.0",
    "-y", os.path.join(dir_after, "frame_%06d.png")
]
print("Running command with -ss after -i...")
subprocess.run(cmd_after, capture_output=True)
files_after = sorted(os.listdir(dir_after))
print("After files:", files_after)
if files_after:
    size_after = os.path.getsize(os.path.join(dir_after, files_after[0]))
    print("First frame size (after):", size_after)

# Let's write a small analysis to see if they are identical
if files_before and files_after:
    same_size = (size_before == size_after)
    print("Are the file sizes identical?", same_size)
