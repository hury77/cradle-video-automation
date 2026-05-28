import os
import uuid
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
import shutil

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Cradle DualPlay Mini Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
APP_SUPPORT_DIR = Path.home() / "Library/Application Support/Cradle DualPlay"
UPLOADS_DIR = APP_SUPPORT_DIR / "uploads"
PROXIES_DIR = UPLOADS_DIR / "proxies"
FRONTEND_DIR = BASE_DIR.parent / "frontend"

APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
PROXIES_DIR.mkdir(parents=True, exist_ok=True)

# In-memory job store
jobs: Dict[str, Dict[str, Any]] = {}

WEB_COMPATIBLE_CODECS = {"h264", "h265", "hevc", "vp8", "vp9", "av1"}

def needs_transcoding(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    if ext in ['.mxf', '.prores', '.mov', '.avi', '.mkv']:
        return True
    return False

async def transcode_video(file_id: str, input_path: Path):
    proxy_path = PROXIES_DIR / f"{file_id}.mp4"
    jobs[file_id]["status"] = "processing"
    
    ffmpeg_path = APP_SUPPORT_DIR / "ffmpeg"
    cmd = [
        str(ffmpeg_path),
        "-nostdin",
        "-y",
        "-i", str(input_path),
        "-c:v", "h264_videotoolbox",  # Apple Silicon hardware H.264
        "-b:v", "2M",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        str(proxy_path)
    ]
    
    try:
        # Check if videotoolbox is available
        check_vt = subprocess.run([str(ffmpeg_path), "-h", "encoder=h264_videotoolbox"], capture_output=True, text=True)
        if "Encoder h264_videotoolbox" not in check_vt.stdout:
            cmd[6] = "libx264"
            cmd[7] = "-preset"
            cmd.insert(8, "veryfast")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            jobs[file_id]["is_processed"] = True
            jobs[file_id]["status"] = "completed"
            jobs[file_id]["output_path"] = proxy_path
        else:
            jobs[file_id]["processing_error"] = f"Transcoding failed. {stderr.decode('utf-8')}"
    except Exception as e:
        jobs[file_id]["processing_error"] = f"Wewnętrzny błąd serwera (ffmpeg): {str(e)}"


@app.post("/api/v1/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    file_type: Optional[str] = Form(None)
):
    try:
        file_id = str(uuid.uuid4())
        ext = Path(file.filename).suffix
        safe_filename = f"{file_id}{ext}"
        upload_path = UPLOADS_DIR / safe_filename
        
        with open(upload_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        jobs[file_id] = {
            "id": file_id,
            "original_name": file.filename,
            "path": upload_path,
            "is_processed": False,
            "processing_error": None,
            "status": "pending"
        }
        
        if needs_transcoding(file.filename):
            asyncio.create_task(transcode_video(file_id, upload_path))
        else:
            jobs[file_id]["is_processed"] = True
            jobs[file_id]["status"] = "completed"
            jobs[file_id]["output_path"] = upload_path
            
        return {"success": True, "file_id": file_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/files/{file_id}")
async def get_file_status(file_id: str):
    if file_id not in jobs:
        raise HTTPException(status_code=404, detail="File not found")
    
    return jobs[file_id]

@app.get("/api/v1/files/stream/{file_id}")
@app.head("/api/v1/files/stream/{file_id}")
async def stream_video(file_id: str, request: Request):
    if file_id not in jobs or not jobs[file_id].get("is_processed"):
        raise HTTPException(status_code=404, detail="File not ready or not found")
        
    file_path = jobs[file_id]["output_path"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
        
    file_size = file_path.stat().st_size
    range_header = request.headers.get("range")
    
    if range_header:
        range_match = range_header.replace("bytes=", "").split("-")
        start = int(range_match[0])
        end = int(range_match[1]) if range_match[1] else file_size - 1
        
        chunk_size = min(end - start + 1, 1024 * 1024 * 10)
        end = start + chunk_size - 1
        
        def iterfile():
            with open(file_path, "rb") as f:
                f.seek(start)
                yield f.read(chunk_size)
                
        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
            "Content-Type": "video/mp4",
        }
        return StreamingResponse(iterfile(), status_code=206, headers=headers)
    else:
        return FileResponse(file_path, media_type="video/mp4")

# Frontend Catch-All
if FRONTEND_DIR.exists():
    static_dir = FRONTEND_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/{full_path:path}")
async def serve_spa(full_path: str = ""):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    
    if FRONTEND_DIR.exists() and full_path:
        file_path = FRONTEND_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
            
    if FRONTEND_DIR.exists():
        index_path = FRONTEND_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
            
    return {"error": "Frontend build not found."}

if __name__ == "__main__":
    import threading
    import webbrowser
    import time
    
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://127.0.0.1:8005")
        
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("server:app", host="127.0.0.1", port=8005, log_level="info")
