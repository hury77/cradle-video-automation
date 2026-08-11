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
import subprocess
import urllib.request
import urllib.error

async def dev_cleanup_loop():
    from config import settings
    # Run only in development environment
    if not settings.is_development:
        logger.info("🧹 [CLEANER] LIVE mode detected. Periodic cleaner disabled.")
        return
        
    logger.info("🧹 [CLEANER] DEV mode detected. Starting periodic cleaner task (10 min retention)...")
    uploads_dir = settings.upload_dir
    
    while True:
        try:
            await asyncio.sleep(60) # Scan every 60 seconds
            now = time.time()
            retention_seconds = 600 # 10 minutes retention
            
            if uploads_dir.exists():
                # 1. Clean old source video files in uploads
                for item in uploads_dir.iterdir():
                    if item.is_file() and item.suffix.lower() in [".mp4", ".mov", ".mxf", ".zip", ".gif"]:
                        mtime = item.stat().st_mtime
                        age = now - mtime
                        if age > retention_seconds:
                            try:
                                item.unlink()
                                logger.info(f"🧹 [CLEANER] Deleted old DEV video file (>10 min): {item.name}")
                            except Exception as e:
                                logger.error(f"🧹 [CLEANER] Failed to delete DEV video {item.name}: {e}")
                                
                # 1.5 Clean old proxy video files in uploads/proxies
                proxies_dir = uploads_dir / "proxies"
                if proxies_dir.exists():
                    for item in proxies_dir.iterdir():
                        if item.is_file() and item.suffix.lower() in [".mp4", ".gif"]:
                            mtime = item.stat().st_mtime
                            age = now - mtime
                            if age > retention_seconds:
                                try:
                                    item.unlink()
                                    logger.info(f"🧹 [CLEANER] Deleted old DEV proxy file (>10 min): {item.name}")
                                except Exception as e:
                                    logger.error(f"🧹 [CLEANER] Failed to delete DEV proxy {item.name}: {e}")
                                
                # 2. Clean old temp frame folders in uploads/temp
                temp_dir = uploads_dir / "temp"
                if temp_dir.exists():
                    for job_folder in temp_dir.iterdir():
                        if job_folder.is_dir() and job_folder.name.startswith("job_"):
                            mtime = job_folder.stat().st_mtime
                            age = now - mtime
                            if age > retention_seconds:
                                try:
                                    acc_frames = job_folder / "acceptance_frames"
                                    em_frames = job_folder / "emission_frames"
                                    cleaned_subfolders = []
                                    # SOUL.md Rule: Protect .png and .jpg files needed for difference masks
                                    for subfolder in [acc_frames, em_frames]:
                                        if subfolder.exists():
                                            for item in subfolder.iterdir():
                                                if item.is_file() and item.suffix.lower() not in [".png", ".jpg", ".jpeg"]:
                                                    item.unlink()
                                                    cleaned_subfolders.append(item.name)
                                    
                                    if cleaned_subfolders:
                                        logger.info(f"🧹 [CLEANER] Deleted heavy temp files (but protected PNG/JPG masks) in DEV folder (>10 min): {job_folder.name}")
                                    else:
                                        logger.debug(f"🧹 [CLEANER] No non-image temp files to clean in DEV temp folder: {job_folder.name}")
                                except Exception as e:
                                    logger.error(f"🧹 [CLEANER] Failed to delete DEV temp folder {job_folder.name}: {e}")
        except asyncio.CancelledError:
            logger.info("🧹 [CLEANER] Periodic cleaner task cancelled.")
            break
        except Exception as err:
            logger.error(f"🧹 [CLEANER] Error in DEV periodic cleaner: {err}")

def check_ollama_running():
    try:
        response = urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=1)
        return response.getcode() == 200
    except Exception:
        return False

def verify_git_hooks():
    try:
        repo_root = Path(__file__).parent.parent.parent
        if not (repo_root / ".git").is_dir():
            # Nie jesteśmy w repozytorium gita (np. produkcja po zwykłym skopiowaniu plików)
            return

        result = subprocess.run(["git", "config", "core.hooksPath"], cwd=repo_root, capture_output=True, text=True)
        if ".githooks" not in result.stdout:
            logger.warning("🛡️ Git hooks (core.hooksPath) nie są zainstalowane! Instaluję...")
            subprocess.run(["./scripts/install_hooks.sh"], cwd=repo_root, check=True)
            logger.info("✅ Git hooks zostały zainstalowane pomyślnie podczas startu serwera.")
    except Exception as e:
        logger.error(f"❌ Błąd weryfikacji Git Hooks podczas startu: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Uruchomienie aplikacji - system WebSocket zainicjalizowany")
    verify_git_hooks()
    
    # Start Ollama if not running
    ollama_process = None
    if not check_ollama_running():
        logger.info("Ollama nie działa. Uruchamianie serwera Ollama w tle...")
        ollama_path = os.path.expanduser("~/.local/bin/ollama")
        if os.path.exists(ollama_path):
            try:
                # Uruchamiamy w nowej grupie procesów (preexec_fn=os.setpgrp), 
                # aby CTRL+C (SIGINT) z terminala nie zabiło Ollamy natychmiast.
                # Zostanie ona bezpiecznie zamknięta w bloku teardown po zakończeniu zadań.
                ollama_process = subprocess.Popen(
                    [ollama_path, "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setpgrp
                )
                logger.info("Serwer Ollama uruchamiany...")
                
                # Polling: Czekaj aż Ollama w pełni wstanie (max 15 sekund)
                for _ in range(15):
                    if check_ollama_running():
                        logger.info("✅ Serwer Ollama uruchomił się i jest gotowy.")
                        break
                    await asyncio.sleep(1)
                else:
                    logger.warning("Serwer Ollama uruchomiony, ale nie odpowiada po 15 sekundach.")
                    
            except Exception as e:
                logger.error(f"Nie udało się uruchomić serwera Ollama: {e}")
        else:
            logger.warning(f"Brak pliku Ollama w {ollama_path}. Nie można uruchomić automatycznie.")
    else:
        logger.info("✅ Serwer Ollama jest już uruchomiony.")

    # Start periodic background cleanup task
    cleanup_task = asyncio.create_task(dev_cleanup_loop())
    yield
    # Clean up background task on exit
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
        
    if ollama_process:
        logger.info("Zatrzymywanie serwera Ollama...")
        ollama_process.terminate()
        try:
            ollama_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            ollama_process.kill()

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

from config import settings

uploads_dir = settings.upload_dir
uploads_dir.mkdir(parents=True, exist_ok=True)
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
            return FileResponse(index_path, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
            
    return {"error": "Frontend build not found. Please run 'npm run build' in frontend directory."}


if __name__ == "__main__":
    import uvicorn
    from config import settings

    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.reload)
