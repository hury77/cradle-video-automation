from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
# INTEGRATION SCHEMAS
# =============================================================================


class CradleIntegrationRequest(BaseModel):
    """Schema for Cradle integration requests"""

    cradle_id: str = Field(..., min_length=1, max_length=100)
    acceptance_file_url: Optional[str] = None
    emission_file_url: Optional[str] = None
    auto_start_comparison: bool = False
    notification_webhook: Optional[str] = None


class DesktopAppMessage(BaseModel):
    """Schema for Desktop App WebSocket messages"""

    action: str
    data: Dict[str, Any]
    timestamp: Optional[datetime] = None


# =============================================================================
