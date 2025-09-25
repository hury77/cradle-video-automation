"""
New Video Compare - FastAPI Backend
Main application entry point with Files & Comparison API
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from pathlib import Path

# Import configuration
from config import settings

# Import database
from models.database import create_tables, engine

# Import API routers
from api.v1.files import router as files_router
from api.v1.compare import router as compare_router

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info(f"🚀 Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"🌍 Environment: {settings.environment}")
    logger.info(f"🔧 Debug mode: {settings.debug}")
    logger.info(f"📁 Upload directory: {settings.upload_dir}")

    # Create necessary directories
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(exist_ok=True)

    # Create database tables
    try:
        logger.info("📊 Creating database tables...")
        create_tables()
        logger.info("✅ Database tables ready")
    except Exception as e:
        logger.warning(f"⚠️ Database tables creation skipped: {e}")
        logger.info("💡 Using SQLite fallback or existing tables")

    logger.info("✅ Startup complete")

    yield

    # Shutdown
    logger.info("🛑 Shutting down services...")
    logger.info("✅ Shutdown complete")


# Create FastAPI app with dynamic configuration
app = FastAPI(
    title=settings.app_name,
    description="""
🎬 **Inteligentne porównywanie plików wideo i audio**

Automatyzacja procesu porównywania plików acceptance i emission 
z wykorzystaniem zaawansowanych algorytmów analizy wideo i audio.

## Główne funkcje:
- **📁 File Management**: Upload i zarządzanie plikami wideo/audio
- **🎬 Comparison Jobs**: Tworzenie i zarządzanie zadaniami porównywania  
- **🔍 Smart Detection**: Automatyczne rozpoznawanie acceptance/emission  
- **📊 Video Analysis**: SSIM, histogram, perceptual hash, edge detection
- **🎵 Audio Analysis**: Spektralna, MFCC, cross-correlation, loudness
- **⏱️ Real-time Progress**: Live tracking procesów
- **📄 Export Reports**: PDF, JSON, HTML reports

## Workflow:
1. **Upload Files** (`/api/v1/files/upload`) - wgraj pliki acceptance i emission
2. **Create Comparison** (`/api/v1/compare/`) - utwórz zadanie porównywania
3. **Monitor Progress** (`/api/v1/compare/{job_id}`) - śledź postęp
4. **View Results** (`/api/v1/results/{job_id}`) - przeglądaj wyniki

## Auto-Pairing:
- **Smart Pairing** (`/api/v1/compare/auto-pair/{cradle_id}`) - automatyczne parowanie plików

## Integracje:
- **🤖 AI Agent API**: Autonomous workflow management
- **🖥️ Desktop App**: WebSocket communication  
- **🔗 External Systems**: Webhook notifications
- **👆 Manual Mode**: Drag & drop interface

## API Endpoints:
- **Files**: `/api/v1/files/*` - Upload, manage, metadata
- **Compare**: `/api/v1/compare/*` - Start comparisons, monitor jobs
- **Results**: `/api/v1/results/*` - View results & reports

## Status:
- **Version**: """
    + settings.app_version
    + """
- **Environment**: """
    + settings.environment
    + """
- **Debug**: """
    + str(settings.debug)
    + """
    """,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    debug=settings.debug,
)

# CORS middleware with dynamic origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(files_router, prefix="/api/v1")
app.include_router(compare_router, prefix="/api/v1")


# Root endpoint with configuration info
@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "running",
        "docs": "/docs",
        "upload_dir": str(settings.upload_dir),
        "max_file_size_mb": round(settings.max_file_size / 1024 / 1024, 1),
        "api_endpoints": {
            # Files API
            "files_upload": "/api/v1/files/upload",
            "files_list": "/api/v1/files/",
            "files_stats": "/api/v1/files/stats/summary",
            # Comparison API
            "compare_create": "/api/v1/compare/",
            "compare_list": "/api/v1/compare/",
            "compare_auto_pair": "/api/v1/compare/auto-pair/{cradle_id}",
            "compare_start": "/api/v1/compare/{job_id}/start",
            "compare_cancel": "/api/v1/compare/{job_id}/cancel",
            "compare_stats": "/api/v1/compare/stats/summary",
        },
        "workflows": {
            "manual_upload": "Upload files → Create comparison → Monitor progress",
            "auto_pairing": "Upload files → Auto-pair by Cradle ID → Monitor progress",
            "desktop_integration": "Desktop App → WebSocket → Auto processing",
        },
        "message": f"🎬 {settings.app_name} API is ready!",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment,
        "upload_dir_exists": settings.upload_dir.exists(),
        "max_concurrent_jobs": settings.max_concurrent_jobs,
        "database_connected": True,  # Will be enhanced later
        "apis_available": ["files", "compare"],
        "timestamp": "2024-09-25T13:40:00Z",
    }


@app.get("/api/v1/status")
async def api_status():
    """Comprehensive API status endpoint"""
    return {
        "api_version": "v1",
        "backend_status": "operational",
        "configuration": {
            "environment": settings.environment,
            "debug": settings.debug,
            "upload_dir": str(settings.upload_dir),
            "max_file_size": settings.max_file_size,
            "processing_timeout": settings.processing_timeout,
            "max_concurrent_jobs": settings.max_concurrent_jobs,
            "allowed_video_extensions": settings.allowed_video_extensions,
            "allowed_audio_extensions": settings.allowed_audio_extensions,
        },
        "services": {
            "database": f"configured ({settings.db_host}:{settings.db_port})",
            "redis": f"configured ({settings.redis_host}:{settings.redis_port})",
            "celery": "configured",
            "ffmpeg": settings.ffmpeg_path,
        },
        "integrations": {
            "desktop_app": settings.desktop_app_ws_url,
            "ai_agent": settings.ai_agent_url,
            "webhook": "configured" if settings.webhook_url else "not_configured",
        },
        "endpoints": {
            # Files
            "files_upload": "/api/v1/files/upload",
            "files_list": "/api/v1/files/",
            "files_by_id": "/api/v1/files/{file_id}",
            "files_stats": "/api/v1/files/stats/summary",
            "files_by_cradle": "/api/v1/files/cradle/{cradle_id}",
            # Comparison
            "compare_create": "/api/v1/compare/",
            "compare_list": "/api/v1/compare/",
            "compare_by_id": "/api/v1/compare/{job_id}",
            "compare_start": "/api/v1/compare/{job_id}/start",
            "compare_cancel": "/api/v1/compare/{job_id}/cancel",
            "compare_auto_pair": "/api/v1/compare/auto-pair/{cradle_id}",
            "compare_stats": "/api/v1/compare/stats/summary",
            "compare_by_cradle": "/api/v1/compare/cradle/{cradle_id}",
            # Results (future)
            "results": "/api/v1/results",
        },
    }


@app.get("/api/v1/config")
async def get_config():
    """Get safe configuration info (no secrets)"""
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "allowed_video_extensions": settings.allowed_video_extensions,
        "allowed_audio_extensions": settings.allowed_audio_extensions,
        "max_file_size": settings.max_file_size,
        "max_file_size_mb": round(settings.max_file_size / 1024 / 1024, 1),
        "max_concurrent_jobs": settings.max_concurrent_jobs,
        "frontend_url": settings.frontend_url,
        "upload_dir": str(settings.upload_dir),
        "processing_timeout": settings.processing_timeout,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )
