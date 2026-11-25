"""
Read-only system info endpoint (no secrets, no filesystem paths).
"""

from pathlib import Path
import subprocess
from typing import Optional
from fastapi import APIRouter

from config import settings

router = APIRouter()

ENGINE_VERSION = "1.0.0"


def _get_git_sha() -> Optional[str]:
    try:
        repo_root = Path(__file__).resolve().parents[3]
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()
        return out or None
    except Exception:
        return None


@router.get("/system/info")
async def get_system_info():
    """Return read-only decision engine status and version metadata."""
    return {
        "decision_engine": settings.decision_engine,
        "advisor_provider": settings.advisor_provider,
        "engine_version": ENGINE_VERSION,
        "git_sha": _get_git_sha(),
    }
