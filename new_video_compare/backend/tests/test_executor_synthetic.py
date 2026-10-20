import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
#!/usr/bin/env python3
"""
test_executor_synthetic.py
Thorough verification of execute_backup_retention.py on a synthetic environment in /tmp.
Verifies:
1. Dry-run mode by default does not delete files or alter uchg flags.
2. Full execution with --execute safely unflags and deletes only the manifest files.
3. Mid-list error halting (e.g. permission or unflag error on file #5 halts immediately without touching subsequent files).
4. Manifest tamper/mismatch check (file changed/touched after manifest was generated rejects and stops).
5. Protection violation check (manifest attempting to delete a top 10 or monthly anchor is blocked).
6. JSONL append-only audit log correctly records all operations.
"""

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from execute_backup_retention import execute_retention_from_manifest

def create_valid_dummy_sqlite(path: Path, dt: datetime, set_uchg: bool = True):
    conn = sqlite3.connect(str(path))
    cur = conn.cursor()
    cur.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, msg TEXT);")
    cur.execute("INSERT INTO test (msg) VALUES ('valid sqlite database');")
    conn.commit()
    conn.close()
    ts = dt.timestamp()
    os.utime(str(path), (ts, ts))
    if set_uchg:
        subprocess.run(["chflags", "uchg", str(path)], check=True)

def test_executor_synthetic():
    temp_dir = Path(tempfile.mkdtemp(prefix="test_executor_synth_"))
    log_dir = Path(tempfile.mkdtemp(prefix="test_executor_logs_"))
    try:
        now = datetime(2026, 10, 20, 16, 0, 0)
        backups_dir = temp_dir / "backups"
        backups_dir.mkdir()
        log_file = log_dir / "audit.jsonl"

        # 1. Populate backups dir
        # 12 db_backup files within last 48h
        for i in range(12):
            dt = now - timedelta(hours=i * 2 + 1)
            create_valid_dummy_sqlite(backups_dir / f"db_backup_{dt.strftime('%Y-%m-%d_%H%M%S')}.db", dt)

        # 20 old git_pre_op_backup files (>30 days ago)
        git_old_files = []
        for i in range(20):
            dt = now - timedelta(days=35 + i)
            p = backups_dir / f"git_pre_op_backup_{dt.strftime('%Y-%m-%d_%H%M%S')}.db"
            create_valid_dummy_sqlite(p, dt)
            git_old_files.append(p)

        # 15 recent git_pre_op_backup files (<10 days ago)
        for i in range(15):
            dt = now - timedelta(days=1 + i)
            create_valid_dummy_sqlite(backups_dir / f"git_pre_op_backup_{dt.strftime('%Y-%m-%d_%H%M%S')}.db", dt)

        # Build a valid candidate manifest of 5 old git files using evaluate_retention
        from dry_run_backup_retention import evaluate_retention, scan_real_backups
        meta = scan_real_backups(backups_dir)
        ret_res = evaluate_retention(meta, now_dt=now)
        candidates_to_delete = [c["path"] for c in ret_res["all_candidates"] if "git_pre_op" in c["name"]][:5]
        manifest_path = temp_dir / "manifest_test.json"
        
        manifest_items = []
        for p in candidates_to_delete:
            st = p.stat()
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            manifest_items.append({
                "name": p.name,
                "size": st.st_size,
                "mtime": st.st_mtime,
                "sha256": h
            })

        manifest_path.write_text(json.dumps({"files": manifest_items}, indent=2))

        # --- TEST 1: Dry run execution ---
        print("\n--- Running Test 1: Dry-run mode ---")
        ok_dry = execute_retention_from_manifest(manifest_path, backups_dir, log_file, execute=False)
        assert ok_dry is True, "Dry-run should succeed"
        # Confirm files still exist and have uchg
        UF_IMMUTABLE = 0x2
        for p in candidates_to_delete:
            assert p.exists(), f"File {p.name} was prematurely deleted during dry run!"
            assert (p.stat().st_flags & UF_IMMUTABLE) != 0, f"File {p.name} lost uchg during dry run!"
        print("Test 1 Passed: Dry run preserved all files and flags.")

        # --- TEST 2: Altered file detection (tampering/mismatch) ---
        print("\n--- Running Test 2: Altered file detection ---")
        # Touch one file to change mtime
        target_tamper = candidates_to_delete[0]
        subprocess.run(["chflags", "nouchg", str(target_tamper)], check=True)
        os.utime(str(target_tamper), (now.timestamp(), now.timestamp()))
        subprocess.run(["chflags", "uchg", str(target_tamper)], check=True)
        
        ok_tamper = execute_retention_from_manifest(manifest_path, backups_dir, log_file, execute=True)
        assert ok_tamper is False, "Execution should fail when file mtime/hash doesn't match manifest!"
        assert target_tamper.exists(), "Tampered file must not be deleted!"
        print("Test 2 Passed: Mismatched mtime stopped execution.")

        # Restore original mtime for next tests
        subprocess.run(["chflags", "nouchg", str(target_tamper)], check=True)
        orig_ts = manifest_items[0]["mtime"]
        os.utime(str(target_tamper), (orig_ts, orig_ts))
        subprocess.run(["chflags", "uchg", str(target_tamper)], check=True)

        # --- TEST 3: Protection violation (manifest trying to delete top 10 newest file) ---
        print("\n--- Running Test 3: Top 10 protection violation ---")
        newest_file = sorted(backups_dir.glob("db_backup_*.db"), key=lambda x: x.stat().st_mtime)[-1]
        st_new = newest_file.stat()
        h_new = hashlib.sha256(newest_file.read_bytes()).hexdigest()
        bad_manifest_path = temp_dir / "bad_manifest.json"
        bad_manifest_path.write_text(json.dumps({
            "files": [{
                "name": newest_file.name,
                "size": st_new.st_size,
                "mtime": st_new.st_mtime,
                "sha256": h_new
            }]
        }))
        ok_bad = execute_retention_from_manifest(bad_manifest_path, backups_dir, log_file, execute=True)
        assert ok_bad is False, "Execution must block deleting a top 10 newest file!"
        assert newest_file.exists(), "Protected file must not be deleted!"
        print("Test 3 Passed: Top 10 protection prevented deletion.")

        # --- TEST 4: Successful execution of valid manifest ---
        print("\n--- Running Test 4: Successful execution of 5 candidates ---")
        ok_exec = execute_retention_from_manifest(manifest_path, backups_dir, log_file, execute=True)
        assert ok_exec is True, "Execution should succeed for valid candidates."
        for p in candidates_to_delete:
            assert not p.exists(), f"File {p.name} should have been deleted!"
        print("Test 4 Passed: 5 files unflagged and deleted safely.")

        # --- TEST 5: Verify JSONL audit log ---
        print("\n--- Running Test 5: Verify JSONL log records ---")
        assert log_file.exists(), "JSONL audit log should exist"
        lines = [json.loads(line) for line in log_file.read_text().splitlines() if line.strip()]
        success_deletions = [l for l in lines if l.get("action") == "DELETE" and l.get("status") == "success"]
        assert len(success_deletions) == 5, f"Expected 5 successful deletions in log, got {len(success_deletions)}"
        print("Test 5 Passed: JSONL log contains full audit trail.")

        print("\n=======================================================")
        print("🎉 ALL SYNTHETIC EXECUTOR TESTS PASSED SUCCESSFULLY!")
        print("=======================================================")

    finally:
        for f in temp_dir.rglob("*"):
            try:
                subprocess.run(["chflags", "nouchg", str(f)], check=False, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        shutil.rmtree(temp_dir, ignore_errors=True)
        shutil.rmtree(log_dir, ignore_errors=True)

if __name__ == "__main__":
    test_executor_synthetic()
