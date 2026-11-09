#!/usr/bin/env python3
"""
run_isolated_tests.py — Izolowany runner testów orkiestracji STT

Instrukcja uruchamiania:
    Wymagane środowisko z zainstalowanym pakietem `pytest` (np. backendowy test_venv lub interpreter z pytest).

    Opcja A (zalecana z dedykowanym test_venv):
        new_video_compare/backend/test_venv/bin/python3 new_video_compare/backend/tests/run_isolated_tests.py

    Opcja B (po aktywacji venv lub w interpreterze z pytest):
        cd /Users/hubert.rycaj/Documents/cradle_stt_fix/new_video_compare/backend
        python3 tests/run_isolated_tests.py

    UWAGA: Skrypt NIE działa na czystym Pythonie bez pakietu `pytest` (wypisze ModuleNotFoundError: No module named 'pytest').
    Wymaga interpretera zawierającego instalację `pytest` (np. test_venv/bin/python3 lub /usr/bin/python3 na tym hoście).

Opis:
Wstrzykuje MockFinder na szczyt sys.meta_path, uniemożliwiając import ciężkich
oraz produkcyjnych modułów C/C++ (torch, mlx_whisper, demucs, cv2, sqlalchemy, models).
Pozwala na bezpieczne, hermetyczne wykonywanie testów logiki orkiestracji STT bez
ryzyka otwarcia produkcyjnej bazy danych ani alokacji Unified Memory.
"""
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

class MockModule(types.ModuleType):
    def __getattr__(self, name):
        return MagicMock()

class MockFinder:
    def __init__(self, modules_to_mock):
        self.modules_to_mock = modules_to_mock

    def find_spec(self, fullname, path, target=None):
        for mod in self.modules_to_mock:
            if fullname == mod or fullname.startswith(mod + '.'):
                import importlib.machinery
                return importlib.machinery.ModuleSpec(fullname, MockLoader())
        return None

class MockLoader:
    def create_module(self, spec):
        return MockModule(spec.name)

    def exec_module(self, module):
        pass

sys.meta_path.insert(0, MockFinder([
    'cv2', 'torch', 'mlx_whisper', 'demucs', 'scipy', 'numpy',
    'ollama', 'librosa', 'soundfile', 'pyloudnorm', 'skimage',
    'pytesseract', 'imagehash', 'PIL', 'sqlalchemy', 'models',
    'passlib', 'jose', 'core', 'db', 'pydantic', 'celery',
    'pydantic_settings'
]))

import pytest

if __name__ == '__main__':
    backend_dir = Path(__file__).parent.parent
    test_path = backend_dir / 'tests/test_stt_orchestration_isolated.py'
    sys.exit(pytest.main([str(test_path), '-v']))
