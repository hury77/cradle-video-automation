"""
New Video Compare - Database Configuration
SQLAlchemy setup with async support
"""

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

logger = logging.getLogger(__name__)

# Import settings
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import settings

# Database URL from config
DATABASE_URL = settings.database_url

# SQLite requires special handling
is_sqlite = DATABASE_URL.startswith("sqlite")

# Create SQLAlchemy engine
if is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # SQLite specific
        echo=settings.debug
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=20,       # Increased from default 5
        max_overflow=30,    # Increased from default 10
        echo=settings.debug
    )

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()

# Metadata for table creation
metadata = MetaData()

def get_db():
    """
    Database dependency for FastAPI
    Creates and yields database session
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def create_tables():
    """Create all tables in the database"""
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database tables created successfully")

def drop_tables():
    """Drop all tables in the database (use with caution!)"""
    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    logger.info("✅ Database tables dropped")

# Export for easy import
__all__ = ["engine", "SessionLocal", "Base", "get_db", "create_tables", "drop_tables"]
