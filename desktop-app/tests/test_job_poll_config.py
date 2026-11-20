import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Stub heavy/optional transport & browser packages if absent in test env
for _mod in ("websockets", "playwright", "playwright.async_api", "aiohttp"):
    if _mod not in sys.modules:
        try:
            __import__(_mod)
        except ImportError:
            stub = types.ModuleType(_mod)
            if _mod == "playwright.async_api":
                stub.async_playwright = MagicMock()
                stub.TimeoutError = TimeoutError
            elif _mod == "aiohttp":
                stub.ClientTimeout = MagicMock()
                stub.ClientSession = MagicMock()
            sys.modules[_mod] = stub

from websocket_server import (
    DEFAULT_JOB_POLL_INTERVAL_SECONDS,
    DEFAULT_JOB_POLL_MAX_SECONDS,
    classify_final_job_status,
    compute_poll_attempts,
    get_job_poll_max_seconds,
)


class TestJobPollConfig(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(DEFAULT_JOB_POLL_INTERVAL_SECONDS, 5)
        self.assertEqual(DEFAULT_JOB_POLL_MAX_SECONDS, 2400)
        self.assertEqual(
            compute_poll_attempts(
                DEFAULT_JOB_POLL_MAX_SECONDS, DEFAULT_JOB_POLL_INTERVAL_SECONDS
            ),
            480,
        )

    def test_compute_poll_attempts(self):
        self.assertEqual(compute_poll_attempts(2400, 5), 480)
        self.assertEqual(compute_poll_attempts(7, 5), 2)
        self.assertEqual(compute_poll_attempts(1, 5), 1)
        self.assertEqual(compute_poll_attempts(0, 5), 480)
        self.assertEqual(compute_poll_attempts(-10, 0), 480)

    def test_get_job_poll_max_seconds_env_validation(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NVC_JOB_POLL_MAX_SECONDS", None)
            self.assertEqual(get_job_poll_max_seconds(), 2400)

        with patch.dict(os.environ, {"NVC_JOB_POLL_MAX_SECONDS": "3600"}):
            self.assertEqual(get_job_poll_max_seconds(), 3600)

        for invalid in ("0", "-5", "abc", "", "  "):
            with patch.dict(os.environ, {"NVC_JOB_POLL_MAX_SECONDS": invalid}):
                self.assertEqual(get_job_poll_max_seconds(), 2400)

    def test_classify_final_job_status(self):
        self.assertEqual(classify_final_job_status("COMPLETED"), "success")
        self.assertEqual(classify_final_job_status("completed"), "success")
        for st in ("FAILED", "ERROR", "CANCELLED", "UNKNOWN", "", None):
            self.assertEqual(classify_final_job_status(st), "failure")


if __name__ == "__main__":
    unittest.main()
