#!/usr/bin/env python3
"""
test_backup_db_script.py
Kompleksowe testy jednostkowe i scenariuszowe dla:
- scripts/backup_db.py
- scripts/backup_status.py
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
from datetime import datetime, timezone, timedelta

SCRIPT_PATH = Path(__file__).parent.parent / "scripts/backup_db.py"
STATUS_SCRIPT_PATH = Path(__file__).parent.parent / "scripts/backup_status.py"

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

        # --- 1. Pierwsze utworzenie i status ---
        print("\n--- Scenario 1: First run (created) ---")
        res1 = subprocess.run(["python3", str(SCRIPT_PATH)], env=env, capture_output=True, text=True)
        assert res1.returncode == 0, f"Run 1 failed: {res1.stderr}"
        backups1 = list(fake_backups_dir.glob("db_backup_*.db"))
        assert len(backups1) == 1
        assert (backups1[0].stat().st_flags & UF_IMMUTABLE) != 0
        st1 = json.loads(status_file.read_text())
        assert st1["result"] == "created"
        assert st1["consecutive_skips"] == 0
        assert st1["consecutive_failures"] == 0
        assert st1["last_failure_at"] is None
        first_backup = st1["last_successful_backup"]
        print("Scenario 1 Passed.")

        # --- 2. Identyczna baza (pominięcie + consecutive_skips = 1) ---
        print("\n--- Scenario 2: Identical database (dedup skip) ---")
        time.sleep(1.1)
        res2 = subprocess.run(["python3", str(SCRIPT_PATH)], env=env, capture_output=True, text=True)
        assert res2.returncode == 0
        assert len(list(fake_backups_dir.glob("db_backup_*.db"))) == 1
        st2 = json.loads(status_file.read_text())
        assert st2["result"] == "skipped_duplicate"
        assert st2["consecutive_skips"] == 1
        assert st2["consecutive_failures"] == 0
        assert st2["last_successful_backup"] == first_backup
        print("Scenario 2 Passed.")

        # --- 3. Ponowne pominięcie (consecutive_skips = 2) ---
        print("\n--- Scenario 3: Another dedup skip ---")
        time.sleep(1.1)
        res3 = subprocess.run(["python3", str(SCRIPT_PATH)], env=env, capture_output=True, text=True)
        assert res3.returncode == 0
        st3 = json.loads(status_file.read_text())
        assert st3["result"] == "skipped_duplicate"
        assert st3["consecutive_skips"] == 2
        assert st3["consecutive_failures"] == 0
        print("Scenario 3 Passed.")

        # --- 4. Zmiana bazy -> reset consecutive_skips do 0 ---
        print("\n--- Scenario 4: Database modified ---")
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
        assert st4["consecutive_failures"] == 0
        assert st4["last_successful_backup"] != first_backup
        print("Scenario 4 Passed.")

        # --- 5. Uszkodzona baza (Błąd integralności PRAGMA integrity_check) ---
        print("\n--- Scenario 5: Corrupted DB integrity check ---")
        time.sleep(1.1)
        corrupt_db = temp_root / "corrupted_real.db"
        shutil.copy2(fake_db, corrupt_db)
        with open(corrupt_db, "r+b") as fp:
            fp.seek(100)
            fp.write(b"\x00\x00\x00\x00\xff\xff\xff\xff" * 16)

        env_corrupt = env.copy()
        env_corrupt["DB_PATH"] = str(corrupt_db)

        res_corr = subprocess.run(["python3", str(SCRIPT_PATH)], env=env_corrupt, capture_output=True, text=True)
        assert res_corr.returncode != 0, "Corrupted DB must exit with error code"
        out_corr = res_corr.stdout + res_corr.stderr
        assert ("SKORUMPOWANY BACKUP" in out_corr or "Błąd integralności bazy" in out_corr)
        st_corr = json.loads(status_file.read_text())
        assert st_corr["result"] == "failed"
        assert st_corr["consecutive_failures"] == 1
        assert st_corr["last_failure_at"] is not None
        assert "Integrity check failed" in st_corr["last_failure_reason"]
        # Upewnij się, że nie utworzono uszkodzonego pliku finalnego z uchg
        corrupt_final = list(fake_backups_dir.glob("db_backup_*corrupted*"))
        assert len(corrupt_final) == 0
        print("Scenario 5 Passed.")

        # --- 6. Kolejne błędy i powiadomienie osascript (consecutive_failures >= 3) ---
        print("\n--- Scenario 6: Consecutive failures tracking and alert ---")
        time.sleep(1.1)
        res_fail2 = subprocess.run(["python3", str(SCRIPT_PATH)], env=env_corrupt, capture_output=True, text=True)
        assert res_fail2.returncode != 0
        st_f2 = json.loads(status_file.read_text())
        assert st_f2["consecutive_failures"] == 2

        time.sleep(1.1)
        # Przy 3 błędzie odpala się kod osascript (weryfikujemy, że skrypt nie wywala się i loguje stan)
        res_fail3 = subprocess.run(["python3", str(SCRIPT_PATH)], env=env_corrupt, capture_output=True, text=True)
        assert res_fail3.returncode != 0
        st_f3 = json.loads(status_file.read_text())
        assert st_f3["consecutive_failures"] == 3
        print("Scenario 6 Passed: consecutive_failures reached 3 without crashing.")

        # --- 7. Powrót do zdrowej bazy -> reset consecutive_failures i last_failure ---
        print("\n--- Scenario 7: Recovery resets failure counters ---")
        time.sleep(1.1)
        res_rec = subprocess.run(["python3", str(SCRIPT_PATH)], env=env, capture_output=True, text=True)
        assert res_rec.returncode == 0
        st_rec = json.loads(status_file.read_text())
        assert st_rec["consecutive_failures"] == 0
        assert st_rec["last_failure_at"] is None
        assert st_rec["last_failure_reason"] is None
        print("Scenario 7 Passed.")

        # --- 8. Błąd haszowania w dedup (Fail-closed: nowa kopia powstaje mimo błędu) ---
        print("\n--- Scenario 8: Dedup hashing error triggers fail-closed backup ---")
        time.sleep(1.1)
        conn = sqlite3.connect(str(fake_db))
        conn.execute("INSERT INTO test (msg) VALUES ('row 3 for dedup error');")
        conn.commit()
        conn.close()

        test_fail_closed_code = f"""
import os, sys
sys.path.insert(0, "{SCRIPT_PATH.parent}")
os.environ["DB_PATH"] = "{fake_db}"
os.environ["BACKUPS_DIR"] = "{fake_backups_dir}"
os.environ["LOG_DIR"] = "{fake_logs_dir}"

import backup_db

orig_calc = backup_db.calculate_sha256
def faulty_calc(p):
    if "tmp" not in str(p):
        raise RuntimeError("Simulated hashing error on existing backup!")
    return orig_calc(p)

backup_db.calculate_sha256 = faulty_calc
ok = backup_db.run_backup()
assert ok is True, "Backup must succeed fail-closed even when dedup comparison fails"
"""
        res8 = subprocess.run(["python3", "-c", test_fail_closed_code], capture_output=True, text=True)
        assert res8.returncode == 0, f"Fail-closed test failed: {res8.stderr}"
        backups8 = list(fake_backups_dir.glob("db_backup_*.db"))
        # Było 2 backupy w katalogu, po fail-closed musi być 3
        assert len(backups8) == 3, f"Expected 3 backups, got {len(backups8)}"
        print("Scenario 8 Passed: Backup cleanly created despite hashing error.")

        # --- 9. Ostrzeżenie przy 1-2 starych .tmp (>1h) ---
        print("\n--- Scenario 9: Stale .tmp warning (<3) ---")
        now_ts = time.time()
        stale_ts = now_ts - 7200
        tmp1 = fake_backups_dir / "stale_1.tmp"
        tmp2 = fake_backups_dir / "stale_2.tmp"
        tmp1.write_bytes(b"tmp 1")
        tmp2.write_bytes(b"tmp 2")
        os.utime(str(tmp1), (stale_ts, stale_ts))
        os.utime(str(tmp2), (stale_ts, stale_ts))

        time.sleep(1.1)
        res9 = subprocess.run(["python3", str(SCRIPT_PATH)], env=env, capture_output=True, text=True)
        out9 = res9.stdout + res9.stderr
        assert "Wykryto 2 porzuconych plików *.tmp" in out9
        assert tmp1.exists() and tmp2.exists()
        print("Scenario 9 Passed.")

        # --- 10. Blokada fail-closed przy >= 3 starych .tmp (>1h) ---
        print("\n--- Scenario 10: Stale .tmp block (>=3) ---")
        tmp3 = fake_backups_dir / "stale_3.tmp"
        tmp3.write_bytes(b"tmp 3")
        os.utime(str(tmp3), (stale_ts, stale_ts))

        time.sleep(1.1)
        res10 = subprocess.run(["python3", str(SCRIPT_PATH)], env=env, capture_output=True, text=True)
        assert res10.returncode != 0
        out10 = res10.stdout + res10.stderr
        assert "BLOKADA FAIL-CLOSED" in out10
        st10 = json.loads(status_file.read_text())
        assert st10["result"] == "failed"
        assert "Blocked by >= 3 stale .tmp files" in st10["last_failure_reason"]
        print("Scenario 10 Passed.")

        # --- 11. Testy backup_status.py (monitoring statusu) ---
        print("\n--- Scenario 11: Testing backup_status.py inspection tool ---")
        # 11a. Test dla zdrowego stanu
        healthy_status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "last_success_at": datetime.now(timezone.utc).isoformat(),
            "result": "skipped_duplicate",
            "last_successful_backup": "db_backup_2026-10-21_100000.db",
            "consecutive_skips": 1,
            "consecutive_failures": 0
        }
        status_file.write_text(json.dumps(healthy_status))
        res_stat1 = subprocess.run(["python3", str(STATUS_SCRIPT_PATH), "--status-file", str(status_file)], capture_output=True, text=True)
        assert res_stat1.returncode == 0, f"Expected 0 for healthy status, got {res_stat1.returncode}"
        assert "STATUS: ZDROWY (OK)" in res_stat1.stdout

        # 11b. Test dla cyklu starszego niż 12h
        old_time = (datetime.now(timezone.utc) - timedelta(hours=13)).isoformat()
        stale_status = healthy_status.copy()
        stale_status["last_success_at"] = old_time
        status_file.write_text(json.dumps(stale_status))
        res_stat2 = subprocess.run(["python3", str(STATUS_SCRIPT_PATH), "--status-file", str(status_file)], capture_output=True, text=True)
        assert res_stat2.returncode != 0, "Expected non-zero exit for stale backup >12h"
        assert "starszy niż 12h" in res_stat2.stdout

        # 11c. Test dla consecutive_failures >= 3
        fail_status = healthy_status.copy()
        fail_status["consecutive_failures"] = 3
        status_file.write_text(json.dumps(fail_status))
        res_stat3 = subprocess.run(["python3", str(STATUS_SCRIPT_PATH), "--status-file", str(status_file)], capture_output=True, text=True)
        assert res_stat3.returncode != 0, "Expected non-zero exit for consecutive_failures >= 3"
        assert "Zbyt wiele kolejnych awarii" in res_stat3.stdout

        print("Scenario 11 Passed: backup_status.py correctly validates healthy and unhealthy states.")

        print("\n🎉 ALL 11 UNIT AND SCENARIO TESTS PASSED SUCCESSFULLY!")

    finally:
        for f in temp_root.rglob("*"):
            try:
                subprocess.run(["chflags", "nouchg", str(f)], check=False, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        shutil.rmtree(temp_root, ignore_errors=True)

if __name__ == "__main__":
    test_backup_db_all_scenarios()
