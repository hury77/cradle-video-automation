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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Uruchomienie aplikacji - system WebSocket zainicjalizowany")
    yield
    logger.info("Zamknięcie aplikacji - czyszczenie połączeń WebSocket")


# Utworzenie aplikacji FastAPI
app = FastAPI(
    title="New Video Compare API",
    description="Zaawansowany system porównywania wideo i audio z aktualizacjami WebSocket w czasie rzeczywistym",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Skonfiguruj odpowiednio dla produkcji
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
# Dołącz routery
app.include_router(compare_router, prefix="/api/v1", tags=["comparison"])
app.include_router(websocket_router, prefix="/ws", tags=["websocket"])
app.include_router(files_router, prefix="/api/v1", tags=["files"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])

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


@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "API działa", "websocket_enabled": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
