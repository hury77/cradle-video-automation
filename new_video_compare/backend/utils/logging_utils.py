from sqlalchemy.orm import Session
from models.models import AutomationLog
from datetime import datetime, timezone
import json
from typing import Optional, Any, Dict

def log_automation_event(
    db: Session,
    component: str,
    action: str,
    message: str,
    cradle_id: Optional[str] = None,
    is_error: bool = False,
    details: Optional[Dict[str, Any]] = None
):
    """
    Helper function to log events to the automation_logs table from backend services.
    """
    try:
        new_log = AutomationLog(
            cradle_id=cradle_id,
            component=component,
            action=action,
            message=message,
            is_error=is_error,
            details=details
        )
        db.add(new_log)
        db.commit()
        db.refresh(new_log)
        return new_log
    except Exception as e:
        # Fallback to standard logging if DB logging fails to avoid breaking core logic
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to write to AutomationLog: {e}")
        db.rollback()
        return None
