#!/usr/bin/env python3
"""
Initialize database for New Video Compare
Creates all tables in SQLite database
"""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from models.database import create_tables, engine, Base
from models.models import File, ComparisonJob, ComparisonResult

def init_db():
    print("🔧 Initializing database...")
    print(f"   Database URL: {engine.url}")
    
    # Create all tables
    create_tables()
    
    print("✅ Database initialized successfully!")
    print("   Tables created:")
    for table in Base.metadata.tables.keys():
        print(f"   - {table}")

if __name__ == "__main__":
    init_db()
