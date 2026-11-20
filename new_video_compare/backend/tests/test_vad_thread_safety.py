"""
Thread-safety regression tests for Silero VAD loading and inference in services.audio_service.
"""

import contextlib
import subprocess
import sys
import threading
import time
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import services.audio_service as audio_service


class _StatefulFakeVadModel:
    """Fake stateful VAD model that fails loudly if entered concurrently."""

    def __init__(self):
        self._guard = threading.Lock()
        self.active_calls = 0
        self.max_concurrent = 0
        self.reset_count = 0
        self.call_count = 0
        self.was_reset_before_call = True

    def reset_states(self):
        with self._guard:
            self.reset_count += 1
            self.was_reset_before_call = True

    def infer(self):
        with self._guard:
            self.active_calls += 1
            if self.active_calls > self.max_concurrent:
                self.max_concurrent = self.active_calls
            if not self.was_reset_before_call:
                raise AssertionError("Model state was not reset before inference!")
            self.was_reset_before_call = False
            self.call_count += 1
        try:
            time.sleep(0.01)
            return [{"start": 0, "end": 8000}]
        finally:
            with self._guard:
                self.active_calls -= 1


def _write_wav_16k(path: Path, samples: np.ndarray):
    pcm = np.clip(samples * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(pcm.tobytes())


def test_silero_vad_lazy_load_and_inference_serialized(tmp_path):
    """
    Verifies with a stateful fake model that:
    1. Concurrent get_silero_vad() calls load the model exactly once.
    2. Concurrent detect_raw_audio_speech() and apply_vad_filter() calls
       never overlap inside get_speech_timestamps() and always reset state.
    """
    fake_model = _StatefulFakeVadModel()
    load_calls = 0
    load_lock = threading.Lock()

    def _fake_hub_load(**kwargs):
        nonlocal load_calls
        with load_lock:
            load_calls += 1
        time.sleep(0.02)
        fake_utils = (
            lambda wav, model, **kw: model.infer(),
            None,
            lambda p, sampling_rate=16000: np.zeros(16000, dtype=np.float32),
            None,
            None,
        )
        return fake_model, fake_utils

    acc_wav = tmp_path / "acc.wav"
    _write_wav_16k(acc_wav, np.zeros(16000, dtype=np.float32))

    with (
        patch.object(audio_service, "_silero_vad_model", None),
        patch.object(audio_service, "_silero_vad_utils", None),
        patch("torch.hub.load", side_effect=_fake_hub_load),
    ):
        barrier = threading.Barrier(6)

        def _worker(idx: int):
            barrier.wait()
            if idx % 2 == 0:
                res = audio_service.detect_raw_audio_speech(str(acc_wav))
                assert res["status"] == "speech_detected"
            else:
                out_wav = tmp_path / f"out_{idx}.wav"
                ok = audio_service.apply_vad_filter(str(acc_wav), str(out_wav))
                assert ok is True

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(_worker, i) for i in range(6)]
            for fut in futures:
                fut.result()

    assert load_calls == 1
    assert fake_model.max_concurrent == 1
    assert fake_model.call_count == 6
    assert fake_model.reset_count == 6


def test_silero_vad_real_model_multithreaded_cached(tmp_path):
    """
    Runs 4 threads x 5 calls on synthetic 16 kHz audio with the real Silero VAD
    TorchScript model ONLY if torch and the cached Silero repo exist locally.
    Never downloads from the network.
    """
    torch = pytest.importorskip("torch")
    cache_dir = Path.home() / ".cache" / "torch" / "hub" / "snakers4_silero-vad_master"
    if not cache_dir.exists():
        pytest.skip(f"Silero VAD cache not found at {cache_dir}; skipping offline test")

    # Pre-load strictly from local cache without network access
    model, utils = torch.hub.load(
        repo_or_dir=str(cache_dir),
        model="silero_vad",
        source="local",
        force_reload=False,
        trust_repo=True,
    )

    tone_wav = tmp_path / "tone_16k.wav"
    t = np.linspace(0.0, 1.0, 16000, endpoint=False, dtype=np.float32)
    _write_wav_16k(tone_wav, 0.25 * np.sin(2.0 * np.pi * 440.0 * t))

    with (
        patch.object(audio_service, "_silero_vad_model", model),
        patch.object(audio_service, "_silero_vad_utils", utils),
    ):
        barrier = threading.Barrier(4)
        errors = []

        def _thread_job(tid: int):
            try:
                barrier.wait()
                for _ in range(5):
                    res = audio_service.detect_raw_audio_speech(str(tone_wav))
                    assert res["status"] in ("speech_detected", "no_speech"), res
                    assert res["error"] is None
            except Exception as exc:
                errors.append((tid, repr(exc)))

        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = [pool.submit(_thread_job, tid) for tid in range(4)]
            for fut in futs:
                fut.result()

        assert errors == [], f"Multithreaded Silero VAD errors: {errors}"


def test_negative_control_without_lock_reproduces_silero_race(tmp_path):
    """
    Negative control (gate): runs concurrent inference on the real cached
    Silero VAD model in an isolated subprocess with _silero_vad_lock replaced
    by contextlib.nullcontext(). Proves the race condition reproduces (either
    RuntimeError in TorchScript or native TorchScript abort/heap corruption)
    when the lock is removed.
    """
    pytest.importorskip("torch")
    cache_dir = Path.home() / ".cache" / "torch" / "hub" / "snakers4_silero-vad_master"
    if not cache_dir.exists():
        pytest.skip(f"Silero VAD cache not found at {cache_dir}; skipping offline test")

    tone_wav = tmp_path / "tone_16k_neg.wav"
    t = np.linspace(0.0, 2.0, 32000, endpoint=False, dtype=np.float32)
    _write_wav_16k(tone_wav, 0.25 * np.sin(2.0 * np.pi * 440.0 * t))

    script = f"""
import contextlib, threading, sys
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import torch
sys.path.insert(0, {str(backend_dir)!r})
import services.audio_service as audio_service

model, utils = torch.hub.load(
    repo_or_dir={str(cache_dir)!r},
    model="silero_vad",
    source="local",
    force_reload=False,
    trust_repo=True,
)
race_errors = []
with (
    patch.object(audio_service, "_silero_vad_model", model),
    patch.object(audio_service, "_silero_vad_utils", utils),
    patch.object(audio_service, "_silero_vad_lock", contextlib.nullcontext()),
):
    for attempt in range(5):
        barrier = threading.Barrier(4)
        def _worker(tid):
            barrier.wait()
            for idx in range(20):
                res = audio_service.detect_raw_audio_speech({str(tone_wav)!r})
                if res["status"] == "error":
                    race_errors.append((attempt, tid, idx, res["error"]))
        with ThreadPoolExecutor(max_workers=4) as pool:
            for f in [pool.submit(_worker, i) for i in range(4)]:
                f.result()
        if race_errors:
            break
print("RACE_ERRORS:", len(race_errors), race_errors[0] if race_errors else None)
sys.exit(0 if not race_errors else 2)
"""
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode != 0, (
        f"Expected concurrent Silero VAD race/crash without lock, got rc=0: {proc.stdout}"
    )
