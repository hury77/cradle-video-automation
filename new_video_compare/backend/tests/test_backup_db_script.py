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
        status_file = fake_logs_dir / "backup_status_db_backup.json"
        legacy_status_file = fake_logs_dir / "backup_status.json"
        git_status_file = fake_logs_dir / "backup_status_git_pre_op_backup.json"
        GIT_HOOK_PATH = Path(__file__).parent.parent / "scripts/git_hook_backup.sh"

        conn = sqlite3.connect(str(fake_db))
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, msg TEXT);")
        conn.execute("INSERT INTO test (msg) VALUES ('initial row 1');")
        conn.commit()
        conn.close()

        # Utworzenie atrapowego osascript w mock_bin, aby nie wysylac prawdziwych powiadomien macOS
        mock_bin_dir = temp_root / "mock_bin"
        mock_bin_dir.mkdir(exist_ok=True)
        fake_osascript = mock_bin_dir / "osascript"
        osascript_log = temp_root / "osascript_calls.log"
        fake_script_content = "#!/bin/sh\necho \"$@\" >> \"" + str(osascript_log) + "\"\nexit 0\n"
        fake_osascript.write_text(fake_script_content)
        fake_osascript.chmod(0o755)

        env = os.environ.copy()
        env["PATH"] = str(mock_bin_dir) + ":" + env.get("PATH", "")
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
        # Przy 3 błędzie odpala się atrapowy osascript (weryfikujemy mocka i brak crasha)
        res_fail3 = subprocess.run(["python3", str(SCRIPT_PATH)], env=env_corrupt, capture_output=True, text=True)
        assert res_fail3.returncode != 0
        st_f3 = json.loads(status_file.read_text())
        assert st_f3["consecutive_failures"] == 3
        assert osascript_log.exists(), "Atrapowy osascript powinien zostać wywołany przy consecutive_failures >= 3"
        osascript_calls = osascript_log.read_text()
        assert "Cradle DB Backup Alert" in osascript_calls
        print("Scenario 6 Passed: consecutive_failures reached 3 and mock osascript received alert.")

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
        # Weryfikacja powiadomienia blokady w atrapowym osascript
        osascript_calls_after_10 = osascript_log.read_text()
        assert "Cradle DB Backup Blokada" in osascript_calls_after_10
        # Czyszczenie starych plików .tmp po teście blokady, aby nie blokować kolejnych scenariuszy
        tmp1.unlink()
        tmp2.unlink()
        tmp3.unlink()
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

        # --- 12. Test timeoutu osascript (TimeoutExpired nie przerywa działania ani nie zmienia kodu) ---
        print("\n--- Scenario 12: osascript timeout handling (TimeoutExpired) ---")
        slow_osascript = mock_bin_dir / "osascript"
        slow_osascript.write_text("#!/bin/sh\nsleep 2\nexit 0\n")
        slow_osascript.chmod(0o755)

        script_dir = str(SCRIPT_PATH.parent)
        test_timeout_code = """
import os, sys, time
sys.path.insert(0, """ + repr(script_dir) + """)
import backup_db
# Testujemy bezposrednio send_macos_notification z krotkim timeoutem 0.1s
t0 = time.time()
backup_db.send_macos_notification("Test Title", "Test Message", timeout=0.1)
elapsed = time.time() - t0
assert elapsed < 1.0, f"Notification call took too long: {elapsed}s"
print("Timeout handled gracefully.")
"""
        res_timeout = subprocess.run(["python3", "-c", test_timeout_code], env=env, capture_output=True, text=True)
        assert res_timeout.returncode == 0, f"Timeout test failed: {res_timeout.stderr}"
        print("Scenario 12 Passed: TimeoutExpired handled cleanly without altering execution.")

        # --- 13. Odrzucenie nieprawidłowego prefiksu CLI (kod 2) ---
        print("\n--- Scenario 13: Invalid CLI prefix rejected with exit code 2 ---")
        res13 = subprocess.run(["python3", str(SCRIPT_PATH), "--prefix", "invalid_prefix_"], env=env, capture_output=True, text=True)
        assert res13.returncode == 2, f"Expected exit code 2 for invalid prefix, got {res13.returncode}"
        print("Scenario 13 Passed: Invalid prefix rejected.")

        # --- 14. git_hook_backup.sh: Pierwszy zrzut i dedykowany status git_pre_op_backup ---
        print("\n--- Scenario 14: git_hook_backup.sh first run and separated status ---")
        time.sleep(1.1)
        res14 = subprocess.run(["bash", str(GIT_HOOK_PATH)], env=env, capture_output=True, text=True)
        assert res14.returncode == 0, f"git_hook_backup.sh failed: {res14.stderr}"
        git_backups14 = list(fake_backups_dir.glob("git_pre_op_backup_*.db"))
        assert len(git_backups14) == 1
        assert (git_backups14[0].stat().st_flags & UF_IMMUTABLE) != 0

        # Weryfikacja rozdzielenia statusów:
        assert git_status_file.exists(), "Hook Git musi utworzyć backup_status_git_pre_op_backup.json"
        st_git14 = json.loads(git_status_file.read_text())
        assert st_git14["result"] == "created"
        assert st_git14["last_successful_backup"] == git_backups14[0].name

        # Plik statusu db_backup_ nie może zostać zmieniony przez hooka
        st_db_prev = json.loads(status_file.read_text())
        assert "git_pre_op_backup" not in st_db_prev.get("last_successful_backup", "")
        print("Scenario 14 Passed: git_hook_backup.sh created backup with isolated status.")

        # --- 15. Deduplikacja per prefix: Hook dedupuje tylko po git_pre_op, a db_backup po db_backup ---
        print("\n--- Scenario 15: Deduplication isolated per prefix ---")
        time.sleep(1.1)
        # 15a. Hook na identycznej bazie -> skipped_duplicate w statusie git_pre_op
        res15a = subprocess.run(["bash", str(GIT_HOOK_PATH)], env=env, capture_output=True, text=True)
        assert res15a.returncode == 0
        assert len(list(fake_backups_dir.glob("git_pre_op_backup_*.db"))) == 1
        st_git15a = json.loads(git_status_file.read_text())
        assert st_git15a["result"] == "skipped_duplicate"
        assert st_git15a["consecutive_skips"] == 1

        # 15b. Cykliczny db_backup_ na identycznej bazie -> pomija względem db_backup_
        time.sleep(1.1)
        res15b = subprocess.run(["python3", str(SCRIPT_PATH)], env=env, capture_output=True, text=True)
        assert res15b.returncode == 0
        st_db15b = json.loads(status_file.read_text())
        assert st_db15b["result"] == "skipped_duplicate"

        # 15c. Zmiana bazy -> hook tworzy nową kopię git_pre_op
        time.sleep(1.1)
        conn = sqlite3.connect(str(fake_db))
        conn.execute("INSERT INTO test (msg) VALUES ('hook test row');")
        conn.commit()
        conn.close()

        res15c = subprocess.run(["bash", str(GIT_HOOK_PATH)], env=env, capture_output=True, text=True)
        assert res15c.returncode == 0
        assert len(list(fake_backups_dir.glob("git_pre_op_backup_*.db"))) == 2
        st_git15c = json.loads(git_status_file.read_text())
        assert st_git15c["result"] == "created"
        assert st_git15c["consecutive_skips"] == 0
        print("Scenario 15 Passed: Deduplication operates strictly within same prefix.")

        # --- 16. Propagacja błędu przez git_hook_backup.sh (uszkodzona baza) ---
        print("\n--- Scenario 16: git_hook_backup.sh propagates failure on corrupt DB ---")
        time.sleep(1.1)
        env_corrupt_hook = env.copy()
        env_corrupt_hook["DB_PATH"] = str(corrupt_db)
        res16 = subprocess.run(["bash", str(GIT_HOOK_PATH)], env=env_corrupt_hook, capture_output=True, text=True)
        assert res16.returncode != 0, "Hook Git musi zwrócić kod błędu przy awarii backupu"
        assert "BŁĄD BACKUPU" in res16.stderr
        st_git16 = json.loads(git_status_file.read_text())
        assert st_git16["result"] == "failed"
        assert "Integrity check failed" in st_git16["last_failure_reason"]
        print("Scenario 16 Passed: Failure correctly propagated by git_hook_backup.sh.")

        # --- 17. backup_status.py: Domyślny odczyt db_backup_, opcja --prefix oraz fallback legacy ---
        print("\n--- Scenario 17: backup_status.py prefix handling and legacy fallback ---")
        # 17a. Domyślne wywołanie sprawdza db_backup
        res17a = subprocess.run(["python3", str(STATUS_SCRIPT_PATH)], env=env, capture_output=True, text=True)
        assert res17a.returncode == 0
        assert "db_backup_" in res17a.stdout

        # 17b. Wywołanie z --prefix git_pre_op_backup_
        res17b = subprocess.run(["python3", str(STATUS_SCRIPT_PATH), "--prefix", "git_pre_op_backup_"], env=env, capture_output=True, text=True)
        assert "git_pre_op_backup" in res17b.stdout

        # 17c. Fallback do starego backup_status.json tylko gdy nowego pliku brak
        temp_legacy_root = Path(tempfile.mkdtemp(prefix="test_legacy_fallback_"))
        try:
            legacy_logs = temp_legacy_root / "logs"
            legacy_logs.mkdir()
            old_file = legacy_logs / "backup_status.json"
            old_file.write_text(json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "last_success_at": datetime.now(timezone.utc).isoformat(),
                "result": "created",
                "last_successful_backup": "legacy_db_backup.db",
                "consecutive_skips": 0,
                "consecutive_failures": 0
            }))
            env_legacy = env.copy()
            env_legacy["LOG_DIR"] = str(legacy_logs)
            res17c = subprocess.run(["python3", str(STATUS_SCRIPT_PATH)], env=env_legacy, capture_output=True, text=True)
            assert res17c.returncode == 0
            assert "legacy_db_backup.db" in res17c.stdout
            # Upewnij się, że nie utworzono automatycznie kopii/symlinku do starego pliku
            assert not (legacy_logs / "backup_status_db_backup.json").exists()
        finally:
            shutil.rmtree(temp_legacy_root, ignore_errors=True)

        print("Scenario 17 Passed: backup_status.py prefix resolution and legacy fallback verified.")

        # --- 18. Testy wrapperów w .githooks w środowisku izolowanym z atrapowym backupem ---
        print("\n--- Scenario 18: Testing .githooks wrappers exit codes and error handling ---")
        hook_test_dir = temp_root / "hook_wrapper_test"
        hook_test_dir.mkdir(exist_ok=True)
        fake_repo_dir = hook_test_dir / "new_video_compare/backend/scripts"
        fake_repo_dir.mkdir(parents=True, exist_ok=True)
        fake_hook_script = fake_repo_dir / "git_hook_backup.sh"

        repo_root = Path(__file__).parent.parent.parent.parent
        pre_merge_src = (repo_root / ".githooks/pre-merge-commit").read_text(encoding="utf-8")
        post_checkout_src = (repo_root / ".githooks/post-checkout").read_text(encoding="utf-8")

        test_pre_merge = hook_test_dir / "pre-merge-commit"
        test_post_checkout = hook_test_dir / "post-checkout"
        test_pre_merge.write_text(pre_merge_src, encoding="utf-8")
        test_post_checkout.write_text(post_checkout_src, encoding="utf-8")
        test_pre_merge.chmod(0o755)
        test_post_checkout.chmod(0o755)

        # 18a. Atrapowy backup zwracający błąd (exit 1)
        fake_hook_script.write_text("#!/bin/sh\necho \"Simulated backup failure\" >&2\nexit 1\n", encoding="utf-8")
        fake_hook_script.chmod(0o755)

        # pre-merge-commit musi propagować kod błędu 1 i wypisać blokadę merge
        res_pm_fail = subprocess.run(["bash", str(test_pre_merge)], cwd=str(hook_test_dir), capture_output=True, text=True)
        assert res_pm_fail.returncode == 1, f"pre-merge-commit should return code 1, got {res_pm_fail.returncode}"
        assert "Blokada utworzenia commitu merge" in res_pm_fail.stderr

        # post-checkout musi zwrócić kod 0, lecz wypisać ostrzeżenie na stderr
        res_pc_fail = subprocess.run(["bash", str(test_post_checkout)], cwd=str(hook_test_dir), capture_output=True, text=True)
        assert res_pc_fail.returncode == 0, f"post-checkout must return code 0 even on backup failure, got {res_pc_fail.returncode}"
        assert "OSTRZEŻENIE: Checkout powiódł się, lecz zrzut bezpieczeństwa" in res_pc_fail.stderr

        # 18b. Atrapowy backup zwracający sukces (exit 0)
        fake_hook_script.write_text("#!/bin/sh\necho \"Backup successful\"\nexit 0\n", encoding="utf-8")
        res_pm_ok = subprocess.run(["bash", str(test_pre_merge)], cwd=str(hook_test_dir), capture_output=True, text=True)
        assert res_pm_ok.returncode == 0
        assert "Blokada" not in res_pm_ok.stderr

        res_pc_ok = subprocess.run(["bash", str(test_post_checkout)], cwd=str(hook_test_dir), capture_output=True, text=True)
        assert res_pc_ok.returncode == 0
        assert "OSTRZEŻENIE" not in res_pc_ok.stderr

        print("Scenario 18 Passed: .githooks wrappers correctly propagate / handle exit codes.")

        print("\n🎉 ALL 18 UNIT AND SCENARIO TESTS PASSED SUCCESSFULLY!")

    finally:
        for f in temp_root.rglob("*"):
            try:
                subprocess.run(["chflags", "nouchg", str(f)], check=False, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        shutil.rmtree(temp_root, ignore_errors=True)

if __name__ == "__main__":
    test_backup_db_all_scenarios()
