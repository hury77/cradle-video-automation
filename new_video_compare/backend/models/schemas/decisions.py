from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from .enums import DecisionVerdictEnum, HallucinationMatchTypeEnum
# QA KNOWLEDGE BASE SCHEMAS
# =============================================================================


class QADecisionCreate(BaseModel):
    """Schema for creating a QA decision"""
    verdict: DecisionVerdictEnum
    reasoning: Optional[str] = Field(None, max_length=2000)
    comment: Optional[str] = Field(None, max_length=2000)        # Free-text QA note from human
    override_reason: Optional[str] = Field(None, max_length=500) # Why human overrode AI
    client_name: Optional[str] = Field(None, max_length=200)
    decided_by: str = Field(default="human", max_length=100)


class QADecisionResponse(BaseModel):
    """Schema for QA decision response"""
    id: int
    job_id: int
    verdict: DecisionVerdictEnum
    reasoning: Optional[str] = None
    ai_reasoning: Optional[str] = None    # Original AI reasoning (preserved after override)
    comment: Optional[str] = None         # Human QA comment
    override_reason: Optional[str] = None # Why human overrode AI
    client_name: Optional[str] = None
    cradle_id: Optional[str] = None
    metrics_snapshot: Optional[Dict[str, Any]] = None
    decided_by: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# WHISPER HALLUCINATION SCHEMAS
# =============================================================================


class HallucinationCreate(BaseModel):
    """Schema for creating a whisper hallucination filter"""
    phrase: str = Field(..., min_length=1, max_length=500)
    language: Optional[str] = Field(None, max_length=10)
    match_type: HallucinationMatchTypeEnum = Field(default=HallucinationMatchTypeEnum.CONTAINS)
    is_active: bool = True


class HallucinationUpdate(BaseModel):
    """Schema for updating a whisper hallucination filter"""
    phrase: Optional[str] = Field(None, min_length=1, max_length=500)
    language: Optional[str] = Field(None, max_length=10)
    match_type: Optional[HallucinationMatchTypeEnum] = None
    is_active: Optional[bool] = None


class HallucinationResponse(BaseModel):
    """Schema for whisper hallucination response"""
    id: int
    phrase: str
    language: Optional[str] = None
    match_type: HallucinationMatchTypeEnum
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
