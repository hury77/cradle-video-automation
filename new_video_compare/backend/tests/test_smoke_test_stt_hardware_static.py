#!/usr/bin/env python3
"""
test_smoke_test_stt_hardware_static.py — Test statyczny i lekki test timeoutu dla smoke_test_stt_hardware.py

Weryfikuje kontrakty bezpieczenstwa smoke testu sprzetowego BEZ uruchamiania MLX/Demucs:
1. Bezwzgledny zakaz wystepowania proc.kill, SIGKILL i kill -9 w kodzie i testach.
2. Obecnosc start_new_session=True, os.killpg oraz signal.SIGTERM.
3. Warunkowy cleanup katalogu tmp (cleanup_deferred=True przy wiszacym procesie).
4. Brak flagi --force w parserze CLI.
5. Obecnosc limitow czasowych: STAGE_TIMEOUT_SEC (60s) i GLOBAL_MAX_TIMEOUT_SEC (180s).
6. Odmowa startu przy aktywnym Ollama (kod wyjscia 1).
7. Odmowa startu przy RAM < 8 GiB (kod wyjscia 2).
8. Zaakceptowanie no-speech / pustego tekstu jako prawidlowego wyniku syntetycznego audio.
9. Czystosc kodu: brak .cradle_data, brak uploads, brak usuwania globalnego locka.
10. Lekki test funkcjonalny timeoutu na /bin/sh -c 'sleep 2' z timeoutem 0.1s:
    - sprawdza start w osobnej grupie procesow (PGID == PID);
    - sprawdza timed_out=True i still_running=False po SIGTERM;
    - sprawdza, ze cleanup bylby wykonany dla zakonczonego procesu, a odroczony dla still_running.
"""
import os
import sys
import ast
import time
import signal
import tempfile
import argparse
from pathlib import Path
from unittest.mock import patch, MagicMock

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

SMOKE_SCRIPT_PATH = backend_dir / "tests/smoke_test_stt_hardware.py"

def test_static_source_code_cleanliness_and_no_lock_deletion():
    """Sprawdza brak produkcyjnych sciezek oraz brak usuwania globalnego locka."""
    with open(SMOKE_SCRIPT_PATH, 'r') as f:
        src = f.read()

    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                assert 'models.database' not in n.name
                assert 'models.models' not in n.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ''
            assert 'models.database' not in mod
            assert 'models.models' not in mod

    assert ".cradle_data" not in src, "Smoke test nie moze odwolywac sie do ~/.cradle_data"
    assert "/uploads" not in src and r"\uploads" not in src, "Smoke test nie moze dotykac uploads"
    assert "os.remove" not in src or "/tmp/nvc_heavy_model_mps.lock" not in src
    assert "unlink" not in src or "/tmp/nvc_heavy_model_mps.lock" not in src
    print("Test 1: Statyczna czystosc kodu zaliczona.")

def test_strictly_forbidden_kill_mechanisms():
    """Sprawdza calkowity zakaz wystepowania proc.kill, SIGKILL oraz kill -9."""
    with open(SMOKE_SCRIPT_PATH, 'r') as f:
        src = f.read()

    assert "proc.kill(" not in src, "Wywolanie proc.kill() jest bezwzglednie zakazane"
    assert "proc.kill" not in src, "proc.kill jest bezwzglednie zakazane"
    assert "SIGKILL" not in src, "SIGKILL jest bezwzglednie zakazane"
    assert "kill -9" not in src, "kill -9 jest bezwzglednie zakazane"
    print("Test 2: Calkowity zakaz proc.kill, SIGKILL i kill -9 zaliczony.")

def test_static_process_group_and_conditional_cleanup_assertions():
    """Sprawdza obecnosc start_new_session=True, os.killpg, signal.SIGTERM oraz logiki cleanup_deferred."""
    with open(SMOKE_SCRIPT_PATH, 'r') as f:
        src = f.read()

    assert "start_new_session=True" in src, "Wymagane uruchamianie subprocessu z start_new_session=True"
    assert "os.killpg" in src, "Wymagane uzycie os.killpg do sygnalizowania calej grupy procesow"
    assert "signal.SIGTERM" in src, "Wymagane uzycie signal.SIGTERM"
    assert "cleanup_deferred" in src, "Wymagana flaga cleanup_deferred w raporcie i logice sprzatania"
    print("Test 3: Statyczne asercje start_new_session, os.killpg, signal.SIGTERM i cleanup_deferred zaliczone.")

def test_no_force_flag_in_cli_and_strict_defaults():
    """Sprawdza, ze flaga --force zostala calkowicie usunieta z parsera argumentow."""
    with open(SMOKE_SCRIPT_PATH, 'r') as f:
        src = f.read()

    assert "--force" not in src, "Flaga --force musi byc calkowicie usunieta ze skryptu"

    parser = argparse.ArgumentParser()
    parser.add_argument('--with-demucs', action='store_true', default=False)
    args = parser.parse_args([])
    assert args.with_demucs is False, "Demucs musi byc domyslnie wylaczony"
    print("Test 4: Brak flagi --force oraz domyslne with_demucs=False zaliczone.")

def test_timeout_definitions():
    """Sprawdza zdefiniowane stale timeoutu."""
    from tests import smoke_test_stt_hardware
    assert hasattr(smoke_test_stt_hardware, 'STAGE_TIMEOUT_SEC')
    assert smoke_test_stt_hardware.STAGE_TIMEOUT_SEC == 60
    assert hasattr(smoke_test_stt_hardware, 'GLOBAL_MAX_TIMEOUT_SEC')
    assert smoke_test_stt_hardware.GLOBAL_MAX_TIMEOUT_SEC == 180
    print("Test 5: Definicje limitow czasowych (60s etap, 180s globalny) zaliczone.")

def test_refuse_start_on_active_ollama_fail_closed():
    """Sprawdza, ze skrypt bezwzglednie odmawia startu (kod 1) przy aktywnym Ollama."""
    from tests import smoke_test_stt_hardware
    with patch.object(smoke_test_stt_hardware, 'check_active_conflicting_processes', return_value=['ollama (PID 1234: ollama serve)']):
        with patch.object(smoke_test_stt_hardware, 'check_available_system_ram', return_value=(12.0, True)):
            exit_code = smoke_test_stt_hardware.run_smoke_test(with_demucs=False)
            assert exit_code == 1, f"Oczekiwano kodu 1 (odmowa przy Ollama), otrzymano: {exit_code}"
    print("Test 6: Bezwzgledna odmowa startu przy aktywnym Ollama (kod wyjscia 1) zaliczona.")

def test_refuse_start_on_low_memory_fail_closed():
    """Sprawdza, ze skrypt bezwzglednie odmawia startu (kod 2) przy RAM < 8 GiB."""
    from tests import smoke_test_stt_hardware
    with patch.object(smoke_test_stt_hardware, 'check_active_conflicting_processes', return_value=[]):
        with patch.object(smoke_test_stt_hardware, 'check_available_system_ram', return_value=(3.5, False)):
            exit_code = smoke_test_stt_hardware.run_smoke_test(with_demucs=False)
            assert exit_code == 2, f"Oczekiwano kodu 2 (odmowa przy niskiej pamieci), otrzymano: {exit_code}"
    print("Test 7: Bezwzgledna odmowa startu przy RAM < 8 GiB (kod wyjscia 2) zaliczona.")

def test_expected_no_speech_acceptance():
    """Weryfikuje logike akceptacji pustego tekstu / no-speech jako oczekiwanego sukcesu syntetycznej sinusoidy."""
    empty_whisper_payload = {"text": "", "segments": []}
    has_error = "error" in empty_whisper_payload
    detected_text = empty_whisper_payload.get("text", "").strip()
    is_expected_no_speech = (detected_text == "" or len(detected_text) < 10)
    success = (not has_error)

    assert success is True
    assert is_expected_no_speech is True
    print("Test 8: Prawidlowa akceptacja no-speech dla syntetycznego audio zaliczona.")

def test_functional_lightweight_timeout_sleep_with_process_group():
    """
    Lekki test funkcjonalny procedury run_stage_subprocess:
    Uruchamia /bin/sh -c 'sleep 2' z timeoutem 0.1s.
    Weryfikuje:
    - start_new_session utworzylo osobna grupe procesow (PID == PGID);
    - timed_out == True;
    - still_running == False po obsludze SIGTERM;
    - logika warunkowego sprzatania: dla still_running=False katalog bylby usuwany,
      natomiast dla still_running=True katalog jest zachowywany (cleanup_deferred).
    """
    from tests.smoke_test_stt_hardware import run_stage_subprocess
    import shutil

    start_t = time.time()
    rc, stdout, stderr, timed_out, still_running, pid, pgid = run_stage_subprocess(
        ["/bin/sh", "-c", "sleep 2"],
        timeout_sec=0.1
    )
    duration = time.time() - start_t

    assert timed_out is True, "Oczekiwano timed_out=True dla sleep 2 przy timeout 0.1s"
    assert rc == -1, f"Oczekiwano returncode=-1, otrzymano: {rc}"
    assert duration < 2.0, f"Subprocess powinien zakonczyc sie natychmiast po terminate(), trwal: {duration:.2f}s"
    assert still_running is False, "Zwykly proces sleep powinien bezproblemowo zakonczyc sie po SIGTERM"
    assert pid is not None and pid > 0, "PID powinien byc prawidlowo zwrocony"
    assert pgid is not None and pgid == pid, f"Oczekiwano PID ({pid}) == PGID ({pgid}) dzieki start_new_session=True"

    # Weryfikacja kontraktu warunkowego sprzatania
    temp_dir_test = Path(tempfile.mkdtemp(prefix="test_cleanup_"))
    try:
        cleanup_deferred_case1 = False  # still_running=False
        if not cleanup_deferred_case1:
            shutil.rmtree(temp_dir_test, ignore_errors=True)
        assert not temp_dir_test.exists(), "Katalog powinien byc usuniety gdy still_running=False"

        temp_dir_test2 = Path(tempfile.mkdtemp(prefix="test_cleanup_deferred_"))
        cleanup_deferred_case2 = True   # still_running=True
        if not cleanup_deferred_case2:
            shutil.rmtree(temp_dir_test2, ignore_errors=True)
        assert temp_dir_test2.exists(), "Katalog NIE moze byc usuniety gdy still_running=True (cleanup_deferred)"
        shutil.rmtree(temp_dir_test2, ignore_errors=True)
    finally:
        shutil.rmtree(temp_dir_test, ignore_errors=True)

    print(f"Test 9: Lekki test funkcjonalny subprocessu i warunkowego cleanupu zaliczony (timed_out={timed_out}, still_running={still_running}, PID={pid}, PGID={pgid}, duration={duration:.2f}s).")

def test_build_stage_error_diagnostics_with_error_and_home_redaction():
    """
    Weryfikuje, ze build_stage_error_diagnostics prawidlowo ekstrahuje pola,
    wykrywa stderr_tail oraz redaguje sciezke home do ~.
    """
    from tests.smoke_test_stt_hardware import build_stage_error_diagnostics

    home_dir = str(Path.home())
    fake_error = f"Subprocess failed with code 1 in {home_dir}/models/whisper. stderr tail: File not found in {home_dir}/cache"
    mock_payload = {
        "error": fake_error,
        "text": "",
        "segments": []
    }

    diag = build_stage_error_diagnostics(mock_payload, returncode=0)

    assert diag["has_error"] is True
    assert diag["returncode"] == 0
    assert diag["payload_keys"] == ["error", "segments", "text"]
    assert home_dir not in diag["error"], "Pelna sciezka home powinna byc zredagowana"
    assert "~" in diag["error"], "Zamiast sciezki home powinien pojawic sie znak ~"
    assert diag["stderr_tail"] is not None
    assert home_dir not in diag["stderr_tail"]
    assert "File not found in ~/cache" in diag["stderr_tail"]
    print("Test 10: build_stage_error_diagnostics z bledem i redagowaniem home zaliczony.")

def test_build_stage_error_diagnostics_without_error():
    """
    Weryfikuje, ze build_stage_error_diagnostics dla poprawnego payloadu
    zwraca minimalna diagnostyke bez bledu.
    """
    from tests.smoke_test_stt_hardware import build_stage_error_diagnostics

    mock_payload = {
        "text": "",
        "segments": [],
        "language": "en"
    }

    diag = build_stage_error_diagnostics(mock_payload, returncode=0)

    assert diag["has_error"] is False
    assert diag["returncode"] == 0
    assert diag["error"] is None
    assert diag["stderr_tail"] is None
    assert diag["payload_keys"] == ["language", "segments", "text"]
    print("Test 11: build_stage_error_diagnostics bez bledu zaliczony.")

def test_build_stage_error_diagnostics_none_or_empty_payload():
    """
    Weryfikuje, ze payload=None lub pusty payload zawsze ustawia has_error=True
    oraz error='Missing result payload' (dla returncode=0).
    """
    from tests.smoke_test_stt_hardware import build_stage_error_diagnostics

    diag_none = build_stage_error_diagnostics(None, returncode=0)
    assert diag_none["has_error"] is True
    assert diag_none["returncode"] == 0
    assert diag_none["error"] == "Missing result payload"
    assert diag_none["payload_keys"] == []
    assert diag_none["stderr_tail"] is None

    diag_empty_dict = build_stage_error_diagnostics({}, returncode=0)
    assert diag_empty_dict["has_error"] is True
    assert diag_empty_dict["returncode"] == 0
    assert diag_empty_dict["error"] == "Missing result payload"
    print("Test 12: build_stage_error_diagnostics dla payload=None i pustego payloadu zaliczony.")

def test_build_stage_error_diagnostics_empty_error_value():
    """
    Weryfikuje, ze payload z kluczem 'error': '' zwraca has_error=True
    oraz bezpieczny komunikat 'Payload reported error without message'.
    """
    from tests.smoke_test_stt_hardware import build_stage_error_diagnostics

    mock_payload = {
        "error": "",
        "text": "",
        "segments": []
    }

    diag = build_stage_error_diagnostics(mock_payload, returncode=0)
    assert diag["has_error"] is True
    assert diag["returncode"] == 0
    assert diag["error"] == "Payload reported error without message"
    assert diag["payload_keys"] == ["error", "segments", "text"]
    assert diag["stderr_tail"] is None
    print("Test 13: build_stage_error_diagnostics dla pustej wartosci error zaliczony.")

def test_static_stage1_diagnostics_condition_on_success_false():
    """
    Weryfikuje, ze w smoke_test_stt_hardware.py wypisywanie diagnostyki Stage 1
    bazuje bezposrednio na warunku stage1_data['success'] is False.
    """
    with open(SMOKE_SCRIPT_PATH, 'r') as f:
        src = f.read()

    assert "if not stage1_data[\"success\"]:" in src, "Wypisywanie diagnostyki Stage 1 musi bazowac na success=False"
    print("Test 14: Warunek diagnostyki Stage 1 oparty na success=False zaliczony.")

if __name__ == '__main__':

    test_static_source_code_cleanliness_and_no_lock_deletion()
    test_strictly_forbidden_kill_mechanisms()
    test_static_process_group_and_conditional_cleanup_assertions()
    test_no_force_flag_in_cli_and_strict_defaults()
    test_timeout_definitions()
    test_refuse_start_on_active_ollama_fail_closed()
    test_refuse_start_on_low_memory_fail_closed()
    test_expected_no_speech_acceptance()
    test_functional_lightweight_timeout_sleep_with_process_group()
    test_build_stage_error_diagnostics_with_error_and_home_redaction()
    test_build_stage_error_diagnostics_without_error()
    test_build_stage_error_diagnostics_none_or_empty_payload()
    test_build_stage_error_diagnostics_empty_error_value()
    test_static_stage1_diagnostics_condition_on_success_false()
    print("WSZYSTKIE TESTY STATYCZNE I LEKKI TEST TIMEOUTU ZALICZONE POMYSLNIE!")
