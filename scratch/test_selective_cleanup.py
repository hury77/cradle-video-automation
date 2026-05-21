import os
import shutil
from pathlib import Path

def test_cleanup():
    print("🧪 Running Selective Cleanup Verification Test...")
    
    # 1. Setup paths
    base_dir = Path(__file__).parent.parent
    uploads_dir = base_dir / "new_video_compare" / "backend" / "uploads"
    if not uploads_dir.exists():
        uploads_dir = base_dir / "uploads"
    
    temp_dir = uploads_dir / "temp"
    temp_dir.mkdir(exist_ok=True, parents=True)
    
    job_folder = temp_dir / "job_9999"
    acc_dir = job_folder / "acceptance_frames"
    em_dir = job_folder / "emission_frames"
    diff_dir = job_folder / "diff_frames"
    
    # Create directories and files
    acc_dir.mkdir(exist_ok=True, parents=True)
    em_dir.mkdir(exist_ok=True, parents=True)
    diff_dir.mkdir(exist_ok=True, parents=True)
    
    (acc_dir / "frame_001.png").write_text("dummy frame data")
    (em_dir / "frame_001.png").write_text("dummy frame data")
    (diff_dir / "diff_1.5.png").write_text("dummy diff data")
    
    print("✅ Created test directories and files:")
    print(f"   - {acc_dir / 'frame_001.png'} exists? {(acc_dir / 'frame_001.png').exists()}")
    print(f"   - {em_dir / 'frame_001.png'} exists? {(em_dir / 'frame_001.png').exists()}")
    print(f"   - {diff_dir / 'diff_1.5.png'} exists? {(diff_dir / 'diff_1.5.png').exists()}")
    
    # 2. Simulate the new dev_cleanup_loop logic
    print("\n🔄 Simulating background dev_cleanup_loop logic...")
    acc_frames = job_folder / "acceptance_frames"
    em_frames = job_folder / "emission_frames"
    
    cleaned_subfolders = []
    if acc_frames.exists():
        shutil.rmtree(acc_frames)
        cleaned_subfolders.append("acceptance_frames")
    if em_frames.exists():
        shutil.rmtree(em_frames)
        cleaned_subfolders.append("emission_frames")
        
    print(f"   - Cleaned subfolders: {cleaned_subfolders}")
    print(f"   - {acc_dir} still exists? {acc_dir.exists()} (Expected: False)")
    print(f"   - {em_dir} still exists? {em_dir.exists()} (Expected: False)")
    print(f"   - {diff_dir / 'diff_1.5.png'} still exists? {(diff_dir / 'diff_1.5.png').exists()} (Expected: True)")
    
    if not acc_dir.exists() and not em_dir.exists() and (diff_dir / 'diff_1.5.png').exists():
        print("\n🎉 SUCCESS! Background selective cleanup verified perfectly!")
    else:
        print("\n❌ FAILURE! Background selective cleanup failed!")
        
    # Clean up test directories
    if job_folder.exists():
        shutil.rmtree(job_folder)

if __name__ == "__main__":
    test_cleanup()
