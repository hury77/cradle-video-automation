"""
New Video Compare - FastAPI Backend
Main application entry point
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# App metadata
APP_VERSION = "0.1.0"
APP_TITLE = "New Video Compare API"
APP_DESCRIPTION = """
🎬 **Inteligentne porównywanie plików wideo i audio**

Automatyzacja procesu porównywania plików acceptance i emission 
z wykorzystaniem zaawansowanych algorytmów analizy wideo i audio.

## Główne funkcje:
- Upload i zarządzanie plikami
- Automatyczne parowanie acceptance/emission
- Analiza wideo (SSIM, histogram, perceptual hash)
- Analiza audio (spektralna, MFCC, cross-correlation)
- Real-time progress tracking
- Export raportów
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info(f"🚀 Starting {APP_TITLE} v{APP_VERSION}")
    logger.info("🔧 Initializing services...")

    # Initialize database, Redis, etc. here later
    logger.info("✅ Startup complete")

    yield

    # Shutdown
    logger.info("🛑 Shutting down services...")
    logger.info("✅ Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
    ],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "app": APP_TITLE,
        "version": APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "message": "🎬 New Video Compare API is ready!",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "timestamp": "2024-09-24T12:00:00Z",
    }


@app.get("/api/v1/status")
async def api_status():
    """API status endpoint"""
    return {
        "api_version": "v1",
        "backend_status": "operational",
        "services": {
            "database": "not_configured",
            "redis": "not_configured",
            "celery": "not_configured",
            "ffmpeg": "not_configured",
        },
        "endpoints": {
            "files": "/api/v1/files",
            "compare": "/api/v1/compare",
            "results": "/api/v1/results",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True, log_level="info")
