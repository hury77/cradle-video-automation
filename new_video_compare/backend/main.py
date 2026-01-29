import sys
import os
from pathlib import Path

# Dodaj katalog backend do Python path przed lokalnymi importami
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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

# Importuj routery po skonfigurowaniu sys.path
from api.v1.compare import router as compare_router
from api.v1.websocket import router as websocket_router
from api.v1.files import router as files_router
from api.v1.dashboard import router as dashboard_router
# Dołącz routery
app.include_router(compare_router, prefix="/api/v1", tags=["comparison"])
app.include_router(websocket_router, prefix="/ws", tags=["websocket"])
app.include_router(files_router, prefix="/api/v1/files", tags=["files"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])

@app.get("/")
async def root():
    return {
        "message": "New Video Compare API",
        "version": "1.0.0",
        "features": [
            "Porównywanie wideo",
            "Analiza audio",
            "Aktualizacje WebSocket w czasie rzeczywistym",
        ],
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "API działa", "websocket_enabled": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
