"""
New Video Compare - FastAPI Backend
Main application entry point with configuration support
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from pathlib import Path

# Import configuration
from config import settings

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
- Upload i zarządzanie plikami wideo/audio
- Automatyczne parowanie acceptance/emission  
- Analiza wideo (SSIM, histogram, perceptual hash)
- Analiza audio (spektralna, MFCC, cross-correlation)
- Real-time progress tracking
- Export raportów (PDF, JSON, HTML)

## Integracje:
- **AI Agent API**: Autonomous workflow management
- **Desktop App**: WebSocket communication  
- **External Systems**: Webhook notifications
- **Manual Mode**: Drag & drop interface

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
        "timestamp": "2024-09-24T12:00:00Z",
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
            "files": "/api/v1/files",
            "compare": "/api/v1/compare",
            "results": "/api/v1/results",
            "upload": "/api/v1/files/upload",
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
        "max_concurrent_jobs": settings.max_concurrent_jobs,
        "frontend_url": settings.frontend_url,
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
