import sys
import os
from pathlib import Path

# OPTIMIZATION: Limit CPU threads to prevent system freeze during AI processing
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

# Dodaj katalog backend do Python path przed lokalnymi importami
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

# Konfiguracja logowania
# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("backend.log"),
        logging.StreamHandler(sys.stdout)
    ],
    force=True
)
logger = logging.getLogger(__name__)

import asyncio
import time
import shutil

async def dev_cleanup_loop():
    from config import settings
    # Run only in development environment
    if not settings.is_development:
        logger.info("🧹 [CLEANER] LIVE mode detected. Periodic cleaner disabled.")
        return
        
    logger.info("🧹 [CLEANER] DEV mode detected. Starting periodic cleaner task (10 min retention)...")
    uploads_dir = Path(__file__).parent / "uploads"
    
    while True:
        try:
            await asyncio.sleep(60) # Scan every 60 seconds
            now = time.time()
            retention_seconds = 600 # 10 minutes retention
            
            if uploads_dir.exists():
                # 1. Clean old source video files in uploads
                for item in uploads_dir.iterdir():
                    if item.is_file() and item.suffix.lower() in [".mp4", ".mov", ".mxf", ".zip"]:
                        mtime = item.stat().st_mtime
                        age = now - mtime
                        if age > retention_seconds:
                            try:
                                item.unlink()
                                logger.info(f"🧹 [CLEANER] Deleted old DEV video file (>10 min): {item.name}")
                            except Exception as e:
                                logger.error(f"🧹 [CLEANER] Failed to delete DEV video {item.name}: {e}")
                                
                # 2. Clean old temp frame folders in uploads/temp
                temp_dir = uploads_dir / "temp"
                if temp_dir.exists():
                    for job_folder in temp_dir.iterdir():
                        if job_folder.is_dir() and job_folder.name.startswith("job_"):
                            mtime = job_folder.stat().st_mtime
                            age = now - mtime
                            if age > retention_seconds:
                                try:
                                    shutil.rmtree(job_folder)
                                    logger.info(f"🧹 [CLEANER] Deleted old DEV temp frames folder (>10 min): {job_folder.name}")
                                except Exception as e:
                                    logger.error(f"🧹 [CLEANER] Failed to delete DEV temp folder {job_folder.name}: {e}")
        except asyncio.CancelledError:
            logger.info("🧹 [CLEANER] Periodic cleaner task cancelled.")
            break
        except Exception as err:
            logger.error(f"🧹 [CLEANER] Error in DEV periodic cleaner: {err}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Uruchomienie aplikacji - system WebSocket zainicjalizowany")
    # Start periodic background cleanup task
    cleanup_task = asyncio.create_task(dev_cleanup_loop())
    yield
    # Clean up background task on exit
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("Zamknięcie aplikacji - czyszczenie połączeń WebSocket")


# Utworzenie aplikacji FastAPI
app = FastAPI(
    title="New Video Compare API",
    description="Zaawansowany system porównywania wideo i audio z aktualizacjami WebSocket w czasie rzeczywistym",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (Uploads)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

uploads_dir = Path(__file__).parent / "uploads"
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# Frontend build directory defined for later use
frontend_build_dir = Path(__file__).parent.parent / "frontend" / "build"

if frontend_build_dir.exists():
    # Mount static assets (js, css, media)
    app.mount("/static", StaticFiles(directory=str(frontend_build_dir / "static")), name="static")
else:
    logger.warning("Frontend build directory not found. Static serving will fail.")

# Importuj routery po skonfigurowaniu sys.path
from api.v1.compare import router as compare_router
from api.v1.websocket import router as websocket_router
from api.v1.files import router as files_router
from api.v1.dashboard import router as dashboard_router
from api.v1.settings import router as settings_router

# Dołącz routery
app.include_router(compare_router, prefix="/api/v1", tags=["comparison"])
app.include_router(websocket_router, prefix="/ws", tags=["websocket"])
app.include_router(files_router, prefix="/api/v1", tags=["files"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(settings_router, prefix="/api/v1", tags=["settings"])

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "API działa", "websocket_enabled": True}


# Catch-all route for SPA (Single Page Application) - MUST BE LAST


@app.get("/")
@app.get("/{full_path:path}")
async def serve_spa(full_path: str = ""):
    # Allow API calls to pass through if they weren't caught by routers above
    if full_path.startswith("api/") or full_path.startswith("ws/"):
        raise HTTPException(status_code=404, detail="Not Found")
    
    # Check if the file exists in the build directory (for root files like favicon.ico, manifest.json)
    if frontend_build_dir.exists() and full_path:
        file_path = frontend_build_dir / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        
    # Serve index.html for client-side routing or root
    if frontend_build_dir.exists():
        index_path = frontend_build_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
            
    return {"error": "Frontend build not found. Please run 'npm run build' in frontend directory."}


if __name__ == "__main__":
    import uvicorn
    from config import settings

    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.reload)
