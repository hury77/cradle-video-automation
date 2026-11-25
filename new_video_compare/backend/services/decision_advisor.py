"""
Advisory-only DecisionAdvisor seam for future non-authoritative annotations.

Strictly advisory:
- An advisor NEVER alters the deterministic verdict or decided_by.
- Currently only NullAdvisor (provider='none') is implemented.
"""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import logging
from typing import Any, Dict, Optional, Protocol

logger = logging.getLogger(__name__)


class DecisionAdvisor(Protocol):
    def annotate(
        self,
        canonical_metrics: Dict[str, Any],
        decision: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Return optional advisory metadata dict, or None. Must never mutate verdict."""
        ...


class NullAdvisor:
    """Default no-op advisor returning None."""

    def annotate(
        self,
        canonical_metrics: Dict[str, Any],
        decision: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        return None


def get_decision_advisor(provider: Optional[str] = None) -> DecisionAdvisor:
    """Return configured DecisionAdvisor (currently only NullAdvisor for 'none')."""
    if provider not in (None, "none"):
        logger.warning(f"Unsupported advisor_provider={provider!r}; using NullAdvisor.")
    return NullAdvisor()


def run_advisor_advisory(
    advisor: DecisionAdvisor,
    canonical_metrics: Dict[str, Any],
    decision: Dict[str, Any],
    timeout_seconds: float = 1.5,
) -> Optional[Dict[str, Any]]:
    """
    Safely execute advisor.annotate with a short timeout and full exception isolation.
    Returns None on NullAdvisor, timeout, non-dict result, or any exception.
    """
    if isinstance(advisor, NullAdvisor):
        return None

    pool = ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(advisor.annotate, canonical_metrics, decision)
        result = future.result(timeout=timeout_seconds)
        if isinstance(result, dict):
            return result
        return None
    except FuturesTimeoutError:
        logger.warning("⚠️ DecisionAdvisor timed out; continuing without advisory annotation.")
        return None
    except Exception as exc:
        logger.warning(f"⚠️ DecisionAdvisor failed non-fatally ({type(exc).__name__}); continuing.")
        return None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
