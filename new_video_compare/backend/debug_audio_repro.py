
import sys
import os
import traceback
from pathlib import Path
import numpy as np

# Add backend to path
backend_dir = Path("/Users/hubert.rycaj/Documents/cradle-video-automation/new_video_compare/backend")
sys.path.insert(0, str(backend_dir))

from services.audio_service import compare_loudness, compare_audio_similarity, separate_sources, compare_voiceovers

file1 = "/Users/hubert.rycaj/Documents/cradle-video-automation/new_video_compare/backend/uploads/118699_963296_CITROEN_ITALY_CTV_SUV_C5_AC_FEBRUARY_2026_30s_XR_PA_SMlFZwf_44f7400b.mp4"
file2 = "/Users/hubert.rycaj/Documents/cradle-video-automation/new_video_compare/backend/uploads/118699_CITROEN_ITALY_CTV_SUV_C5_AC_FEBRUARY_2026_30s_PA_a99ae7b0.mov"

print(f"Testing files:\n1: {file1}\n2: {file2}")

def safe_run(name, func, *args, **kwargs):
    print(f"\n--- Testing {name} ---")
    try:
        res = func(*args, **kwargs)
        print("Result:", res)
        return res
    except Exception:
        traceback.print_exc()
        return None

# Basic tests
safe_run("compare_loudness", compare_loudness, file1, file2)
safe_run("compare_audio_similarity", compare_audio_similarity, file1, file2)

# Advanced tests (potential failure points)
sep1 = safe_run("separate_sources (file1)", separate_sources, file1)
sep2 = safe_run("separate_sources (file2)", separate_sources, file2)

if sep1 and sep2 and "vocals" in sep1.get("sources", {}) and "vocals" in sep2.get("sources", {}):
    vocals1 = sep1["sources"]["vocals"]["path"]
    vocals2 = sep2["sources"]["vocals"]["path"]
    safe_run("compare_voiceovers", compare_voiceovers, vocals1, vocals2)

