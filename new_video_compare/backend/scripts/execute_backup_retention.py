#!/usr/bin/env python3
"""
execute_backup_retention.py
Retention executor tool with default dry-run mode and explicit --execute flag.
Safeguards:
- Accepts a JSON manifest containing exact files to delete with name, size, mtime, sha256.
- Verifies PRAGMA integrity_check on the latest db_backup_* before proceeding.
- Validates each file strictly:
  * Strict regex filename match
  * Exclusively located in ~/.cradle_data/backups (or synthetic test dir)
  * Regular file, not a symlink
  * Size, mtime and sha256 match manifest
  * Is not among the top 10 newest files overall
  * Is not a monthly anchor or protected reason
- Individual unflag (chflags nouchg) + single unlink (no rm -rf, no globs).
- Halts immediately upon any unexpected mismatch or error (fail-closed).
- Writes an append-only JSONL log of every operation outside the backups dir.
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dry_run_backup_retention import evaluate_retention, scan_real_backups, RE_DB_BACKUP, RE_GIT_BACKUP

logger = logging.getLogger("retention_executor")

def check_latest_db_integrity(backup_dir: Path) -> bool:
    """Read-only integrity check on the newest db_backup_* file."""
    db_files = sorted(
        [f for f in backup_dir.iterdir() if f.is_file() and not f.is_symlink() and RE_DB_BACKUP.match(f.name)],
        key=lambda x: x.stat().st_mtime
    )
    if not db_files:
        logger.error("No valid db_backup_*.db found to verify integrity!")
        return False
    latest = db_files[-1]
    logger.info(f"Checking integrity of latest backup: {latest.name} (read-only mode)...")
    try:
        uri = f"file:{latest.resolve()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        res = cur.fetchall()
        conn.close()
        if len(res) == 1 and res[0][0].lower() == "ok":
            logger.info("PRAGMA integrity_check passed: OK")
            return True
        logger.error(f"Integrity check failed: {res}")
        return False
    except Exception as e:
        logger.error(f"Error checking PRAGMA integrity_check: {e}")
        return False

def calculate_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()

def execute_retention_from_manifest(
    manifest_path: Path,
    backup_dir: Path,
    log_file: Path,
    execute: bool = False
) -> bool:
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    if not backup_dir.exists():
        raise FileNotFoundError(f"Backups directory not found: {backup_dir}")

    # Ensure log directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # 1. Integrity check on newest backup
    if not check_latest_db_integrity(backup_dir):
        logger.error("STOPPING: Latest backup integrity check failed or no backup exists.")
        return False

    # 2. Evaluate fresh live retention state to confirm anchors and top 10
    meta = scan_real_backups(backup_dir)
    retention_state = evaluate_retention(meta)
    kept_names = set(retention_state["kept_reasons"].keys())

    manifest_data = json.loads(manifest_path.read_text())
    target_files = manifest_data.get("files", [])
    logger.info(f"Loaded manifest with {len(target_files)} target files. Mode: {'EXECUTE' if execute else 'DRY-RUN'}")

    for idx, target in enumerate(target_files, 1):
        filename = target["name"]
        expected_size = target["size"]
        expected_mtime = target["mtime"]
        expected_sha = target.get("sha256")

        target_path = (backup_dir / filename).resolve()
        
        # Security & Boundary checks
        # Must be directly inside backup_dir
        if target_path.parent != backup_dir.resolve():
            logger.error(f"SECURITY VIOLATION: Path traversal detected for {target_path}")
            return False

        # Strict regex matching
        if not (RE_DB_BACKUP.match(filename) or RE_GIT_BACKUP.match(filename)):
            logger.error(f"REJECTED: Filename {filename} does not match strict backup regex.")
            return False

        # Regular file, not a symlink
        if not target_path.exists() or not target_path.is_file() or target_path.is_symlink():
            logger.error(f"REJECTED: {filename} does not exist, is not regular, or is a symlink.")
            return False

        # Verify not in KEPT / Top 10 / Monthly anchor
        if filename in kept_names:
            reasons = retention_state["kept_reasons"][filename]
            logger.error(f"PROTECTION VIOLATION: {filename} is protected under retention rules: {reasons}")
            return False

        # Size and mtime verification
        stat_res = target_path.stat()
        if stat_res.st_size != expected_size:
            logger.error(f"MISMATCH: Size of {filename} ({stat_res.st_size}) != manifest ({expected_size})")
            return False

        if abs(stat_res.st_mtime - expected_mtime) > 1.0:
            logger.error(f"MISMATCH: mtime of {filename} ({stat_res.st_mtime}) != manifest ({expected_mtime})")
            return False

        if expected_sha:
            actual_sha = calculate_sha256(target_path)
            if actual_sha != expected_sha:
                logger.error(f"MISMATCH: SHA-256 of {filename} ({actual_sha}) != manifest ({expected_sha})")
                return False

        # Log entry for JSONL
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "DELETE" if execute else "DRY_RUN_DELETE",
            "file": filename,
            "path": str(target_path),
            "size_bytes": stat_res.st_size,
            "mtime": stat_res.st_mtime,
            "sha256": expected_sha or calculate_sha256(target_path),
            "status": "pending"
        }

        if execute:
            try:
                # 1. Unflag uchg
                logger.info(f"[{idx}/{len(target_files)}] Unflagging uchg: {filename}")
                subprocess.run(["chflags", "nouchg", str(target_path)], check=True)
                
                # 2. Delete single file
                logger.info(f"[{idx}/{len(target_files)}] Deleting file: {filename}")
                target_path.unlink()
                log_entry["status"] = "success"
            except Exception as del_err:
                logger.error(f"ERROR deleting {filename}: {del_err}. Halting immediately.")
                log_entry["status"] = f"error: {del_err}"
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(json.dumps(log_entry) + "\n")
                return False
        else:
            logger.info(f"[DRY-RUN] [{idx}/{len(target_files)}] Would safely unflag and delete: {filename}")
            log_entry["status"] = "dry_run_verified"

        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(json.dumps(log_entry) + "\n")

    logger.info(f"Finished processing all {len(target_files)} files successfully.")
    return True

def main():
    parser = argparse.ArgumentParser(description="Backup retention execution tool.")
    parser.add_argument("--manifest", type=str, required=True, help="Path to JSON manifest")
    parser.add_argument("--backups-dir", type=str, default=str(Path.home() / ".cradle_data/backups"))
    parser.add_argument("--log-file", type=str, default=str(Path.home() / ".cradle_data/logs/retention_audit.jsonl"))
    parser.add_argument("--execute", action="store_true", help="Execute deletion (default is dry-run)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    ok = execute_retention_from_manifest(
        manifest_path=Path(args.manifest),
        backup_dir=Path(args.backups_dir),
        log_file=Path(args.log_file),
        execute=args.execute
    )
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
