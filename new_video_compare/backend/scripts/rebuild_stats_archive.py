#!/usr/bin/env python3
"""Rebuild the StatsArchive table from the current database state.

This script can be executed manually when the archive is out of sync or
has been lost. It aggregates counters for jobs, processing time, storage,
knowledge‑base entries and per‑client job counts, then stores the result
in a singleton StatsArchive row.
"""

import sys
from pathlib import Path

# Adjust PYTHONPATH to include the backend package where models live
project_root = Path(__file__).resolve().parents[1]  # backend directory
sys.path.append(str(project_root))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from models.models import (
    ComparisonJob,
    JobStatus,
    File,
    QADecision,
    StatsArchive,
)

# Database URL – same as used in the FastAPI app (SQLite in this project)
# Use the same database URL as FastAPI app (from models.database)
from models.database import DATABASE_URL
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def rebuild():
    db = SessionLocal()
    try:
        # Ensure a singleton row exists
        archive = db.query(StatsArchive).first()
        if not archive:
            archive = StatsArchive()
            db.add(archive)
            db.flush()

        # Aggregate job statistics
        total_jobs = db.query(func.count(ComparisonJob.id)).scalar() or 0
        completed = (
            db.query(func.count(ComparisonJob.id))
            .filter(ComparisonJob.status == JobStatus.COMPLETED)
            .scalar()
            or 0
        )
        failed = (
            db.query(func.count(ComparisonJob.id))
            .filter(ComparisonJob.status == JobStatus.FAILED)
            .scalar()
            or 0
        )
        processing = (
            db.query(func.count(ComparisonJob.id))
            .filter(ComparisonJob.status.in_([JobStatus.PROCESSING, JobStatus.PENDING]))
            .scalar()
            or 0
        )
        total_processing_seconds = (
            db.query(func.coalesce(func.sum(ComparisonJob.processing_duration), 0))
            .filter(ComparisonJob.status == JobStatus.COMPLETED)
            .scalar()
            or 0.0
        )
        total_storage_bytes = db.query(func.coalesce(func.sum(File.file_size), 0)).scalar() or 0
        total_kb_count = db.query(func.count(QADecision.id)).scalar() or 0

        # Per‑client job counts
        client_counts_query = (
            db.query(ComparisonJob.client_name, func.count(ComparisonJob.id))
            .group_by(ComparisonJob.client_name)
            .all()
        )
        client_counts = {client if client else "Unknown": cnt for client, cnt in client_counts_query}

        # Update the archive
        archive.total_jobs = total_jobs
        archive.total_completed = completed
        archive.total_failed = failed
        archive.total_processing = processing
        archive.total_processing_seconds = float(total_processing_seconds)
        archive.total_storage_bytes = total_storage_bytes
        archive.total_kb_count = total_kb_count
        archive.client_counts = client_counts

        db.commit()
        print("✅ StatsArchive rebuilt successfully")
        print("--- Aggregated values ---")
        for key, value in [
            ("total_jobs", total_jobs),
            ("total_completed", completed),
            ("total_failed", failed),
            ("total_processing", processing),
            ("total_processing_seconds", total_processing_seconds),
            ("total_storage_bytes", total_storage_bytes),
            ("total_kb_count", total_kb_count),
        ]:
            print(f"{key}: {value}")
        print("client_counts:", client_counts)
    finally:
        db.close()

if __name__ == "__main__":
    rebuild()
