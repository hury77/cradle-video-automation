"""
New Video Compare - Configuration Settings
Loads environment variables and provides app configuration
"""

import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings  # ← Poprawiony import
from pathlib import Path

class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # =============================================================================
    # APPLICATION SETTINGS
    # =============================================================================
    app_name: str = Field(default="New Video Compare", env="APP_NAME")
    app_version: str = Field(default="0.1.0", env="APP_VERSION")
    debug: bool = Field(default=False, env="DEBUG")
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # =============================================================================
    # SERVER SETTINGS
    # =============================================================================
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8001, env="PORT")
    reload: bool = Field(default=True, env="RELOAD")
    
    # =============================================================================
    # DATABASE CONFIGURATION
    # =============================================================================
    database_url: str = Field(
        default="postgresql://username:password@localhost:5432/new_video_compare",
        env="DATABASE_URL"
    )
    db_host: str = Field(default="localhost", env="DB_HOST")
    db_port: int = Field(default=5432, env="DB_PORT")
    db_name: str = Field(default="new_video_compare", env="DB_NAME")
    db_user: str = Field(default="username", env="DB_USER")
    db_password: str = Field(default="password", env="DB_PASSWORD")
    
    # =============================================================================
    # REDIS CONFIGURATION
    # =============================================================================
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    redis_db: int = Field(default=0, env="REDIS_DB")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    
    # =============================================================================
    # FILE STORAGE SETTINGS
    # =============================================================================
    upload_dir: Path = Field(default=Path("./uploads"), env="UPLOAD_DIR")
    max_file_size: int = Field(default=2147483648, env="MAX_FILE_SIZE")  # 2GB
    allowed_video_extensions: List[str] = Field(
        default=[".mp4", ".mov", ".avi", ".mkv", ".mxf", ".prores"],
        env="ALLOWED_VIDEO_EXTENSIONS"
    )
    allowed_audio_extensions: List[str] = Field(
        default=[".wav", ".mp3", ".aac", ".flac"],
        env="ALLOWED_AUDIO_EXTENSIONS"
    )
    
    # =============================================================================
    # PROCESSING SETTINGS
    # =============================================================================
    ffmpeg_path: str = Field(default="ffmpeg", env="FFMPEG_PATH")
    ffprobe_path: str = Field(default="ffprobe", env="FFPROBE_PATH")
    max_concurrent_jobs: int = Field(default=3, env="MAX_CONCURRENT_JOBS")
    processing_timeout: int = Field(default=1800, env="PROCESSING_TIMEOUT")  # 30 min
    
    # =============================================================================
    # INTEGRATION SETTINGS
    # =============================================================================
    desktop_app_ws_url: str = Field(default="ws://localhost:8765", env="DESKTOP_APP_WS_URL")
    ai_agent_url: str = Field(default="http://localhost:8002", env="AI_AGENT_URL")
    ai_agent_api_key: Optional[str] = Field(default=None, env="AI_AGENT_API_KEY")
    webhook_url: Optional[str] = Field(default=None, env="WEBHOOK_URL")
    webhook_secret: Optional[str] = Field(default=None, env="WEBHOOK_SECRET")
    
    # =============================================================================
    # SECURITY SETTINGS
    # =============================================================================
    secret_key: str = Field(
        default="your-super-secret-key-here-change-in-production",
        env="SECRET_KEY"
    )
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    algorithm: str = Field(default="HS256", env="ALGORITHM")
    
    # =============================================================================
    # LOGGING SETTINGS
    # =============================================================================
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="logs/app.log", env="LOG_FILE")
    log_max_size: int = Field(default=10485760, env="LOG_MAX_SIZE")  # 10MB
    log_backup_count: int = Field(default=5, env="LOG_BACKUP_COUNT")
    
    # =============================================================================
    # FRONTEND SETTINGS
    # =============================================================================
    frontend_url: str = Field(default="http://localhost:3000", env="FRONTEND_URL")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        env="CORS_ORIGINS"
    )
    
    # =============================================================================
    # COMPARISON SENSITIVITY THRESHOLDS
    # =============================================================================
    # Thresholds for each sensitivity level (LOW/MEDIUM/HIGH)
    # ssim_min: Minimum SSIM score for "match" status
    # pixel_diff_tolerance: Percentage of different pixels allowed
    # enable_ocr: Whether to run OCR text detection
    # ocr_region: Which part of frame to OCR ('none', 'bottom_fifth', 'full_frame')
    # normalize_quality: Pre-normalize quality before comparison (slower but more accurate)
    
    # =============================================================================
    # CELERY SETTINGS
    # =============================================================================
    celery_broker_url: str = Field(default="redis://localhost:6379/1", env="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/2", env="CELERY_RESULT_BACKEND")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create upload directory if it doesn't exist
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Create logs directory if it doesn't exist
        log_dir = Path(self.log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment.lower() == "development"

# Create global settings instance
settings = Settings()

# =============================================================================
# SENSITIVITY THRESHOLDS CONFIGURATION
# =============================================================================
# Thresholds for each sensitivity level (LOW/MEDIUM/HIGH)
SENSITIVITY_THRESHOLDS = {
    "low": {
        "ssim_min": 0.85,           # Minimum SSIM for "match"
        "pixel_diff_tolerance": 0.10,  # 10% different pixels allowed
        "enable_ocr": False,
        "ocr_region": "none",
        "normalize_quality": False,
        "description": "Quick check, high tolerance"
    },
    "medium": {
        "ssim_min": 0.92,           # Recommended threshold
        "pixel_diff_tolerance": 0.05,  # 5% different pixels allowed
        "enable_ocr": True,
        "ocr_region": "bottom_fifth",  # Focus on legal text at bottom
        "normalize_quality": False,
        "description": "Recommended, with text detection"
    },
    "high": {
        "ssim_min": 0.98,           # Strict threshold
        "pixel_diff_tolerance": 0.01,  # 1% different pixels allowed  
        "enable_ocr": True,
        "ocr_region": "full_frame",    # OCR entire frame
        "normalize_quality": True,     # Normalize quality before comparison
        "enable_source_separation": True,  # Demucs source separation + voiceover comparison
        "description": "Critical QA, near-perfect match required"
    }
}

def get_sensitivity_config(level: str) -> dict:
    """Get threshold configuration for a sensitivity level"""
    return SENSITIVITY_THRESHOLDS.get(level.lower(), SENSITIVITY_THRESHOLDS["medium"])

# Export for easy import
__all__ = ["settings", "Settings", "SENSITIVITY_THRESHOLDS", "get_sensitivity_config"]
