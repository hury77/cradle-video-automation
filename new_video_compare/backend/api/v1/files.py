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

async def process_file_metadata(file_path: Path) -> dict:
    """Extract file metadata (basic version, will be enhanced later)"""
    try:
        stat = file_path.stat()
        return {
            "file_size": stat.st_size,
            "duration": None,  # Will be extracted with FFmpeg later
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
