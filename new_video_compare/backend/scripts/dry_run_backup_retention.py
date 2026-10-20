#!/usr/bin/env python3
"""
dry_run_backup_retention.py
Dry-run simulator for ~/.cradle_data/backups retention policy.
Does NOT delete, move, or change flags on any files.
"""

import os
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

# Strict regex patterns (exact full filename match)
RE_DB_BACKUP = re.compile(r"^db_backup_\d{4}-\d{2}-\d{2}_\d{6}\.db$")
RE_GIT_BACKUP = re.compile(r"^git_pre_op_backup_\d{4}-\d{2}-\d{2}_\d{6}\.db$")

def parse_filename_time(filename: str) -> datetime:
    """Extract timestamp from filename to protect against corrupted system mtime."""
    # Format: db_backup_YYYY-MM-DD_HHMMSS.db or git_pre_op_backup_YYYY-MM-DD_HHMMSS.db
    m = re.search(r"(\d{4}-\d{2}-\d{2}_\d{6})", filename)
    if m:
        return datetime.strptime(m.group(1), "%Y-%m-%d_%H%M%S")
    raise ValueError(f"Cannot parse timestamp from filename: {filename}")

def evaluate_retention(files_metadata: list, now_dt: datetime = None, limit_per_run: int = 10):
    """
    Evaluates backup retention according to specified policy:
    1. Always keep 10 latest files overall (across all valid backup files).
    2. db_backup_*:
       - keep all from last 48 hours (0 - 2 days);
       - keep 1 per day for days 2 to 14;
       - keep 1 per week (7-day calendar bucket or ISO week) for weeks 3 to 8 (days 15 to 56);
       - eligible for deletion if older and not bucket-selected.
    3. git_pre_op_backup_*:
       - keep 10 latest git_pre_op backups;
       - keep all from last 14 days;
       - eligible for deletion if older and not in latest 10.
    4. Unrecognized files (e.g. manual backups):
       - ALWAYS PRESERVED (fail-closed, never delete unknown filenames).
    5. Limit deletions per run:
       - Up to limit_per_run files (FIFO: oldest candidates first).

    files_metadata: list of dicts with keys:
      'path': Path or str,
      'name': str,
      'size': int,
      'mtime': float,
      'dt': datetime
    """
    if now_dt is None:
        now_dt = datetime.now()

    # Filter only valid regular files
    items = list(files_metadata)
    # Sort strictly by timestamp ascending (oldest first)
    items.sort(key=lambda x: x["dt"])

    kept_reasons = {}   # name -> set of reasons
    candidates_to_delete = []

    def mark_keep(item, reason):
        name = item["name"]
        if name not in kept_reasons:
            kept_reasons[name] = set()
        kept_reasons[name].add(reason)

    # 1. Global Rule: ALWAYS keep the 10 newest files overall
    newest_10_overall = items[-10:] if len(items) >= 10 else items
    for it in newest_10_overall:
        mark_keep(it, "GLOBAL: Top 10 newest files overall")

    # Separate by type
    db_files = [it for it in items if RE_DB_BACKUP.match(it["name"])]
    git_files = [it for it in items if RE_GIT_BACKUP.match(it["name"])]
    other_files = [it for it in items if not RE_DB_BACKUP.match(it["name"]) and not RE_GIT_BACKUP.match(it["name"])]

    # Unknown files: never delete
    for it in other_files:
        mark_keep(it, "SAFETY: Unrecognized / manual backup format (fail-closed)")

    # 2. git_pre_op_backup_* policy
    # 2a. 10 newest git_pre_op
    for it in git_files[-10:]:
        mark_keep(it, "GIT: Top 10 newest git_pre_op backups")

    # 2b. All from last 14 days
    cutoff_14d = now_dt.timestamp() - 14 * 86400
    for it in git_files:
        if it["dt"].timestamp() >= cutoff_14d:
            mark_keep(it, "GIT: Within last 14 days")

    # Future dates protection
    for it in items:
        if it["dt"] > now_dt:
            mark_keep(it, "SAFETY: Timestamp is in the future (anomaly protection)")

    # 3. db_backup_* policy
    # - all within last 48h
    cutoff_48h = now_dt.timestamp() - 48 * 3600
    for it in db_files:
        if it["dt"].timestamp() >= cutoff_48h:
            mark_keep(it, "DB: Within last 48 hours")

    # - 1 per day for days 2 to 14 (between 48h and 14 days)
    # Group by calendar day (YYYY-MM-DD), keep the latest of each day
    day_buckets = {}
    cutoff_14d_dt = now_dt.timestamp() - 14 * 86400
    for it in db_files:
        ts = it["dt"].timestamp()
        if cutoff_14d_dt <= ts < cutoff_48h:
            day_key = it["dt"].strftime("%Y-%m-%d")
            if day_key not in day_buckets or it["dt"] > day_buckets[day_key]["dt"]:
                day_buckets[day_key] = it

    for day_key, it in day_buckets.items():
        mark_keep(it, f"DB: Daily retain bucket ({day_key}) [days 2-14]")

    # - 1 per week for weeks 3 to 8 (between 14 days and 56 days)
    # Group by ISO year + week (YYYY-Www), keep latest of each week
    cutoff_56d_dt = now_dt.timestamp() - 56 * 86400
    week_buckets = {}
    for it in db_files:
        ts = it["dt"].timestamp()
        if cutoff_56d_dt <= ts < cutoff_14d_dt:
            year, week, _ = it["dt"].isocalendar()
            week_key = f"{year}-W{week:02d}"
            if week_key not in week_buckets or it["dt"] > week_buckets[week_key]["dt"]:
                week_buckets[week_key] = it

    for week_key, it in week_buckets.items():
        mark_keep(it, f"DB: Weekly retain bucket ({week_key}) [weeks 3-8]")

    # 4. Monthly Anchor Rule: Always keep the OLDEST copy of each calendar month
    # Applied separately for db_backup_* and git_pre_op_backup_*
    month_anchors_db = {}
    for it in db_files:
        month_key = it["dt"].strftime("%Y-%m")
        if month_key not in month_anchors_db or it["dt"] < month_anchors_db[month_key]["dt"]:
            month_anchors_db[month_key] = it
    for month_key, it in month_anchors_db.items():
        mark_keep(it, f"ANCHOR: Oldest db_backup of month ({month_key})")

    month_anchors_git = {}
    for it in git_files:
        month_key = it["dt"].strftime("%Y-%m")
        if month_key not in month_anchors_git or it["dt"] < month_anchors_git[month_key]["dt"]:
            month_anchors_git[month_key] = it
    for month_key, it in month_anchors_git.items():
        mark_keep(it, f"ANCHOR: Oldest git_pre_op of month ({month_key})")

    # Identify all deletion candidates
    all_candidates = []
    for it in items:
        if it["name"] not in kept_reasons:
            all_candidates.append(it)

    # Sort deletion candidates oldest first (FIFO)
    all_candidates.sort(key=lambda x: x["dt"])
    eligible_in_this_run = all_candidates[:limit_per_run]
    eligible_deferred = all_candidates[limit_per_run:]

    return {
        "items": items,
        "kept_reasons": kept_reasons,
        "all_candidates": all_candidates,
        "eligible_in_this_run": eligible_in_this_run,
        "eligible_deferred": eligible_deferred,
    }

def scan_real_backups(backup_dir: Path):
    if not backup_dir.exists():
        raise FileNotFoundError(f"Directory not found: {backup_dir}")

    files_metadata = []
    for entry in backup_dir.iterdir():
        # Only regular files, NO symlinks
        if not entry.is_file() or entry.is_symlink():
            continue
        try:
            dt = parse_filename_time(entry.name)
        except ValueError:
            dt = datetime.fromtimestamp(entry.stat().st_mtime)

        files_metadata.append({
            "path": entry,
            "name": entry.name,
            "size": entry.stat().st_size,
            "mtime": entry.stat().st_mtime,
            "dt": dt
        })
    return files_metadata

if __name__ == "__main__":
    b_dir = Path(os.path.expanduser("~/.cradle_data/backups"))
    meta = scan_real_backups(b_dir)
    res = evaluate_retention(meta)

    total_files = len(meta)
    total_size = sum(f["size"] for f in meta)
    
    kept_files = [f for f in meta if f["name"] in res["kept_reasons"]]
    kept_size = sum(f["size"] for f in kept_files)
    
    cand_files = res["all_candidates"]
    cand_size = sum(f["size"] for f in cand_files)
    
    run_files = res["eligible_in_this_run"]
    run_size = sum(f["size"] for f in run_files)

    print("=" * 80)
    print(" DRY RUN BACKUP RETENTION SIMULATION (~/.cradle_data/backups)")
    print("=" * 80)
    print(f"Total backups scanned:      {total_files} ({total_size / (1024**3):.2f} GiB)")
    print(f"Total files to KEEP:        {len(kept_files)} ({kept_size / (1024**3):.2f} GiB)")
    print(f"Total candidates to DELETE: {len(cand_files)} ({cand_size / (1024**3):.2f} GiB)")
    print(f"Limit for current run:      {len(run_files)} files ({run_size / (1024**3):.2f} GiB)")
    print("=" * 80)

    print("\nFILES TO DELETE IN THIS RUN (limit 10, oldest first):")
    for idx, f in enumerate(run_files, 1):
        dt_str = f["dt"].strftime("%Y-%m-%d %H:%M:%S")
        sz_mb = f["size"] / (1024**2)
        print(f"  {idx:2d}. [DEL] {f['name']} ({sz_mb:6.1f} MB) - Date: {dt_str}")

    if res["eligible_deferred"]:
        print(f"\nDEFERRED CANDIDATES (to be deleted in subsequent runs, total {len(res['eligible_deferred'])}):")
        for idx, f in enumerate(res["eligible_deferred"][:10], 1):
            dt_str = f["dt"].strftime("%Y-%m-%d %H:%M:%S")
            sz_mb = f["size"] / (1024**2)
            print(f"  +{idx:2d}. [DEFERRED] {f['name']} ({sz_mb:6.1f} MB) - Date: {dt_str}")
        if len(res["eligible_deferred"]) > 10:
            print(f"      ... and {len(res['eligible_deferred']) - 10} more files")

    print("\nFILES TO KEEP (Summary sample):")
    for f in kept_files[-15:]:
        reasons = "; ".join(sorted(res["kept_reasons"][f["name"]]))
        dt_str = f["dt"].strftime("%Y-%m-%d %H:%M:%S")
        print(f"  [KEEP] {f['name']} ({f['size']/(1024**2):5.1f} MB) [{dt_str}] -> {reasons}")
