from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import logging

from models.database import get_db
from models.models import WhisperHallucination, HallucinationMatchType
from models.schemas import HallucinationCreate, HallucinationUpdate, HallucinationResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("/hallucinations", response_model=List[HallucinationResponse])
async def get_hallucinations(
    language: str = None,
    is_active: bool = None,
    db: Session = Depends(get_db)
):
    """
    Get whisper hallucinations
    """
    query = db.query(WhisperHallucination)
    if language is not None:
        query = query.filter(WhisperHallucination.language == language)
    if is_active is not None:
        query = query.filter(WhisperHallucination.is_active == is_active)
        
    return query.all()

@router.post("/hallucinations", response_model=HallucinationResponse)
async def create_hallucination(
    hallucination: HallucinationCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new whisper hallucination filter
    """
    db_hallucination = WhisperHallucination(**hallucination.model_dump())
    db.add(db_hallucination)
    db.commit()
    db.refresh(db_hallucination)
    return db_hallucination

@router.put("/hallucinations/{hallucination_id}", response_model=HallucinationResponse)
async def update_hallucination(
    hallucination_id: int,
    hallucination_update: HallucinationUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an existing whisper hallucination filter
    """
    db_hallucination = db.query(WhisperHallucination).filter(WhisperHallucination.id == hallucination_id).first()
    if not db_hallucination:
        raise HTTPException(status_code=404, detail="Hallucination not found")
        
    for field, value in hallucination_update.model_dump(exclude_unset=True).items():
        setattr(db_hallucination, field, value)
        
    db.commit()
    db.refresh(db_hallucination)
    return db_hallucination

@router.delete("/hallucinations/{hallucination_id}")
async def delete_hallucination(
    hallucination_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a whisper hallucination filter
    """
    db_hallucination = db.query(WhisperHallucination).filter(WhisperHallucination.id == hallucination_id).first()
    if not db_hallucination:
        raise HTTPException(status_code=404, detail="Hallucination not found")
        
    db.delete(db_hallucination)
    db.commit()
    return {"message": "Hallucination deleted successfully"}
