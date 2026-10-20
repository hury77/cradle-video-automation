import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
#!/usr/bin/env python3
"""
test_synthetic_retention.py
Unit and scenario tests for backup retention logic on synthetic directories in /tmp.
Tests:
1. Strict filename regex matching (regular files only, ignores non-matching or symlinks).
2. Global rule: top 10 newest files overall preserved regardless of age.
3. db_backup_*: preserves <48h, 1/day (2-14d), 1/week (3-8w), deletes older non-bucketed.
4. git_pre_op_backup_*: preserves top 10 newest + all within 14 days, deletes older.
5. Limit of 10 deletions per run (FIFO: oldest deleted first).
6. Future date anomaly protection (files with future mtime/timestamp are preserved).
7. Flag uchg handling: verify that files created with `chflags uchg` can be detected and
   safely manipulated in dry-run without altering flags.
"""

import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from dry_run_backup_retention import evaluate_retention, scan_real_backups

def test_retention_synthetic():
    temp_dir = Path(tempfile.mkdtemp(prefix="test_retention_synth_"))
    try:
        now = datetime(2026, 10, 20, 15, 0, 0)
        
        # Helper to generate a dummy file with specific datetime
        def create_dummy(name: str, dt: datetime, size_bytes: int = 1024, set_uchg: bool = False):
            p = temp_dir / name
            p.write_bytes(b"0" * size_bytes)
            ts = dt.timestamp()
            os.utime(str(p), (ts, ts))
            if set_uchg:
                subprocess.run(["chflags", "uchg", str(p)], check=True)
            return p

        # 1. Create a future dated file
        create_dummy("db_backup_2026-11-01_120000.db", now + timedelta(days=12), set_uchg=True)
        create_dummy("git_pre_op_backup_2026-11-05_120000.db", now + timedelta(days=16), set_uchg=True)

        # 2. Create 15 db_backup files within last 48h
        for h in range(15):
            dt = now - timedelta(hours=h * 2 + 1)
            create_dummy(f"db_backup_{dt.strftime('%Y-%m-%d_%H%M%S')}.db", dt, set_uchg=True)

        # 3. Create db_backup files between 2 and 14 days (several per day)
        for day in range(3, 10):
            # create 2 backups per day
            dt1 = now - timedelta(days=day, hours=4)
            dt2 = now - timedelta(days=day, hours=10)
            create_dummy(f"db_backup_{dt1.strftime('%Y-%m-%d_%H%M%S')}.db", dt1, set_uchg=True)
            create_dummy(f"db_backup_{dt2.strftime('%Y-%m-%d_%H%M%S')}.db", dt2, set_uchg=True)

        # 4. Create db_backup files older than 8 weeks (e.g. 70 days ago)
        for d in range(65, 75):
            dt = now - timedelta(days=d)
            create_dummy(f"db_backup_{dt.strftime('%Y-%m-%d_%H%M%S')}.db", dt, set_uchg=True)

        # 5. Create 25 git_pre_op_backup files: 15 very old (>30 days), 10 recent (<10 days)
        for d in range(35, 50):
            dt = now - timedelta(days=d)
            create_dummy(f"git_pre_op_backup_{dt.strftime('%Y-%m-%d_%H%M%S')}.db", dt, set_uchg=True)
        for d in range(1, 11):
            dt = now - timedelta(days=d, hours=3)
            create_dummy(f"git_pre_op_backup_{dt.strftime('%Y-%m-%d_%H%M%S')}.db", dt, set_uchg=True)

        # 6. Create unrecognized / manual files and symlinks
        manual_p = create_dummy("manual_snapshot.db", now - timedelta(days=100), set_uchg=True)
        # Symlink pointing to a db file
        symlink_p = temp_dir / "symlink_backup.db"
        try:
            symlink_p.symlink_to(manual_p)
        except OSError:
            pass

        # Scan synthetic directory
        meta = scan_real_backups(temp_dir)
        eval_res = evaluate_retention(meta, now_dt=now, limit_per_run=10)

        kept_names = set(eval_res["kept_reasons"].keys())

        # Assertions
        # 1. Symlinks must NOT be in scan results
        assert all(not f["path"].is_symlink() for f in meta), "Symlinks should not be scanned"

        # 2. Future files MUST be kept
        assert "db_backup_2026-11-01_120000.db" in kept_names, "Future db backup must be kept"
        assert "git_pre_op_backup_2026-11-05_120000.db" in kept_names, "Future git backup must be kept"

        # 3. Manual unrecognized files must be kept (fail-closed)
        assert "manual_snapshot.db" in kept_names, "Unrecognized backup must be safely kept"

        # 4. Limit per run must be exactly 10
        assert len(eval_res["eligible_in_this_run"]) == 10, f"Limit per run should be 10, got {len(eval_res['eligible_in_this_run'])}"

        # 5. Oldest candidates are prioritized in FIFO order
        run_candidates = eval_res["eligible_in_this_run"]
        for i in range(len(run_candidates) - 1):
            assert run_candidates[i]["dt"] <= run_candidates[i+1]["dt"], "Candidates must be sorted oldest-first"

        # 6. In days 3-9, exactly 1 file per day was kept for db_backup
        kept_days = [eval_res["kept_reasons"][f["name"]] for f in meta if "Daily retain bucket" in str(eval_res["kept_reasons"].get(f["name"], ""))]
        assert len(kept_days) == 7, f"Expected 7 daily kept backups, got {len(kept_days)}"

        # 7. uchg flags remain intact
        UF_IMMUTABLE = 0x2
        for f in temp_dir.glob("*.db"):
            if not f.is_symlink():
                assert (f.stat().st_flags & UF_IMMUTABLE) != 0, f"File {f.name} lost its uchg flag during evaluation!"

        print("✅ ALL SYNTHETIC TESTS PASSED SUCCESSFULLY!")
        print(f"Total synthetic files evaluated: {len(meta)}")
        print(f"Total kept: {len(kept_names)}, Total deletion candidates: {len(eval_res['all_candidates'])}")
        print(f"Eligible in this run (limit 10): {len(eval_res['eligible_in_this_run'])}")

    finally:
        # Cleanup: unflag uchg before rmtree so directory can be removed
        for f in temp_dir.glob("*"):
            try:
                subprocess.run(["chflags", "nouchg", str(f)], check=False, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    test_retention_synthetic()
