"""
New Video Compare - Files API Endpoints
File upload, management, and metadata handling
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import shutil
from pathlib import Path
import logging
import time
import uuid

# Import dependencies
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from models.database import get_db
from models.models import File as FileModel, FileType, FileFormat
from models.schemas import (
    FileResponse, FileCreate, FileUpdate, FileUploadResponse, 
    BulkUploadResponse, FileTypeEnum, FileFormatEnum
)
from config import settings

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/files", tags=["Files"])

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_file_format_from_extension(filename: str) -> FileFormatEnum:
    """Determine file format from extension"""
    ext = Path(filename).suffix.lower().lstrip('.')
    format_mapping = {
        'mp4': FileFormatEnum.MP4,
        'mov': FileFormatEnum.MOV,
        'avi': FileFormatEnum.AVI,
        'mkv': FileFormatEnum.MKV,
        'mxf': FileFormatEnum.MXF,
        'prores': FileFormatEnum.PRORES,
        'wav': FileFormatEnum.WAV,
        'mp3': FileFormatEnum.MP3,
        'aac': FileFormatEnum.AAC,
        'flac': FileFormatEnum.FLAC,
    }
    return format_mapping.get(ext, FileFormatEnum.MP4)

def detect_file_type_from_name(filename: str, cradle_id: Optional[str] = None) -> FileTypeEnum:
    """Intelligently detect file type from filename"""
    filename_lower = filename.lower()
    
    # Acceptance patterns
    acceptance_patterns = [
        'accept', 'approval', 'qa', 'proof', 'wcy'
    ]
    
    # Emission patterns  
    emission_patterns = [
        'emission', 'broadcast', 'final', 'master', '_1.', '_final'
    ]
    
    # Check acceptance patterns
    if any(pattern in filename_lower for pattern in acceptance_patterns):
        return FileTypeEnum.ACCEPTANCE
        
    # Check emission patterns
    if any(pattern in filename_lower for pattern in emission_patterns):
        return FileTypeEnum.EMISSION
    
    # Check by file extension (MP4 usually acceptance, MOV/MXF usually emission)
    ext = Path(filename).suffix.lower()
    if ext == '.mp4':
        return FileTypeEnum.ACCEPTANCE
    elif ext in ['.mov', '.mxf', '.prores']:
        return FileTypeEnum.EMISSION
    
    return FileTypeEnum.UNKNOWN

def is_allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    allowed_extensions = (
        settings.allowed_video_extensions + 
        settings.allowed_audio_extensions
    )
    ext = Path(filename).suffix.lower()
    return ext in allowed_extensions

import subprocess
import json

async def process_file_metadata(file_path: Path) -> dict:
    """Extract file metadata using FFprobe for immediate validation"""
    try:
        stat = file_path.stat()
        metadata = {
            "file_size": stat.st_size,
            "duration": None,
            "width": None,
            "height": None,
            "fps": None,
            "bitrate": None,
            "codec": None,
            "audio_channels": None,
            "audio_sample_rate": None,
            "audio_bitrate": None,
            "audio_codec": None,
        }
        
        # Run FFprobe to get detailed metadata
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(file_path)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            logger.warning(f"FFprobe failed for {file_path}: {result.stderr}")
            return metadata
        
        probe_data = json.loads(result.stdout)
        
        # Extract format-level metadata
        if "format" in probe_data:
            fmt = probe_data["format"]
            if "duration" in fmt:
                metadata["duration"] = float(fmt["duration"])
            if "bit_rate" in fmt:
                metadata["bitrate"] = int(fmt["bit_rate"])
        
        # Extract stream-level metadata
        for stream in probe_data.get("streams", []):
            codec_type = stream.get("codec_type")
            
            if codec_type == "video":
                # Video stream info
                metadata["width"] = stream.get("width")
                metadata["height"] = stream.get("height")
                metadata["codec"] = stream.get("codec_name")
                
                # Calculate FPS from frame rate
                if "r_frame_rate" in stream:
                    try:
                        num, den = map(int, stream["r_frame_rate"].split("/"))
                        if den > 0:
                            metadata["fps"] = round(num / den, 2)
                    except (ValueError, ZeroDivisionError):
                        pass
                        
            elif codec_type == "audio":
                # Audio stream info
                metadata["audio_codec"] = stream.get("codec_name")
                metadata["audio_channels"] = stream.get("channels")
                metadata["audio_sample_rate"] = int(stream.get("sample_rate", 0)) or None
                if "bit_rate" in stream:
                    metadata["audio_bitrate"] = int(stream["bit_rate"])
        
        logger.info(f"📊 Extracted metadata: duration={metadata['duration']:.2f}s, " +
                   f"resolution={metadata['width']}x{metadata['height']}, " +
                   f"fps={metadata['fps']}, codec={metadata['codec']}")
        
        return metadata
        
    except subprocess.TimeoutExpired:
        logger.error(f"FFprobe timeout for {file_path}")
        return {"file_size": file_path.stat().st_size}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse FFprobe output for {file_path}: {e}")
        return {"file_size": file_path.stat().st_size}
    except Exception as e:
        logger.error(f"Error extracting metadata from {file_path}: {e}")
        return {"file_size": 0}

# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    file_type: Optional[FileTypeEnum] = Form(None),
    cradle_id: Optional[str] = Form(None),
    external_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload a single video/audio file
    
    - **file**: Video or audio file to upload
    - **file_type**: Optional file type (acceptance/emission), auto-detected if not provided
    - **cradle_id**: Optional Cradle ID for integration
    - **external_id**: Optional external system ID
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        if not is_allowed_file(file.filename):
            raise HTTPException(
                status_code=400, 
                detail=f"File type not allowed. Allowed extensions: {settings.allowed_video_extensions + settings.allowed_audio_extensions}"
            )
        
        if file.size and file.size > settings.max_file_size:
            raise HTTPException(
                status_code=400, 
                detail=f"File too large. Maximum size: {settings.max_file_size / 1024 / 1024:.1f} MB"
            )
        
        # Generate unique filename to avoid conflicts
        unique_id = str(uuid.uuid4())[:8]
        file_extension = Path(file.filename).suffix
        safe_filename = f"{Path(file.filename).stem}_{unique_id}{file_extension}"
        
        # Create upload path
        upload_path = settings.upload_dir / safe_filename
        
        logger.info(f"📤 Uploading file: {file.filename} -> {safe_filename}")
        logger.info(f"💾 Upload path: {upload_path}")
        
        # Save file
        with open(upload_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"✅ File saved: {upload_path}")
        
        # Extract basic metadata
        metadata = await process_file_metadata(upload_path)
        
        # Detect file type if not provided
        detected_file_type = file_type or detect_file_type_from_name(file.filename, cradle_id)
        
        # Create database record
        file_record = FileModel(
            filename=safe_filename,
            original_name=file.filename,
            file_path=str(upload_path),
            file_type=FileType(detected_file_type.value),
            file_format=FileFormat(get_file_format_from_extension(file.filename).value),
            file_size=metadata["file_size"],
            duration=metadata.get("duration"),
            width=metadata.get("width"),
            height=metadata.get("height"),
            fps=metadata.get("fps"),
            bitrate=metadata.get("bitrate"),
            codec=metadata.get("codec"),
            audio_channels=metadata.get("audio_channels"),
            audio_sample_rate=metadata.get("audio_sample_rate"),
            audio_bitrate=metadata.get("audio_bitrate"),
            audio_codec=metadata.get("audio_codec"),
            cradle_id=cradle_id,
            external_id=external_id,
            is_processed=False
        )
        
        db.add(file_record)
        db.commit()
        db.refresh(file_record)
        
        logger.info(f"✅ File record created: ID={file_record.id}")
        
        # Schedule background processing (metadata extraction with FFmpeg)
        # background_tasks.add_task(process_file_full_metadata, file_record.id)
        
        return FileUploadResponse(
            success=True,
            message="File uploaded successfully",
            file_id=file_record.id,
            filename=safe_filename,
            file_size=metadata["file_size"],
            file_type=detected_file_type,
            processing_started=True
        )
        
    except HTTPException:
        # Remove uploaded file if database operation failed
        if upload_path and upload_path.exists():
            upload_path.unlink()
        raise
    except Exception as e:
        # Remove uploaded file if error occurred
        if 'upload_path' in locals() and upload_path.exists():
            upload_path.unlink()
        logger.error(f"❌ File upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

@router.get("/", response_model=List[FileResponse])
async def list_files(
    skip: int = 0,
    limit: int = 100,
    file_type: Optional[FileTypeEnum] = None,
    cradle_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List uploaded files with optional filtering
    
    - **skip**: Number of files to skip (pagination)
    - **limit**: Maximum number of files to return
    - **file_type**: Filter by file type (acceptance/emission)
    - **cradle_id**: Filter by Cradle ID
    """
    query = db.query(FileModel)
    
    if file_type:
        query = query.filter(FileModel.file_type == FileType(file_type.value))
    
    if cradle_id:
        query = query.filter(FileModel.cradle_id == cradle_id)
    
    files = query.offset(skip).limit(limit).all()
    return files

@router.get("/{file_id}", response_model=FileResponse)
async def get_file(file_id: int, db: Session = Depends(get_db)):
    """
    Get file by ID
    
    - **file_id**: File ID to retrieve
    """
    file_record = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    return file_record

@router.put("/{file_id}", response_model=FileResponse)
async def update_file(
    file_id: int, 
    file_update: FileUpdate, 
    db: Session = Depends(get_db)
):
    """
    Update file metadata
    
    - **file_id**: File ID to update
    - **file_update**: File update data
    """
    file_record = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Update fields
    for field, value in file_update.dict(exclude_unset=True).items():
        if field == "file_type" and value:
            setattr(file_record, field, FileType(value.value))
        else:
            setattr(file_record, field, value)
    
    db.commit()
    db.refresh(file_record)
    
    logger.info(f"✅ File updated: ID={file_id}")
    return file_record

@router.delete("/{file_id}")
async def delete_file(file_id: int, db: Session = Depends(get_db)):
    """
    Delete file and its database record
    
    - **file_id**: File ID to delete
    """
    file_record = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete physical file
    file_path = Path(file_record.file_path)
    if file_path.exists():
        file_path.unlink()
        logger.info(f"🗑️ Physical file deleted: {file_path}")
    
    # Delete database record
    db.delete(file_record) 
    db.commit()
    
    logger.info(f"✅ File record deleted: ID={file_id}")
    return {"message": "File deleted successfully"}

# =============================================================================
# BULK OPERATIONS
# =============================================================================

@router.get("/cradle/{cradle_id}", response_model=List[FileResponse])
async def get_files_by_cradle_id(cradle_id: str, db: Session = Depends(get_db)):
    """
    Get all files for a specific Cradle ID
    
    - **cradle_id**: Cradle ID to search for
    """
    files = db.query(FileModel).filter(FileModel.cradle_id == cradle_id).all()
    return files

@router.get("/stats/summary")
async def get_file_stats(db: Session = Depends(get_db)):
    """Get file statistics summary"""
    total_files = db.query(FileModel).count()
    acceptance_files = db.query(FileModel).filter(FileModel.file_type == FileType.ACCEPTANCE).count()
    emission_files = db.query(FileModel).filter(FileModel.file_type == FileType.EMISSION).count()
    processed_files = db.query(FileModel).filter(FileModel.is_processed == True).count()
    
    return {
        "total_files": total_files,
        "acceptance_files": acceptance_files,
        "emission_files": emission_files,
        "unknown_files": total_files - acceptance_files - emission_files,
        "processed_files": processed_files,
        "pending_files": total_files - processed_files,
        "upload_dir": str(settings.upload_dir),
        "upload_dir_size_mb": sum(f.stat().st_size for f in settings.upload_dir.glob("*") if f.is_file()) / 1024 / 1024
    }


# =============================================================================
# VIDEO STREAMING ENDPOINT WITH AUTO-TRANSCODING
# =============================================================================

from fastapi import Request
from fastapi.responses import StreamingResponse
import subprocess

# Web-compatible codecs that browsers can play natively
WEB_COMPATIBLE_CODECS = {"h264", "h265", "hevc", "vp8", "vp9", "av1"}

def needs_transcoding(file_record) -> bool:
    """Check if file needs transcoding for web playback"""
    codec = (file_record.codec or "").lower()
    
    # Handle FileFormat enum - get string value
    file_format_obj = file_record.file_format
    if file_format_obj:
        file_format = file_format_obj.value.lower() if hasattr(file_format_obj, 'value') else str(file_format_obj).lower()
    else:
        file_format = ""
    
    # ProRes, DNxHD, and similar professional codecs need transcoding
    if codec in ["prores", "dnxhd", "dnxhr", "mpeg2video", "rawvideo"]:
        return True
    
    # MOV files with non-H264 codecs need transcoding
    if file_format == "mov" and codec not in WEB_COMPATIBLE_CODECS:
        return True
    
    # If codec is unknown but format is MOV, assume it needs transcoding
    if file_format == "mov" and not codec:
        return True
        
    return False

def get_proxy_path(original_path: Path) -> Path:
    """Get path for transcoded proxy file"""
    proxy_dir = settings.upload_dir / "proxies"
    proxy_dir.mkdir(exist_ok=True)
    return proxy_dir / f"{original_path.stem}_proxy.mp4"

from starlette.concurrency import run_in_threadpool

def transcode_to_mp4(input_path: Path, output_path: Path) -> bool:
    """Transcode video to web-compatible H.264 MP4"""
    if output_path.exists():
        logger.info(f"✅ Proxy already exists: {output_path}")
        return True
    
    logger.info(f"🔄 Transcoding {input_path.name} to web-compatible MP4...")
    
    cmd = [
        "ffmpeg",
        "-nostdin",  # Prevent hanging
        "-y",
        "-i", str(input_path),
        "-c:v", "libx264",           # H.264 codec
        "-preset", "fast",            # Fast encoding
        "-crf", "23",                # Good quality
        "-c:a", "aac",               # AAC audio
        "-b:a", "128k",              # Audio bitrate
        "-movflags", "+faststart",   # Enable fast web playback
        "-pix_fmt", "yuv420p",       # Compatible pixel format
        str(output_path)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 min timeout
        )
        
        if result.returncode == 0:
            logger.info(f"✅ Transcoding complete: {output_path}")
            return True
        else:
            logger.error(f"❌ Transcoding failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"❌ Transcoding timeout for {input_path}")
        return False
    except Exception as e:
        logger.error(f"❌ Transcoding error: {e}")
        return False


@router.get("/stream/{file_id}")
async def stream_video(
    file_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Stream a video file with Range request support for seeking.
    Automatically transcodes ProRes/MOV to H.264 MP4 for web playback.
    
    - **file_id**: ID of the file to stream
    """
    # Get file from database
    file_record = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Get file path
    file_path = Path(file_record.file_path)
    if not file_path.is_absolute():
        file_path = settings.upload_dir / file_record.filename
    
    
    # Check if file exists at stored path
    if not file_path.exists():
        # Fallback 1: Check in settings.upload_dir
        fallback_path = settings.upload_dir / file_record.filename
        if fallback_path.exists():
            file_path = fallback_path
        else:
             # Fallback 2: Check in new_video_compare/backend/uploads (where we know they are)
             backend_upload_path = Path("new_video_compare/backend/uploads") / file_record.filename
             if backend_upload_path.exists():
                 file_path = backend_upload_path
             else:
                 # Fallback 3: Check relative to backend dir logic
                 relative_backend_upload = Path("uploads") / file_record.filename
                 if relative_backend_upload.exists():
                     file_path = relative_backend_upload

    if not file_path.exists():
        logger.error(f"❌ File not found on disk: {file_record.file_path}")
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    # Check if transcoding is needed
    if needs_transcoding(file_record):
        proxy_path = get_proxy_path(file_path)
        
        if not proxy_path.exists():
            # Transcode asynchronously in thread pool to avoid blocking event loop
            success = await run_in_threadpool(transcode_to_mp4, file_path, proxy_path)
            if not success:
                raise HTTPException(
                    status_code=500, 
                    detail="Failed to transcode video for web playback"
                )
        
        # Use proxy for streaming
        file_path = proxy_path
        content_type = "video/mp4"
    else:
        # Use original file
        content_type_map = {
            "mp4": "video/mp4",
            "mov": "video/quicktime",
            "avi": "video/x-msvideo",
            "mkv": "video/x-matroska",
            "webm": "video/webm",
        }
        ext = file_path.suffix.lower().lstrip(".")
        content_type = content_type_map.get(ext, "video/mp4")
    
    file_size = file_path.stat().st_size
    
    # Handle Range requests for seeking
    range_header = request.headers.get("range")
    
    if range_header:
        # Parse range header
        range_match = range_header.replace("bytes=", "").split("-")
        start = int(range_match[0])
        end = int(range_match[1]) if range_match[1] else file_size - 1
        
        # Limit chunk size
        chunk_size = min(end - start + 1, 1024 * 1024 * 10)  # 10MB max chunk
        end = start + chunk_size - 1
        
        def iterfile():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    chunk = f.read(min(8192, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        
        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
            "Content-Type": content_type,
        }
        
        return StreamingResponse(
            iterfile(),
            status_code=206,
            headers=headers,
            media_type=content_type,
        )
    else:
        # Full file response
        def iterfile():
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    yield chunk
        
        headers = {
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        }
        
        return StreamingResponse(
            iterfile(),
            headers=headers,
            media_type=content_type,
        )

