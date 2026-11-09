"""
Unit, security, and safety tests for replay_deterministic_decisions.py.
Tested EXCLUSIVELY against synthetic SQLite databases created dynamically in /tmp.
ZERO real data, ZERO database writes, ZERO Ollama, ZERO network calls.
"""

import csv
import json
import os
import re
import sqlite3
import pytest
from pathlib import Path

from scripts.replay_deterministic_decisions import (
    validate_db_path,
    validate_output_dir,
    open_readonly_connection,
    check_snapshot_completeness,
    run_replay,
    CAT_AGREEMENT,
    CAT_DETERMINISTIC_REVIEW,
    CAT_DETERMINISTIC_REJECT,
    CAT_DANGEROUS_FALSE_APPROVE,
    CAT_INSUFFICIENT_METRICS,
)


@pytest.fixture
def synthetic_db_dir(tmp_path):
    """Provides a dedicated temporary folder inside /tmp."""
    return tmp_path


@pytest.fixture
def populated_synthetic_db(synthetic_db_dir):
    """
    Creates a temporary synthetic SQLite DB under /tmp with:
    - 1 full complete record matching APPROVE
    - 1 full complete record matching REJECT (video < 0.95)
    - 1 legacy record missing probe & STT
    - 1 false approval scenario (historical REJECT but perfect video/audio)
    - 1 full complete record with LUFS > 3.0 (produces legitimate DETERMINISTIC_REVIEW)
    - 1 no-speech record missing raw_vad_status_acc/emi (must become INSUFFICIENT_HISTORICAL_METRICS)
    - 1 skipped record with untrusted/non-canonical reason (must become INSUFFICIENT_HISTORICAL_METRICS)
    - 1 DOOH silent record with complete flags (must be complete and produce APPROVE)
    """
    db_path = synthetic_db_dir / "synthetic_test.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE qa_decisions (
            id INTEGER PRIMARY KEY,
            verdict VARCHAR(10),
            decided_by VARCHAR(100),
            metrics_snapshot JSON,
            knowledge_snapshot JSON,
            reasoning TEXT,
            ai_reasoning TEXT,
            client_name VARCHAR(200),
            cradle_id VARCHAR(100)
        )
    """)

    rec1_snapshot = {
        "job_id": 1001,
        "job_name": "spot_complete.mp4",
        "client_name": "SensitiveClientA",
        "video_similarity": 0.99,
        "duration_difference": 0.0,
        "is_arpp_slate": False,
        "is_binary_duplicate": False,
        "audio_mismatch": False,
        "no_audio_tracks": False,
        "acc_has_audio": True,
        "emi_has_audio": True,
        "audio_similarity": 0.99,
        "audio_loudness": {"lufs_difference": 0.2, "has_loudness_issue": False},
        "audio_transcription": {
            "status": "completed",
            "is_text_match": True,
            "text_similarity": 1.0,
            "is_uncertain": False,
            "word_count_a": 5,
            "word_count_b": 5,
            "acceptance_text": "Super secret script",
            "emission_text": "Super secret script",
        },
        "raw_vad_metrics_complete": True,
        "raw_vad_inconclusive": False,
        "raw_vad_speech": True,
        "raw_vad_error": None,
        "raw_vad_status_acc": "speech_detected",
        "raw_vad_status_emi": "speech_detected",
        "raw_vad_speech_acc": True,
        "raw_vad_speech_emi": True,
        "music_dominant": False,
    }

    # Record 2: Full complete REJECT
    rec2_snapshot = dict(rec1_snapshot)
    rec2_snapshot["video_similarity"] = 0.88

    # Record 3: Legacy record (missing probe & STT)
    rec3_snapshot = {
        "job_id": 1003,
        "video_similarity": 0.99,
        "duration_difference": 0.0,
        "audio_similarity": 0.98,
    }

    # Record 4: Divergence scenario: historical REJECT, but input metrics are 100% perfect
    rec4_snapshot = dict(rec1_snapshot)

    # Record 5: Complete fields with legitimate LUFS > 3.0 -> DETERMINISTIC_REVIEW
    rec5_snapshot = dict(rec1_snapshot)
    rec5_snapshot["audio_loudness"] = {"lufs_difference": 4.5, "has_loudness_issue": True}

    # Record 6: completed_no_speech missing raw_vad_status_acc/emi -> INSUFFICIENT_HISTORICAL_METRICS
    rec6_snapshot = dict(rec1_snapshot)
    rec6_snapshot["audio_transcription"] = {
        "status": "completed_no_speech",
        "is_text_match": True,
        "text_similarity": 1.0,
        "is_uncertain": False,
        "word_count_a": 0,
        "word_count_b": 0,
    }
    rec6_snapshot["raw_vad_status_acc"] = None
    rec6_snapshot["raw_vad_status_emi"] = None

    # Record 7: skipped with non-canonical reason -> INSUFFICIENT_HISTORICAL_METRICS
    rec7_snapshot = dict(rec1_snapshot)
    rec7_snapshot["audio_transcription"] = {
        "status": "skipped",
        "skipped_reason": "UNAUTHORIZED_CUSTOM_SKIP_REASON",
        "is_uncertain": False,
    }

    # Record 8: DOOH silent with complete probe flags -> complete & APPROVE
    rec8_snapshot = {
        "job_id": 1008,
        "video_similarity": 0.99,
        "duration_difference": 0.0,
        "is_arpp_slate": False,
        "is_binary_duplicate": False,
        "audio_mismatch": False,
        "no_audio_tracks": True,
        "acc_has_audio": False,
        "emi_has_audio": False,
    }

    records = [
        (1, "APPROVE", "agent", json.dumps(rec1_snapshot), "Sensitive reasoning A", "Client A"),
        (2, "REJECT", "agent", json.dumps(rec2_snapshot), "Sensitive reasoning B", "Client B"),
        (3, "APPROVE", "agent", json.dumps(rec3_snapshot), "Sensitive reasoning C", "Client C"),
        (4, "REJECT", "human", json.dumps(rec4_snapshot), "Sensitive reasoning D", "Client D"),
        (5, "APPROVE", "agent", json.dumps(rec5_snapshot), "Sensitive reasoning E", "Client E"),
        (6, "APPROVE", "agent", json.dumps(rec6_snapshot), "Sensitive reasoning F", "Client F"),
        (7, "APPROVE", "agent", json.dumps(rec7_snapshot), "Sensitive reasoning G", "Client G"),
        (8, "APPROVE", "agent", json.dumps(rec8_snapshot), "Sensitive reasoning H", "Client H"),
    ]

    cursor.executemany("""
        INSERT INTO qa_decisions (id, verdict, decided_by, metrics_snapshot, reasoning, client_name)
        VALUES (?, ?, ?, ?, ?, ?)
    """, records)

    conn.commit()
    conn.close()
    return db_path


# 1. Verification that replay code contains ZERO SQL DDL/DML statements
def test_replay_code_contains_no_ddl_dml_statements():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "replay_deterministic_decisions.py"
    with open(script_path, "r", encoding="utf-8") as f:
        code = f.read()

    forbidden_sql_patterns = [
        r'\.execute\(\s*["\']\s*CREATE\s+TABLE',
        r'\.execute\(\s*["\']\s*INSERT\s+INTO',
        r'\.execute\(\s*["\']\s*UPDATE\s+',
        r'\.execute\(\s*["\']\s*DELETE\s+FROM',
        r'\.execute\(\s*["\']\s*DROP\s+TABLE',
    ]

    for pat in forbidden_sql_patterns:
        match = re.search(pat, code, re.IGNORECASE)
        assert match is None, f"Found forbidden DDL/DML execution pattern in replay script: {match.group(0)}"


# 2. Test live DB path prohibition
def test_validation_rejects_live_production_path():
    live_path = "~/.cradle_data/new_video_compare.db"
    with pytest.raises(ValueError, match="BEZPIECZEŃSTWO"):
        validate_db_path(live_path)


# 3. Test symlink prohibition
def test_validation_rejects_symlink(tmp_path):
    real_db = tmp_path / "real.db"
    real_db.touch()
    link_db = tmp_path / "link.db"
    link_db.symlink_to(real_db)

    with pytest.raises(ValueError, match="symlink"):
        validate_db_path(str(link_db))


# 4. Test invalid extension or non-existent file
def test_validation_rejects_invalid_extension(tmp_path):
    bad_file = tmp_path / "data.sqlite"
    bad_file.touch()
    with pytest.raises(ValueError, match="rozszerzeniem '.db'"):
        validate_db_path(str(bad_file))

    with pytest.raises(FileNotFoundError):
        validate_db_path(str(tmp_path / "non_existent.db"))


# 5. Test output dir must be strictly within /tmp
def test_validation_rejects_output_dir_outside_tmp():
    home_dir = Path.home() / "forbidden_replay_out"
    with pytest.raises(ValueError, match="musi znajdować się wewnątrz /tmp"):
        validate_output_dir(str(home_dir))


# 6. Test read-only connection verification without any DDL/DML
def test_readonly_connection_mode_verification(populated_synthetic_db):
    conn = open_readonly_connection(populated_synthetic_db)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM qa_decisions")
    count = cursor.fetchone()[0]
    assert count == 8
    conn.close()


# 7. Test ephemeral salt: two runs produce different anonymized_id for the same record
def test_ephemeral_salt_varies_between_runs(populated_synthetic_db, tmp_path):
    out_dir_1 = tmp_path / "run1"
    out_dir_2 = tmp_path / "run2"

    _, _, csv_path_1 = run_replay(str(populated_synthetic_db), str(out_dir_1), legacy_tolerant=False)
    _, _, csv_path_2 = run_replay(str(populated_synthetic_db), str(out_dir_2), legacy_tolerant=False)

    with open(csv_path_1, "r", encoding="utf-8") as f1, open(csv_path_2, "r", encoding="utf-8") as f2:
        rows1 = list(csv.DictReader(f1))
        rows2 = list(csv.DictReader(f2))

    assert len(rows1) == len(rows2) == 8
    ids_run1 = [r["anonymized_id"] for r in rows1]
    ids_run2 = [r["anonymized_id"] for r in rows2]

    for id1, id2 in zip(ids_run1, ids_run2):
        assert id1 != id2
        assert len(id1) == 16
        assert len(id2) == 16


# 8. Test within-run stability and uniqueness of anonymized IDs
def test_anonymized_ids_unique_within_single_run(populated_synthetic_db, tmp_path):
    out_dir = tmp_path / "uniqueness_run"
    _, _, csv_path = run_replay(str(populated_synthetic_db), str(out_dir), legacy_tolerant=False)

    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    ids = [r["anonymized_id"] for r in rows]
    assert len(ids) == 8
    assert len(set(ids)) == 8


# 9. Test strict completeness rules distinguishing review from insufficient metrics
def test_strict_replay_detailed_categorization(populated_synthetic_db, tmp_path):
    out_dir = tmp_path / "replay_out_detailed"
    summary, json_path, csv_path = run_replay(
        db_path=str(populated_synthetic_db),
        output_dir=str(out_dir),
        legacy_tolerant=False,
    )

    assert summary["experimental"] is False
    assert summary["replay_mode"] == "strict"
    assert summary["total_decisions"] == 8

    cats = summary["categories_breakdown"]
    # rec1: APPROVE == APPROVE (Agreement)
    # rec2: REJECT == REJECT (Agreement)
    # rec8: DOOH silent complete APPROVE == APPROVE (Agreement)
    assert cats[CAT_AGREEMENT] == 3

    # rec5: Complete metrics with LUFS 4.5 -> DETERMINISTIC_REVIEW
    assert cats[CAT_DETERMINISTIC_REVIEW] == 1

    # rec4: Historical REJECT vs det APPROVE -> DANGEROUS_FALSE_APPROVE
    assert cats[CAT_DANGEROUS_FALSE_APPROVE] == 1

    # rec3 (legacy missing probe/STT), rec6 (no-speech missing vad_status), rec7 (untrusted skip reason)
    # -> INSUFFICIENT_HISTORICAL_METRICS
    assert cats[CAT_INSUFFICIENT_METRICS] == 3


# 10. Test legacy-tolerant mode evaluates incomplete records
def test_legacy_tolerant_mode_separation(populated_synthetic_db, tmp_path):
    out_dir = tmp_path / "replay_out_tolerant"
    summary, json_path, csv_path = run_replay(
        db_path=str(populated_synthetic_db),
        output_dir=str(out_dir),
        legacy_tolerant=True,
    )

    assert summary["experimental"] is True
    assert summary["replay_mode"] == "legacy_tolerant"
    assert summary["insufficient_metrics_count"] == 0
    assert summary["evaluated_decisions"] == 8


# 11. Test strict data redaction in generated reports
def test_data_redaction_in_reports(populated_synthetic_db, tmp_path):
    out_dir = tmp_path / "replay_out_redaction"
    _, json_path, csv_path = run_replay(
        db_path=str(populated_synthetic_db),
        output_dir=str(out_dir),
        legacy_tolerant=False,
    )

    json_content = json_path.read_text(encoding="utf-8")
    csv_content = csv_path.read_text(encoding="utf-8")

    sensitive_tokens = [
        "SensitiveClientA",
        "Client A",
        "Client B",
        "spot_complete.mp4",
        "Super secret script",
        "Sensitive reasoning",
    ]
    for token in sensitive_tokens:
        assert token not in json_content
        assert token not in csv_content
