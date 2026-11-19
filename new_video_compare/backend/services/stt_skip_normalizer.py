"""
Strict, anchored STT skip reason normalizer for Deterministic Shadow Mode.

Why two normalizers exist:
- `services.comparison_service.extract_normalized_skip_code` is the legacy
  production normalizer used by `_build_ai_metrics` and `AnalystService` and
  is kept untouched so production behavior with `DETERMINISTIC_SHADOW_MODE=false`
  remains 100% identical to `origin/dev`.
- `normalize_skip_code_strict` (this module) is used ONLY by
  `DeterministicMetricsAdapter` (shadow mode) and its tests, applying strictly
  anchored regexes on canonical tokens and known legacy templates (fail-closed
  on any unknown or non-matching string).

Zero heavy dependencies (no SQLAlchemy, FastAPI, ML, or DB imports).
"""

import re
from typing import Any, Optional

CANONICAL_FAST_PATH_IDENTICAL_AUDIO = "FAST_PATH_IDENTICAL_AUDIO"
CANONICAL_NO_AUDIO_STREAMS = "NO_AUDIO_STREAMS"
CANONICAL_FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH = (
    "FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH"
)
CANONICAL_DUPLICATE_INPUT = "DUPLICATE_INPUT"

ALLOWLIST_EXPLICIT_SKIPS = {
    CANONICAL_FAST_PATH_IDENTICAL_AUDIO,
    CANONICAL_NO_AUDIO_STREAMS,
    CANONICAL_FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH,
    CANONICAL_DUPLICATE_INPUT,
}

# Anchored regexes for canonical tokens (exact or "<CODE>: ..." / "<CODE> - ...")
_CANONICAL_PREFIX_RE = re.compile(
    r"^(FAST_PATH_IDENTICAL_AUDIO|NO_AUDIO_STREAMS|FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH|DUPLICATE_INPUT)"
    r"(?:(?:\s*:|\s+-).*)?$"
)

# Anchored regex for legacy FAST_PATH skip messages emitted by older audio comparison runs
_LEGACY_FAST_PATH_RE = re.compile(
    r"^Audio similarity \d+(?:\.\d+)? >= 0\.98"
    r"(?:\. STT skipped to avoid false positives from source separation non-determinism| — STT skipped to avoid false positives)\.?$"
)


def normalize_skip_code_strict(raw_skip_reason: Any) -> Optional[str]:
    """
    Extracts and validates the normalized skip reason code against the allowlist.
    Uses strictly anchored regexes on canonical tokens and known legacy templates.
    Unknown or unverified text returns None (fail-closed).
    """
    if not raw_skip_reason or not isinstance(raw_skip_reason, str):
        return None
    s = raw_skip_reason.strip()
    match = _CANONICAL_PREFIX_RE.match(s)
    if match:
        return match.group(1)
    if _LEGACY_FAST_PATH_RE.match(s):
        return CANONICAL_FAST_PATH_IDENTICAL_AUDIO
    return None
