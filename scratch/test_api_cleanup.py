import os
import shutil
from pathlib import Path
import httpx

def test_api_cleanup():
    print("🧪 Running API `/cleanup` Selective Cleanup Verification Test...")
    
    # 1. Setup paths
    base_dir = Path(__file__).parent.parent
    uploads_dir = base_dir / "new_video_compare" / "backend" / "uploads"
    temp_dir = uploads_dir / "temp"
    temp_dir.mkdir(exist_ok=True, parents=True)
    
    # --- Case A: Active Job (559 exists in the DB) ---
    job_active = temp_dir / "job_559"
    acc_active = job_active / "acceptance_frames"
    em_active = job_active / "emission_frames"
    diff_active = job_active / "diff_frames"
    
    acc_active.mkdir(exist_ok=True, parents=True)
    em_active.mkdir(exist_ok=True, parents=True)
    diff_active.mkdir(exist_ok=True, parents=True)
    
    (acc_active / "frame_001.png").write_text("dummy frame data")
    (em_active / "frame_001.png").write_text("dummy frame data")
    (diff_active / "diff_1.5.png").write_text("dummy diff data")
    
    # --- Case B: Deleted Job (99999 does not exist in DB) ---
    job_deleted = temp_dir / "job_99999"
    acc_deleted = job_deleted / "acceptance_frames"
    em_deleted = job_deleted / "emission_frames"
    diff_deleted = job_deleted / "diff_frames"
    
    acc_deleted.mkdir(exist_ok=True, parents=True)
    em_deleted.mkdir(exist_ok=True, parents=True)
    diff_deleted.mkdir(exist_ok=True, parents=True)
    
    (acc_deleted / "frame_001.png").write_text("dummy frame data")
    (em_deleted / "frame_001.png").write_text("dummy frame data")
    (diff_deleted / "diff_1.5.png").write_text("dummy diff data")
    
    print("\n✅ Setup active (559) and inactive (99999) dummy jobs in temp dir.")
    
    # 2. Invoke the live API /cleanup endpoint via HTTP
    url = "http://127.0.0.1:8001/api/v1/dashboard/cleanup"
    params = {"days": 100, "count": 10} # high days threshold so we don't accidentally clean actual recent jobs from DB
    
    print(f"📡 Sending DELETE request to: {url} with params {params}")
    try:
        response = httpx.delete(url, params=params, timeout=10.0)
        print(f"📥 API Response status: {response.status_code}")
        print(f"📥 API Response text: {response.text[:200]}")
        print(f"📥 API Response JSON: {response.json()}")
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
    
    # 3. Verify results
    print("\n🔍 Verifying cleanup outcomes:")
    
    # Job 559 (Active):
    print("\nActive Job (559):")
    print(f"  - {acc_active} still exists? {acc_active.exists()} (Expected: False)")
    print(f"  - {em_active} still exists? {em_active.exists()} (Expected: False)")
    print(f"  - {diff_active / 'diff_1.5.png'} still exists? {(diff_active / 'diff_1.5.png').exists()} (Expected: True)")
    
    # Job 99999 (Inactive/Deleted):
    print("\nDeleted Job (99999):")
    print(f"  - {job_deleted} still exists? {job_deleted.exists()} (Expected: False)")
    
    success_active = (not acc_active.exists() and not em_active.exists() and (diff_active / 'diff_1.5.png').exists())
    success_deleted = (not job_deleted.exists())
    
    if success_active and success_deleted:
        print("\n🎉 SUCCESS! API selective cleanup verified perfectly!")
    else:
        print("\n❌ FAILURE! API selective cleanup outcomes did not match expectations!")

if __name__ == "__main__":
    test_api_cleanup()
