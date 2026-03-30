import sys
import os
import time
import logging
import torch
import mlx_whisper
import whisper
from pathlib import Path

# Add backend to path (if not already managed by shell)
sys.path.append("/Users/hubert.rycaj/Documents/cradle-video-automation/new_video_compare/backend")

def compare_engines():
    sample_wav = "/Users/hubert.rycaj/Documents/cradle-video-automation/new_video_compare/backend/uploads/118468_JEEP_COMPASS_THE_GREAT_PRETENDERS_FEVEREIRO_TVC_30s_PTE_3ebc9640.wav"
    
    if not os.path.exists(sample_wav):
        print(f"❌ Sample file not found")
        return

    print(f"\nComparing STT Engines on M4 for: {Path(sample_wav).name}")
    print("=" * 60)

    # 1. Standard OpenAI Whisper (CPU - PyTorch)
    print("\n[Engine 1] Standard Whisper (CPU - PyTorch)...")
    start1 = time.time()
    model_std = whisper.load_model("small")
    res_std = model_std.transcribe(sample_wav, fp16=False)
    dur1 = time.time() - start1
    text_std = res_std.get("text", "").strip()
    print(f"⏱️  Time (CPU): {dur1:.2f}s")

    # 2. MLX Whisper (Neural Engine - Quantized)
    print("\n[Engine 2] MLX Whisper (Neural Engine - M4 Optimized 4-bit)...")
    start2 = time.time()
    res_mlx = mlx_whisper.transcribe(sample_wav, path_or_hf_repo="mlx-community/whisper-small-mlx")
    dur2 = time.time() - start2
    text_mlx = res_mlx.get("text", "").strip()
    print(f"⏱️  Time (M4): {dur2:.2f}s")

    # 3. Final Comparison
    print("\n" + "=" * 60)
    print("RESULTS COMPARISON:")
    print(f"Similarity Score: {100.0 if text_std == text_mlx else 0.0}% Match")
    
    if text_std == text_mlx:
        print("✅ Text is IDENTICAL.")
    else:
        import difflib
        diff = list(difflib.ndiff([text_std], [text_mlx]))
        print("⚠️ Small differences detected:")
        print(f"Standard: {text_std[:150]}...")
        print(f"MLX-M4:   {text_mlx[:150]}...")
        # print("Diff detail:", "".join(diff))

if __name__ == "__main__":
    compare_engines()
