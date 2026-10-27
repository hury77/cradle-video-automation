#!/usr/bin/env python3
"""
smoke_test_stt_hardware.py — Jednorazowy kontrolowany smoke test sprzetowy STT

CEL I ZASADY BEZPIECZENSTWA:
1. Skrypt NIE MOZE byc uruchamiany automatycznie w CI/CD ani w runnerach orkiestracji.
2. Dziala wylacznie w oparciu o syntetyczny 3-sekundowy plik WAV (sinusoida 440 Hz)
   utworzony w lokalnym tempfile.mkdtemp().
3. Kategorycznie NIE importuje:
   - models.database ani models.models (zero ryzyka dotkniecia produkcyjnej bazy)
   - ComparisonService ani API Cradle
   - zadnych plikow produkcyjnych ani folderow uploads.
4. Pre-flight checks (BEZWZGLEDNY FAIL-CLOSED, bez flagi pomijajacej):
   - Odmawia uruchomienia, jesli wykryje aktywny proces 'ollama', 'demucs', 'whisper' lub 'mlx_whisper'.
   - Odmawia uruchomienia, jesli dostepna pamiec RAM w psutil.virtual_memory().available jest mniejsza niz 8 GiB.
5. Pomiary i telemetry:
   - Mierzy RSS procesu oraz pamiec systemowa przed i po kazdym etapie.
6. Kontrola czasu i timeouty:
   - Limit pojedynczego etapu: 60 s.
   - Limit calego smoke testu: 180 s.
   - Kazdy etap MLX/Demucs wykonywany jest w dedykowanej sesji/grupie procesow (start_new_session=True).
   - W przypadku TimeoutExpired wywolywane jest wylacznie os.killpg(proc.pid, signal.SIGTERM) dla calej grupy procesow.
   - Po wyslaniu SIGTERM oczekuje communicate(timeout=5).
   - Jesli grupa nadal zyje: NIE wysyla dalszego sygnalu, zwraca kontrolowany wynik
     timeout_process_still_running=True, raportuje PID i PGID na stdout i konczy sie niezerowym kodem.
   - Calkowity zakaz uzywania wymuszonego zakonczenia bezposredniego.
7. Kontrakt sukcesu dla syntetycznego audio:
   - Sukces oznacza poprawne uruchomienie transcribe_audio, zwrocenie slownika i brak nieobsluzonego wyjatku.
   - Pusty tekst / no-speech dla sinusoidy 440 Hz jest stanem calkowicie oczekiwanym i prawidlowym.
8. Raportowanie i czyszczenie:
   - Kluczowe metryki z raportu wypisywane sa na stdout przed wyjsciem.
   - Raport JSON zapisywany wylacznie wewnatrz temp_dir.
   - Jesli po timeout proces lub grupa nadal dziala:
     * NIE usuwa temp_dir w finally.
     * Wypisuje na stdout pelna sciezke katalogu diagnostycznego, PID i PGID.
     * Ustawia w raporcie cleanup_deferred=True.
     * Nie usuwa globalnego locka /tmp/nvc_heavy_model_mps.lock ani nie zabija procesu.
   - Przy zwyklym sukcesie lub procesie poprawnie zakonczonym przez SIGTERM usuwa wlasny temp_dir.
"""

import os
import sys
import json
import time
import shutil
import signal
import tempfile
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

MIN_REQUIRED_RAM_GIB = 8.0
STAGE_TIMEOUT_SEC = 60
GLOBAL_MAX_TIMEOUT_SEC = 180

def check_forbidden_imports():
    forbidden = [
        'models.database',
        'models.models',
        'services.comparison_service',
        'main'
    ]
    for mod in forbidden:
        if mod in sys.modules:
            raise RuntimeError(f"CRITICAL VIOLATION: Forbidden module already imported: {mod}")

def check_active_conflicting_processes() -> List[str]:
    import psutil
    conflicts = []
    current_pid = os.getpid()
    conflict_patterns = ['ollama', 'demucs', 'whisper', 'mlx_whisper']

    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if p.info['pid'] == current_pid:
                continue
            name = (p.info['name'] or '').lower()
            cmdline = ' '.join(p.info['cmdline'] or []).lower()

            if any(ide in cmdline for ide in ['antigravity', 'vscode', 'pycharm', 'sublime']):
                continue

            for pattern in conflict_patterns:
                if pattern in name or pattern in cmdline:
                    conflicts.append(f"{pattern} (PID {p.info['pid']}: {name})")
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return list(set(conflicts))

def check_available_system_ram(min_gib: float = MIN_REQUIRED_RAM_GIB) -> Tuple[float, bool]:
    import psutil
    mem = psutil.virtual_memory()
    avail_gib = mem.available / (1024 ** 3)
    return avail_gib, (avail_gib >= min_gib)

def get_system_ram_metrics() -> Dict[str, float]:
    import psutil
    mem = psutil.virtual_memory()
    return {
        "total_gib": mem.total / (1024 ** 3),
        "available_gib": mem.available / (1024 ** 3),
        "used_gib": mem.used / (1024 ** 3),
        "percent": mem.percent
    }

def get_process_rss_mb() -> float:
    import psutil
    return psutil.Process().memory_info().rss / (1024 * 1024)

def generate_synthetic_wav(target_path: Path, duration_sec: float = 3.0, sample_rate: int = 16000) -> None:
    import numpy as np
    import soundfile as sf
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    audio_data = (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(str(target_path), audio_data, sample_rate)

def run_stage_subprocess(cmd: List[str], timeout_sec: float) -> Tuple[int, str, str, bool, bool, Optional[int], Optional[int]]:
    """
    Wykonuje etap w kontrolowanym podprocesie z limitem czasu w osobnej grupie procesow (start_new_session=True).
    Zwraca: (returncode, stdout, stderr, timed_out, still_running, pid, pgid)

    Zachowanie przy timeout:
    1. Wysyla os.killpg(proc.pid, signal.SIGTERM) do calej grupy procesow.
    2. Czeka do 5s przez proc.communicate(timeout=5).
    3. Jesli proces/grupa nadal dziala:
       - NIE wysyla dalszych sygnalow.
       - Ustawia still_running=True.
       - Zwraca PID i PGID procesu do dalszej inspekcji.
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True
    )
    pid = proc.pid
    pgid = None
    try:
        pgid = os.getpgid(pid)
    except Exception:
        pgid = pid

    try:
        stdout, stderr = proc.communicate(timeout=timeout_sec)
        return proc.returncode, stdout, stderr, False, False, pid, pgid
    except subprocess.TimeoutExpired:
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception as e:
            pass

        try:
            stdout, stderr = proc.communicate(timeout=5)
            return -1, stdout, stderr, True, False, pid, pgid
        except subprocess.TimeoutExpired:
            # Proces/grupa nie odpowiedziala na SIGTERM w ciagu 5s.
            # Zgodnie z zasadami NIE wysylamy kolejnego sygnalu;
            # zwracamy kontrolowany status still_running wraz z PID i PGID.
            return -1, "", "Process group still running after SIGTERM and 5s grace period", True, True, pid, pgid

def build_stage_error_diagnostics(
    payload: Optional[Dict[str, Any]],
    returncode: int,
    temp_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Buduje zredagowane metadane diagnostyczne dla etapu smoke testu, ktory zwrocil blad.
    Redaguje sciezke katalogu domowego (~), ogranicza rozmiar tekstow do max 500 znakow,
    oraz nie ujawnia pelnych transkrypcji ani config JSON.
    """
    if not payload:
        return {
            "returncode": returncode,
            "has_error": True,
            "error": "Missing result payload" if returncode == 0 else f"Process exited with code {returncode}",
            "payload_keys": [],
            "stderr_tail": None
        }

    payload_keys = sorted(list(payload.keys()))
    has_error_key = ("error" in payload) or ("error_message" in payload)
    raw_error = payload.get("error") if "error" in payload else payload.get("error_message")
    has_error = has_error_key or (returncode != 0)

    if not has_error:
        return {
            "returncode": returncode,
            "has_error": False,
            "error": None,
            "payload_keys": payload_keys,
            "stderr_tail": None
        }

    if has_error_key and (raw_error is None or str(raw_error).strip() == ""):
        err_str = "Payload reported error without message"
    elif raw_error is not None:
        err_str = str(raw_error)
    else:
        err_str = f"Subprocess failed with code {returncode}"

    # Redagowanie sciezki domowej
    home_dir = str(Path.home())
    err_str = err_str.replace(home_dir, "~")

    # Wykrywanie i wyodrebnienie stderr_tail jesli obecne w komunikacie bledu
    stderr_tail = None
    if "stderr tail:" in err_str:
        parts = err_str.split("stderr tail:", 1)
        stderr_tail = parts[1].strip()[:500]

    # Ograniczenie dlugosci bledu do 500 znakow
    truncated_error = err_str[:500]

    return {
        "returncode": returncode,
        "has_error": True,
        "error": truncated_error,
        "payload_keys": payload_keys,
        "stderr_tail": stderr_tail
    }


def run_smoke_test(with_demucs: bool = False) -> int:
    check_forbidden_imports()

    print("==================================================")
    print("STT Hardware Smoke Test — Pre-flight Checks")
    print("==================================================")

    # 1. Bezwzgledna odmowa przy aktywnych procesach rywalizujacych
    active_conflicts = check_active_conflicting_processes()
    if active_conflicts:
        msg = f"REJECTED: Conflicting AI/MPS processes active: {', '.join(active_conflicts)}"
        print(f"STOP: {msg}")
        print("Aborting smoke test to prevent hardware deadlock / memory contention.")
        return 1

    # 2. Bezwzgledna odmowa przy zbyt malej pamieci RAM
    avail_gib, is_ram_ok = check_available_system_ram()
    print(f"RAM Available: {avail_gib:.2f} GiB (Required: {MIN_REQUIRED_RAM_GIB} GiB)")
    if not is_ram_ok:
        msg = f"REJECTED: Insufficient available RAM: {avail_gib:.2f} GiB < {MIN_REQUIRED_RAM_GIB} GiB."
        print(f"STOP: {msg}")
        print("Aborting smoke test to prevent Out-Of-Memory / system swap thrashing.")
        return 2

    global_start_time = time.time()
    temp_dir = Path(tempfile.mkdtemp(prefix="stt_smoke_hw_"))
    synthetic_wav = temp_dir / "synth_3s.wav"
    report_file = temp_dir / "smoke_test_report.json"

    report: Dict[str, Any] = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "initial_ram": get_system_ram_metrics(),
        "initial_rss_mb": get_process_rss_mb(),
        "stages": {},
        "success": False,
        "error": None,
        "cleanup_deferred": False,
        "diagnostic_dir": str(temp_dir)
    }

    try:
        generate_synthetic_wav(synthetic_wav, duration_sec=3.0)
        print(f"Generated 3s synthetic WAV: {synthetic_wav} ({synthetic_wav.stat().st_size} bytes)")

        backend_dir = Path(__file__).parent.parent
        backend_dir_str = str(backend_dir.resolve())
        python_exec = sys.executable

        # --- ETAP 1: MLX Whisper Single-Inference (Subprocess z limitem STAGE_TIMEOUT_SEC) ---
        print("--- Stage 1: transcribe_audio() (MLX Whisper) ---")
        stage1_output_json = temp_dir / "stage1_whisper_result.json"
        stage1_code = (
            f"import sys, json; sys.path.insert(0, '{backend_dir_str}'); "
            f"from services.audio_service import transcribe_audio; "
            f"res = transcribe_audio(audio_path='{synthetic_wav}', language='en', model_name='small'); "
            f"json.dump(res, open('{stage1_output_json}', 'w'))"
        )
        stage1_rss_before = get_process_rss_mb()
        t1_start = time.time()

        if (time.time() - global_start_time) > GLOBAL_MAX_TIMEOUT_SEC:
            report["error"] = f"Global timeout of {GLOBAL_MAX_TIMEOUT_SEC}s exceeded before Stage 1"
            print(f"STOP: {report['error']}")
            return 3

        rc, out, err, timed_out, still_running, proc_pid, proc_pgid = run_stage_subprocess(
            [python_exec, "-c", stage1_code],
            timeout_sec=STAGE_TIMEOUT_SEC
        )
        t1_duration = time.time() - t1_start
        stage1_rss_after = get_process_rss_mb()

        stage1_data: Dict[str, Any] = {
            "duration_sec": t1_duration,
            "timed_out": timed_out,
            "timeout_process_still_running": still_running,
            "process_pid": proc_pid,
            "process_pgid": proc_pgid,
            "returncode": rc,
            "rss_before_mb": stage1_rss_before,
            "rss_after_mb": stage1_rss_after,
            "rss_growth_mb": max(0.0, stage1_rss_after - stage1_rss_before),
            "transcription_result": None,
            "is_expected_no_speech": False,
            "success": False
        }

        if timed_out:
            if still_running:
                report["cleanup_deferred"] = True
                stage1_data["error"] = f"Stage 1 timed out after {STAGE_TIMEOUT_SEC}s and process group (PID {proc_pid}, PGID {proc_pgid}) is still running after SIGTERM"
                print(f"STOP: Stage 1 TIMED OUT after {STAGE_TIMEOUT_SEC}s. Process group PID {proc_pid}, PGID {proc_pgid} is still active. No further signals sent.")
                print(f"DIAGNOSTIC DIR PRESERVED: {temp_dir}")
            else:
                stage1_data["error"] = f"Stage 1 timed out after {STAGE_TIMEOUT_SEC}s (terminated cleanly via SIGTERM)"
                print(f"STOP: Stage 1 TIMED OUT after {STAGE_TIMEOUT_SEC}s (terminated cleanly via SIGTERM)")
            report["stages"]["transcribe_audio"] = stage1_data
            return 3
        elif rc != 0:
            stage1_data["error"] = f"Subprocess failed with code {rc}: {err.strip()}"
            print(f"STOP: Stage 1 FAILED (code {rc}): {err.strip()}")
            report["stages"]["transcribe_audio"] = stage1_data
            return 4
        else:
            if stage1_output_json.exists():
                with open(stage1_output_json) as jf:
                    whisper_payload = json.load(jf)
                stage1_data["transcription_result"] = whisper_payload
                detected_text = whisper_payload.get("text", "").strip()
                has_error = "error" in whisper_payload
                stage1_data["is_expected_no_speech"] = (detected_text == "" or len(detected_text) < 10)
                stage1_data["success"] = (not has_error)
                diag = build_stage_error_diagnostics(whisper_payload, rc, temp_dir=temp_dir)
                stage1_data["diagnostics"] = diag
                if not stage1_data["success"]:
                    stage1_data["error"] = diag["error"]
                    print(f"DIAGNOSTIC: Stage 1 failed (returncode={rc})")
                    print(f"  payload_keys: {diag['payload_keys']}")
                    print(f"  error: {diag['error']}")
                    if diag["stderr_tail"]:
                        print(f"  stderr_tail: {diag['stderr_tail']}")
            else:
                stage1_data["error"] = "Output result file missing"
                stage1_data["success"] = False
                diag = build_stage_error_diagnostics(None, rc, temp_dir=temp_dir)
                stage1_data["diagnostics"] = diag
                print(f"DIAGNOSTIC: Stage 1 failed (missing output file, returncode={rc})")
                print(f"  payload_keys: {diag['payload_keys']}")
                print(f"  error: {diag['error']}")

            report["stages"]["transcribe_audio"] = stage1_data
            print(f"Stage 1 completed in {t1_duration:.2f}s (success={stage1_data['success']}, expected_no_speech={stage1_data['is_expected_no_speech']})")

        # --- ETAP 2 (OPCJONALNY): Demucs Source Separation ---
        if with_demucs:
            print("--- Stage 2: separate_sources() (Demucs) [--with-demucs enabled] ---")
            elapsed_so_far = time.time() - global_start_time
            remaining_global = GLOBAL_MAX_TIMEOUT_SEC - elapsed_so_far
            if remaining_global <= 0:
                report["error"] = f"Global timeout of {GLOBAL_MAX_TIMEOUT_SEC}s exceeded before Stage 2"
                print(f"STOP: {report['error']}")
                return 3

            stage2_timeout = min(STAGE_TIMEOUT_SEC, int(remaining_global))
            stage2_output_json = temp_dir / "stage2_demucs_result.json"
            demucs_out_dir = temp_dir / "demucs_out"
            stage2_code = (
                f"import sys, json; sys.path.insert(0, '{backend_dir_str}'); "
                f"from services.audio_service import separate_sources; "
                f"res = separate_sources(audio_path='{synthetic_wav}', output_dir='{demucs_out_dir}'); "
                f"json.dump(res, open('{stage2_output_json}', 'w'))"
            )
            stage2_rss_before = get_process_rss_mb()
            t2_start = time.time()

            rc2, out2, err2, timed_out2, still_running2, proc_pid2, proc_pgid2 = run_stage_subprocess(
                [python_exec, "-c", stage2_code],
                timeout_sec=stage2_timeout
            )
            t2_duration = time.time() - t2_start
            stage2_rss_after = get_process_rss_mb()

            stage2_data: Dict[str, Any] = {
                "duration_sec": t2_duration,
                "timed_out": timed_out2,
                "timeout_process_still_running": still_running2,
                "process_pid": proc_pid2,
                "process_pgid": proc_pgid2,
                "returncode": rc2,
                "rss_before_mb": stage2_rss_before,
                "rss_after_mb": stage2_rss_after,
                "rss_growth_mb": max(0.0, stage2_rss_after - stage2_rss_before),
                "success": False
            }

            if timed_out2:
                if still_running2:
                    report["cleanup_deferred"] = True
                    stage2_data["error"] = f"Stage 2 timed out after {stage2_timeout}s and process group (PID {proc_pid2}, PGID {proc_pgid2}) is still running after SIGTERM"
                    print(f"STOP: Stage 2 TIMED OUT after {stage2_timeout}s. Process group PID {proc_pid2}, PGID {proc_pgid2} is still active. No further signals sent.")
                    print(f"DIAGNOSTIC DIR PRESERVED: {temp_dir}")
                else:
                    stage2_data["error"] = f"Stage 2 timed out after {stage2_timeout}s (terminated cleanly via SIGTERM)"
                    print(f"STOP: Stage 2 TIMED OUT after {stage2_timeout}s (terminated cleanly via SIGTERM)")
                report["stages"]["separate_sources"] = stage2_data
                return 3
            elif rc2 != 0:
                stage2_data["error"] = f"Subprocess failed with code {rc2}: {err2.strip()}"
                print(f"STOP: Stage 2 FAILED (code {rc2}): {err2.strip()}")
                report["stages"]["separate_sources"] = stage2_data
                return 4
            else:
                if stage2_output_json.exists():
                    with open(stage2_output_json) as jf2:
                        demucs_payload = json.load(jf2)
                    stage2_data["demucs_result"] = demucs_payload
                    stage2_data["success"] = demucs_payload.get("success", False)
                report["stages"]["separate_sources"] = stage2_data
                print(f"Stage 2 completed in {t2_duration:.2f}s (success={stage2_data['success']})")
        else:
            print("--- Stage 2: separate_sources() SKIPPED (use --with-demucs to enable) ---")

        report["success"] = report["stages"].get("transcribe_audio", {}).get("success", False)
        report["total_duration_sec"] = time.time() - global_start_time
        report["final_rss_mb"] = get_process_rss_mb()
        report["final_ram"] = get_system_ram_metrics()

        with open(report_file, 'w') as rf:
            json.dump(report, rf, indent=2)

        return 0 if report["success"] else 5

    finally:
        print("==================================================")
        print("STT Hardware Smoke Test — Podsumowanie Wynikow")
        print("==================================================")
        print(f"Status ogolny (success): {report.get('success', False)}")
        print(f"Calkowity czas wykonania: {report.get('total_duration_sec', 0.0):.2f}s / max {GLOBAL_MAX_TIMEOUT_SEC}s")
        print(f"Poczatkowy RAM dostepny: {report.get('initial_ram', {}).get('available_gib', 0.0):.2f} GiB")
        if "final_ram" in report:
            print(f"Koncowy RAM dostepny: {report['final_ram'].get('available_gib', 0.0):.2f} GiB")

        st1 = report.get("stages", {}).get("transcribe_audio")
        if st1:
            still_run1 = st1.get('timeout_process_still_running', False)
            pid1_info = f", PID={st1.get('process_pid')}, PGID={st1.get('process_pgid')}, still_running={still_run1}" if st1.get('timed_out') else ""
            print(f"Etap 1 (MLX Whisper): duration={st1.get('duration_sec', 0.0):.2f}s, success={st1.get('success')}, expected_no_speech={st1.get('is_expected_no_speech')}{pid1_info}, RSS={st1.get('rss_before_mb', 0.0):.1f}MB->{st1.get('rss_after_mb', 0.0):.1f}MB")

        st2 = report.get("stages", {}).get("separate_sources")
        if st2:
            still_run2 = st2.get('timeout_process_still_running', False)
            pid2_info = f", PID={st2.get('process_pid')}, PGID={st2.get('process_pgid')}, still_running={still_run2}" if st2.get('timed_out') else ""
            print(f"Etap 2 (Demucs): duration={st2.get('duration_sec', 0.0):.2f}s, success={st2.get('success')}{pid2_info}, RSS={st2.get('rss_before_mb', 0.0):.1f}MB->{st2.get('rss_after_mb', 0.0):.1f}MB")

        if report.get("error"):
            print(f"Blad wykonania: {report['error']}")

        # Warunkowy cleanup:
        # Jesli proces/grupa nadal dziala, NIE usuwamy katalogu tymczasowego
        if report.get("cleanup_deferred") is True:
            print(f"UWAGA: cleanup_deferred=true — katalog tymczasowy zachowany dla diagnostyki: {temp_dir}")
        else:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
                print(f"Katalog tymczasowy {temp_dir} pomyslnie usuniety.")

        print("==================================================")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="STT Hardware Smoke Test")
    parser.add_argument('--with-demucs', action='store_true', default=False,
                        help="Enable optional Demucs source separation stage (disabled by default)")
    args = parser.parse_args()

    sys.exit(run_smoke_test(with_demucs=args.with_demucs))
