#!/usr/bin/env python3
"""
test_backup_db_script.py
Kompleksowe testy jednostkowe i scenariuszowe dla scripts/backup_db.py.
Uruchamiane w pelni w katalogu izolowanym /tmp.
"""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

SCRIPT_PATH = Path(__file__).parent.parent / "scripts/backup_db.py"

def test_backup_db_all_scenarios():
    temp_root = Path(tempfile.mkdtemp(prefix="test_backup_db_full_"))
    try:
        fake_db = temp_root / "new_video_compare.db"
        fake_backups_dir = temp_root / "backups"
        fake_logs_dir = temp_root / "logs"
        status_file = fake_logs_dir / "backup_status.json"

        conn = sqlite3.connect(str(fake_db))
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, msg TEXT);")
        conn.execute("INSERT INTO test (msg) VALUES ('initial row 1');")
        conn.commit()
        conn.close()

        env = os.environ.copy()
        env["DB_PATH"] = str(fake_db)
        env["BACKUPS_DIR"] = str(fake_backups_dir)
        env["LOG_DIR"] = str(fake_logs_dir)

        UF_IMMUTABLE = 0x2

        # 1. Pierwsze utworzenie i status
        res1 = subprocess.run(["python3", str(SCRIPT_PATH)], env=env, capture_output=True, text=True)
        assert res1.returncode == 0, f"Run 1 failed: {res1.stderr}"
        backups1 = list(fake_backups_dir.glob("db_backup_*.db"))
        assert len(backups1) == 1
        assert (backups1[0].stat().st_flags & UF_IMMUTABLE) != 0
        st1 = json.loads(status_file.read_text())
        assert st1["result"] == "created"
        assert st1["consecutive_skips"] == 0
        first_backup = st1["last_successful_backup"]

        # 2. Identyczna baza (pominięcie + consecutive_skips = 1)
        time.sleep(1.1)
        res2 = subprocess.run(["python3", str(SCRIPT_PATH)], env=env, capture_output=True, text=True)
        assert res2.returncode == 0
        assert len(list(fake_backups_dir.glob("db_backup_*.db"))) == 1
        st2 = json.loads(status_file.read_text())
        assert st2["result"] == "skipped_duplicate"
        assert st2["consecutive_skips"] == 1
        assert st2["last_successful_backup"] == first_backup

        # 3. Ponowne pominięcie (consecutive_skips = 2)
        time.sleep(1.1)
        res3 = subprocess.run(["python3", str(SCRIPT_PATH)], env=env, capture_output=True, text=True)
        assert res3.returncode == 0
        st3 = json.loads(status_file.read_text())
        assert st3["result"] == "skipped_duplicate"
        assert st3["consecutive_skips"] == 2

        # 4. Zmiana bazy -> utworzenie nowej kopii i reset consecutive_skips do 0
        time.sleep(1.1)
        conn = sqlite3.connect(str(fake_db))
        conn.execute("INSERT INTO test (msg) VALUES ('new row 2');")
        conn.commit()
        conn.close()

        res4 = subprocess.run(["python3", str(SCRIPT_PATH)], env=env, capture_output=True, text=True)
        assert res4.returncode == 0
        assert len(list(fake_backups_dir.glob("db_backup_*.db"))) == 2
        st4 = json.loads(status_file.read_text())
        assert st4["result"] == "created"
        assert st4["consecutive_skips"] == 0
        assert st4["last_successful_backup"] != first_backup

        # 5. Ostrzeżenie przy 1-2 starych .tmp (>1h)
        now_ts = time.time()
        stale_ts = now_ts - 7200
        tmp1 = fake_backups_dir / "stale_1.tmp"
        tmp2 = fake_backups_dir / "stale_2.tmp"
        tmp1.write_bytes(b"tmp 1")
        tmp2.write_bytes(b"tmp 2")
        os.utime(str(tmp1), (stale_ts, stale_ts))
        os.utime(str(tmp2), (stale_ts, stale_ts))

        time.sleep(1.1)
        res5 = subprocess.run(["python3", str(SCRIPT_PATH)], env=env, capture_output=True, text=True)
        out5 = res5.stdout + res5.stderr
        assert "Wykryto 2 porzuconych plików *.tmp" in out5
        assert tmp1.exists() and tmp2.exists()

        # 6. Blokada fail-closed przy >= 3 starych .tmp (>1h)
        tmp3 = fake_backups_dir / "stale_3.tmp"
        tmp3.write_bytes(b"tmp 3")
        os.utime(str(tmp3), (stale_ts, stale_ts))

        time.sleep(1.1)
        res6 = subprocess.run(["python3", str(SCRIPT_PATH)], env=env, capture_output=True, text=True)
        assert res6.returncode != 0
        out6 = res6.stdout + res6.stderr
        assert "BLOKADA FAIL-CLOSED" in out6
        st6 = json.loads(status_file.read_text())
        assert st6["result"] == "failed"
        assert "Blocked by >= 3 stale .tmp files" in st6["error"]

        print("ALL BACKUP_DB UNIT AND SCENARIO TESTS PASSED!")

    finally:
        for f in temp_root.rglob("*"):
            try:
                subprocess.run(["chflags", "nouchg", str(f)], check=False, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        shutil.rmtree(temp_root, ignore_errors=True)

if __name__ == "__main__":
    test_backup_db_all_scenarios()
