"""
Offline Replay Tool for Deterministic Decision Engine v1.

SAFETY & COMPLIANCE RULES:
- Pure read-only inspection tool: NO imports of SQLAlchemy, models, database,
  AnalystService, Ollama, network libraries, or Cradle API.
- Zero DDL/DML statements:
  * Tool performs EXCLUSIVELY SELECT and PRAGMA queries.
  * ZERO CREATE, INSERT, UPDATE, DELETE, DROP statements anywhere in the codebase.
- Strictly guards DB connection:
  * Prohibits path pointing to active production DB (~/.cradle_data/new_video_compare.db).
  * Requires valid, regular, non-symlink file ending with .db.
  * Connects strictly via SQLite URI mode=ro.
  * Verifies connection URI contains mode=ro.
- Output directory MUST be strictly located within /tmp (or macOS /private/tmp, tempfile dirs).
- Strict data redaction and ephemeral salt:
  * Uses secrets.token_bytes(32) generated in-memory per-run for anonymized IDs.
  * Salt is NEVER written to JSON, CSV, stdout, or filenames.
  * IDs are stable and unique within a single run, but change across runs.
  * ZERO client names, file paths, job names, cradle_ids, raw transcripts,
    reasoning, ai_reasoning, or error_message strings in generated reports.
- Categorization:
  * AGREEMENT
  * DETERMINISTIC_REVIEW
  * DETERMINISTIC_REJECT
  * DANGEROUS_FALSE_APPROVE
  * INSUFFICIENT_HISTORICAL_METRICS
"""

import argparse
import csv
import hashlib
import json
import math
import os
import secrets
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Pure engine & adapter imports
current_script_dir = Path(__file__).resolve().parent
backend_dir = current_script_dir.parent
sys.path.insert(0, str(backend_dir))

from services.deterministic_metrics_adapter import adapt_comparison_metrics
from services.deterministic_decision_engine import (
    DeterministicDecisionEngineV1,
    CANONICAL_FAST_PATH_IDENTICAL_AUDIO,
    CANONICAL_FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH,
    CANONICAL_NO_AUDIO_STREAMS,
)


CAT_AGREEMENT = "AGREEMENT"
CAT_DETERMINISTIC_REVIEW = "DETERMINISTIC_REVIEW"
CAT_DETERMINISTIC_REJECT = "DETERMINISTIC_REJECT"
CAT_DANGEROUS_FALSE_APPROVE = "DANGEROUS_FALSE_APPROVE"
CAT_INSUFFICIENT_METRICS = "INSUFFICIENT_HISTORICAL_METRICS"


def _is_valid_number(val: Any) -> bool:
    """Check if value is a finite float or int (not None, NaN, inf, or bool)."""
    if val is None or isinstance(val, bool):
        return False
    if not isinstance(val, (int, float)):
        return False
    return not (math.isnan(val) or math.isinf(val))


def _is_exact_bool(val: Any) -> bool:
    """Check if value is strictly of type bool."""
    return isinstance(val, bool)


def validate_db_path(db_path_str: str) -> Path:
    """
    Strict safety check on input database path.
    Rejects symlinks, non-files, invalid extensions, non-existent files,
    and the live ~/.cradle_data/new_video_compare.db database.
    """
    if not db_path_str.endswith(".db"):
        raise ValueError("Ścieżka bazy danych musi kończyć się rozszerzeniem '.db'.")

    p = Path(db_path_str).expanduser()

    # Block live production database
    live_prod_path = Path("~/.cradle_data/new_video_compare.db").expanduser().resolve()
    try:
        resolved_p = p.resolve()
    except Exception:
        resolved_p = None

    if resolved_p and resolved_p == live_prod_path:
        raise ValueError(
            "BEZPIECZEŃSTWO: Odmowa uruchomienia na aktywnej produkcyjnej bazie ~/.cradle_data/new_video_compare.db."
        )

    # Check symlink before following
    if os.path.islink(p):
        raise ValueError("BEZPIECZEŃSTWO: Plik bazy danych nie może być symlinkiem.")

    if not p.exists():
        raise FileNotFoundError(f"Plik bazy danych nie istnieje: {p}")

    if not p.is_file():
        raise ValueError(f"Ścieżka nie wskazuje na plik regularny: {p}")

    return p.resolve()


def validate_output_dir(output_dir_str: str) -> Path:
    """
    Enforces that output reports are strictly saved under /tmp (or system temporary directory).
    """
    out_path = Path(output_dir_str).expanduser().resolve()
    allowed_temp_roots = [
        Path("/tmp").resolve(),
        Path(tempfile.gettempdir()).resolve(),
    ]

    is_under_tmp = False
    for root in allowed_temp_roots:
        try:
            out_path.relative_to(root)
            is_under_tmp = True
            break
        except ValueError:
            continue

    if not is_under_tmp:
        raise ValueError(
            f"BEZPIECZEŃSTWO: Katalog wyjściowy musi znajdować się wewnątrz /tmp. Podano: {out_path}"
        )

    out_path.mkdir(parents=True, exist_ok=True)
    return out_path


def open_readonly_connection(db_file: Path) -> sqlite3.Connection:
    """
    Opens an SQLite connection in enforced read-only mode using URI file:<path>?mode=ro.
    Verifies that the URI contains mode=ro.
    Performs ZERO DDL / DML operations.
    """
    uri = f"file:{db_file}?mode=ro"
    if "mode=ro" not in uri:
        raise ValueError("KRYTYCZNY BŁĄD WEJŚCIA: URI połączenia musi zawierać mode=ro.")

    conn = sqlite3.connect(uri, uri=True)

    # Query PRAGMA query_only solely for informational / debug inspection
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA query_only")
        _ = cursor.fetchone()
        cursor.close()
    except Exception:
        pass

    return conn


def check_snapshot_completeness(canonical_metrics: Dict[str, Any]) -> Tuple[bool, Dict[str, bool]]:
    """
    Tightened verification of record completeness in strict mode.
    Returns (is_complete, completeness_flags).

    A. Always required:
       - video_similarity (valid number 0.0..1.0)
       - duration_difference (valid number >= 0.0)
       - is_arpp_slate (exact bool)
       - is_binary_duplicate (exact bool)
       - audio_mismatch (exact bool)
       - no_audio_tracks (exact bool)
       - acc_has_audio (exact bool)
       - emi_has_audio (exact bool)

    B. If audio_pair_comparable (both files have audio and no mismatch):
       - audio_similarity (valid number 0.0..1.0)
       - lufs_difference (valid number)
       - STT payload (dict with status and is_uncertain as exact bool)

    C. For completed_no_speech or legacy completed with 0 words:
       Full suite of Raw VAD fields required:
       - raw_vad_metrics_complete is True
       - raw_vad_error in (False, None)
       - raw_vad_inconclusive is False
       - raw_vad_speech is False
       - raw_vad_status_acc == "no_speech"
       - raw_vad_status_emi == "no_speech"
       - raw_vad_speech_acc is False
       - raw_vad_speech_emi is False
       - music_dominant is False

    D. For skipped STT:
       - canonical skipped_reason matching allowlist
       - if FAST_PATH: audio_similarity >= 0.98, lufs_difference valid
       - if FULL_MODE: complete Raw VAD fields
       - if NO_AUDIO_STREAMS: strictly DOOH/both-silent only
    """
    flags: Dict[str, bool] = {
        "has_video_similarity": _is_valid_number(canonical_metrics.get("video_similarity"))
        and (0.0 <= float(canonical_metrics["video_similarity"]) <= 1.0),
        "has_duration_difference": _is_valid_number(canonical_metrics.get("duration_difference"))
        and (float(canonical_metrics["duration_difference"]) >= 0.0),
        "has_is_arpp_slate": _is_exact_bool(canonical_metrics.get("is_arpp_slate")),
        "has_is_binary_duplicate": _is_exact_bool(canonical_metrics.get("is_binary_duplicate")),
        "has_audio_probe": (
            _is_exact_bool(canonical_metrics.get("audio_mismatch"))
            and _is_exact_bool(canonical_metrics.get("no_audio_tracks"))
            and _is_exact_bool(canonical_metrics.get("acc_has_audio"))
            and _is_exact_bool(canonical_metrics.get("emi_has_audio"))
        ),
        "has_audio_similarity": False,
        "has_lufs": False,
        "has_stt_payload": False,
        "has_raw_vad_complete": False,
    }

    # Step A: Universal base checks
    if not (
        flags["has_video_similarity"]
        and flags["has_duration_difference"]
        and flags["has_is_arpp_slate"]
        and flags["has_is_binary_duplicate"]
        and flags["has_audio_probe"]
    ):
        return False, flags

    no_audio = canonical_metrics.get("no_audio_tracks") is True
    audio_mismatch = canonical_metrics.get("audio_mismatch") is True
    acc_audio = canonical_metrics.get("acc_has_audio") is True
    emi_audio = canonical_metrics.get("emi_has_audio") is True

    # If both files lack audio (DOOH / silent)
    if no_audio and not acc_audio and not emi_audio and not audio_mismatch:
        flags["has_lufs"] = True
        flags["has_audio_similarity"] = True
        flags["has_stt_payload"] = True
        flags["has_raw_vad_complete"] = True
        return True, flags

    # If stream mismatch (one has audio, other does not)
    if audio_mismatch:
        flags["has_lufs"] = True
        flags["has_audio_similarity"] = True
        flags["has_stt_payload"] = True
        flags["has_raw_vad_complete"] = True
        return True, flags

    # Step B: Audio pair is comparable
    audio_pair_comparable = acc_audio and emi_audio and not audio_mismatch and not no_audio
    if not audio_pair_comparable:
        return False, flags

    aud_sim = canonical_metrics.get("audio_similarity")
    flags["has_audio_similarity"] = _is_valid_number(aud_sim) and (0.0 <= float(aud_sim) <= 1.0)

    loudness = canonical_metrics.get("audio_loudness")
    raw_lufs = loudness.get("lufs_difference") if isinstance(loudness, dict) else canonical_metrics.get("lufs_difference")
    flags["has_lufs"] = _is_valid_number(raw_lufs)

    stt = canonical_metrics.get("audio_transcription")
    stt_valid = (
        isinstance(stt, dict)
        and stt.get("status") is not None
        and _is_exact_bool(stt.get("is_uncertain"))
    )
    flags["has_stt_payload"] = stt_valid

    if not (flags["has_audio_similarity"] and flags["has_lufs"] and flags["has_stt_payload"]):
        return False, flags

    # Step C & D: Branch-specific completeness
    stt_status = stt.get("status")
    w_a = stt.get("word_count_a")
    w_b = stt.get("word_count_b")
    text_a = str(stt.get("acceptance_text", "")).strip()
    text_b = str(stt.get("emission_text", "")).strip()

    is_no_speech = (
        stt_status == "completed_no_speech"
        or (stt_status == "completed" and text_a == "" and text_b == "" and w_a == 0 and w_b == 0)
    )

    if is_no_speech:
        raw_vad_complete = (
            canonical_metrics.get("raw_vad_metrics_complete") is True
            and canonical_metrics.get("raw_vad_error") in (False, None)
            and canonical_metrics.get("raw_vad_inconclusive") is False
            and canonical_metrics.get("raw_vad_speech") is False
            and canonical_metrics.get("raw_vad_status_acc") == "no_speech"
            and canonical_metrics.get("raw_vad_status_emi") == "no_speech"
            and canonical_metrics.get("raw_vad_speech_acc") is False
            and canonical_metrics.get("raw_vad_speech_emi") is False
            and canonical_metrics.get("music_dominant") is False
        )
        flags["has_raw_vad_complete"] = raw_vad_complete
        return raw_vad_complete, flags

    if stt_status == "skipped":
        raw_reason = stt.get("skipped_reason") or canonical_metrics.get("stt_skipped_reason")
        if not raw_reason or not isinstance(raw_reason, str):
            return False, flags

        # Canonical skip reason checks
        if CANONICAL_FAST_PATH_IDENTICAL_AUDIO in raw_reason:
            flags["has_raw_vad_complete"] = True
            return True, flags
        elif CANONICAL_FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH in raw_reason:
            raw_vad_complete = (
                canonical_metrics.get("raw_vad_metrics_complete") is True
                and canonical_metrics.get("raw_vad_error") in (False, None)
                and canonical_metrics.get("raw_vad_inconclusive") is False
                and canonical_metrics.get("raw_vad_speech") is False
                and canonical_metrics.get("raw_vad_status_acc") == "no_speech"
                and canonical_metrics.get("raw_vad_status_emi") == "no_speech"
                and canonical_metrics.get("raw_vad_speech_acc") is False
                and canonical_metrics.get("raw_vad_speech_emi") is False
                and canonical_metrics.get("music_dominant") is False
            )
            flags["has_raw_vad_complete"] = raw_vad_complete
            return raw_vad_complete, flags
        elif CANONICAL_NO_AUDIO_STREAMS in raw_reason:
            # Valid only if actually silent DOOH (already handled above)
            return False, flags
        else:
            # Non-canonical skip reason
            return False, flags

    # Regular STT with spoken text (completed, failed)
    flags["has_raw_vad_complete"] = True
    return True, flags


def run_replay(
    db_path: str,
    output_dir: str,
    legacy_tolerant: bool = False,
) -> Tuple[Dict[str, Any], Path, Path]:
    """
    Executes offline replay with strict data redaction and fail-closed categorization.
    Uses ephemeral in-memory random salt for anonymization.
    """
    validated_db = validate_db_path(db_path)
    validated_out = validate_output_dir(output_dir)

    # Ephemeral 32-byte run salt generated strictly in memory
    run_salt = secrets.token_bytes(32)

    conn = open_readonly_connection(validated_db)
    cursor = conn.cursor()

    # Query exclusively SELECT on qa_decisions
    query = """
        SELECT id, verdict, decided_by, metrics_snapshot
        FROM qa_decisions
        ORDER BY id ASC
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    engine = DeterministicDecisionEngineV1()

    csv_records: List[Dict[str, Any]] = []
    summary_counts = {
        CAT_AGREEMENT: 0,
        CAT_DETERMINISTIC_REVIEW: 0,
        CAT_DETERMINISTIC_REJECT: 0,
        CAT_DANGEROUS_FALSE_APPROVE: 0,
        CAT_INSUFFICIENT_METRICS: 0,
    }

    total_records = len(rows)
    evaluated_records = 0
    insufficient_records = 0

    for row_id, hist_verdict_raw, dec_by_raw, snapshot_raw in rows:
        hist_verdict = (hist_verdict_raw or "REVIEW").upper().strip()
        decided_by = (dec_by_raw or "unknown").strip()

        # Ephemeral anonymized hash ID based on in-memory run salt + row_id
        anon_hasher = hashlib.sha256()
        anon_hasher.update(run_salt)
        anon_hasher.update(str(row_id).encode("utf-8"))
        anon_id = anon_hasher.hexdigest()[:16]

        snap_dict = {}
        if isinstance(snapshot_raw, str) and snapshot_raw.strip():
            try:
                snap_dict = json.loads(snapshot_raw)
            except Exception:
                snap_dict = {}
        elif isinstance(snapshot_raw, dict):
            snap_dict = snapshot_raw

        canonical = adapt_comparison_metrics(snap_dict)
        is_complete, completeness_flags = check_snapshot_completeness(canonical)

        if not is_complete and not legacy_tolerant:
            # Strict mode: insufficient historical contract -> skip full engine decision
            det_verdict = CAT_INSUFFICIENT_METRICS
            category = CAT_INSUFFICIENT_METRICS
            fired_rule = "INSUFFICIENT_METRICS"
            precedence_step = "PRE_EVALUATION_GUARD"
            confidence = 0.0
            insufficient_records += 1
            summary_counts[CAT_INSUFFICIENT_METRICS] += 1
        else:
            evaluated_records += 1
            decision = engine.evaluate(canonical)
            det_verdict = decision["verdict"].upper()
            confidence = decision["confidence"]
            rule_eval = decision.get("rule_evaluation", {})
            fired_rule = rule_eval.get("fired_rule", "UNKNOWN_RULE")
            precedence_step = rule_eval.get("precedence_step", "UNKNOWN_STEP")

            # Categorize against historical verdict
            if det_verdict == hist_verdict:
                category = CAT_AGREEMENT
                summary_counts[CAT_AGREEMENT] += 1
            elif det_verdict == "APPROVE" and hist_verdict == "REJECT":
                # Critical divergence: engine approves what was rejected historically
                category = CAT_DANGEROUS_FALSE_APPROVE
                summary_counts[CAT_DANGEROUS_FALSE_APPROVE] += 1
            elif det_verdict == "REVIEW":
                category = CAT_DETERMINISTIC_REVIEW
                summary_counts[CAT_DETERMINISTIC_REVIEW] += 1
            elif det_verdict == "REJECT":
                category = CAT_DETERMINISTIC_REJECT
                summary_counts[CAT_DETERMINISTIC_REJECT] += 1
            else:
                category = CAT_DETERMINISTIC_REVIEW
                summary_counts[CAT_DETERMINISTIC_REVIEW] += 1

        # Extract numeric metrics for CSV row (strictly numeric or bool)
        vid_sim = canonical.get("video_similarity")
        dur_diff = canonical.get("duration_difference")
        aud_sim = canonical.get("audio_similarity")
        lufs_diff = canonical.get("audio_loudness", {}).get("lufs_difference") if isinstance(canonical.get("audio_loudness"), dict) else None

        csv_records.append({
            "anonymized_id": anon_id,
            "historical_verdict": hist_verdict,
            "decided_by": decided_by,
            "deterministic_verdict": det_verdict,
            "category": category,
            "fired_rule": fired_rule,
            "precedence_step": precedence_step,
            "confidence": confidence,
            "video_similarity": round(vid_sim, 4) if isinstance(vid_sim, (int, float)) else "",
            "duration_difference": round(dur_diff, 4) if isinstance(dur_diff, (int, float)) else "",
            "audio_similarity": round(aud_sim, 4) if isinstance(aud_sim, (int, float)) else "",
            "lufs_difference": round(lufs_diff, 4) if isinstance(lufs_diff, (int, float)) else "",
            "is_complete": is_complete,
            "has_video": completeness_flags["has_video_similarity"],
            "has_duration": completeness_flags["has_duration_difference"],
            "has_probe": completeness_flags["has_audio_probe"],
            "has_stt": completeness_flags["has_stt_payload"],
            "has_raw_vad": completeness_flags["has_raw_vad_complete"],
        })

    # Prepare summary JSON
    suffix = "legacy_tolerant" if legacy_tolerant else "strict"
    summary_report = {
        "replay_mode": "legacy_tolerant" if legacy_tolerant else "strict",
        "experimental": bool(legacy_tolerant),
        "total_decisions": total_records,
        "evaluated_decisions": evaluated_records,
        "insufficient_metrics_count": insufficient_records,
        "categories_breakdown": summary_counts,
        "dangerous_false_approve_count": summary_counts[CAT_DANGEROUS_FALSE_APPROVE],
    }

    json_path = validated_out / f"replay_summary_{suffix}.json"
    csv_path = validated_out / f"replay_records_{suffix}.csv"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary_report, f, indent=2)

    fieldnames = [
        "anonymized_id",
        "historical_verdict",
        "decided_by",
        "deterministic_verdict",
        "category",
        "fired_rule",
        "precedence_step",
        "confidence",
        "video_similarity",
        "duration_difference",
        "audio_similarity",
        "lufs_difference",
        "is_complete",
        "has_video",
        "has_duration",
        "has_probe",
        "has_stt",
        "has_raw_vad",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_records)

    return summary_report, json_path, csv_path


def main():
    parser = argparse.ArgumentParser(
        description="Offline replay tool for Deterministic Decision Engine v1 (Read-Only)."
    )
    parser.add_argument(
        "--db-path",
        required=True,
        help="Path to an SQLite database file (.db). Must not point to live production DB.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Target output directory for reports. Must be located under /tmp.",
    )
    parser.add_argument(
        "--legacy-tolerant",
        action="store_true",
        default=False,
        help="Run in experimental legacy-tolerant mode for incomplete historical records.",
    )

    args = parser.parse_args()

    try:
        summary, json_out, csv_out = run_replay(
            db_path=args.db_path,
            output_dir=args.output_dir,
            legacy_tolerant=args.legacy_tolerant,
        )
        print("Replay completed successfully.")
        print(f"Summary JSON: {json_out}")
        print(f"Records CSV:  {csv_out}")
        print(f"Total: {summary['total_decisions']} | Evaluated: {summary['evaluated_decisions']} | Agreement: {summary['categories_breakdown'][CAT_AGREEMENT]} | False Approves: {summary['dangerous_false_approve_count']}")
    except Exception as e:
        print(f"BŁĄD REPLAY: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
