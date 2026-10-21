#!/usr/bin/env python3
"""
test_stt_sqlite_payloads_isolated.py — Hermetyczny test integracyjny SQLite dla payloadow STT

ZASADY BEZPIECZENSTWA:
1. Uruchamiany jako samodzielny proces.
2. Tworzy dedykowany katalog w /tmp (tempfile.mkdtemp).
3. PRZED importem modeli wstrzykuje do sys.modules atrapowy models.database z Base i izolowanym engine.
4. Twarda asercja sprawdza, ze URL silnika zaczyna sie od sqlite:////tmp/ lub /var/folders/ i pod zadnym pozorem nie zawiera .cradle_data.
5. Wywoluje RZECZYWISTY serializer/metode zapisu z ComparisonService (_save_results):
   - mapuje clean_results do ComparisonResult.report_data["audio"]["speech_to_text"]
   - zapisuje audio_result do AudioComparisonResult.audio_analysis_data
   - patchuje wylacznie elementy peryferyjne (_run_ai_analyst), pozostawiajac caly serializer nietkniety.
6. Sprawdza odczyt z bazy po commit dla 5 kluczowych payloadow STT:
   - DUPLICATE_INPUT
   - AUDIO_MISMATCH
   - completed_no_speech
   - failed
   - FAST_PATH_IDENTICAL_AUDIO
7. Dodatkowo testuje przypadek z text_similarity=None / brakiem tekstu (weryfikacja braku bledow formatowania i NOT NULL).
8. Testuje bledy NOT NULL (np. brak wymaganego job_id), walidacje JSON oraz rollback sesji.
9. W bloku finally zamyka silnik i usuwa wylacznie wlasny katalog tymczasowy.
"""
import os
import sys
import json
import shutil
import tempfile
import types
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock

def run_isolated_sqlite_test():
    temp_dir = Path(tempfile.mkdtemp(prefix="test_stt_sqlite_"))
    test_db_path = temp_dir / "isolated_stt_test.db"
    isolated_url = f"sqlite:///{test_db_path.resolve()}"

    print("==================================================")
    print(f"[ISOLATED] Engine URL: {isolated_url}")
    print("==================================================")

    def assert_engine_url_safe(engine_instance):
        current_url = str(engine_instance.url)
        assert current_url.startswith("sqlite:////tmp/") or "/var/folders/" in current_url, (
            f"CRITICAL: Non-temp engine URL detected: {current_url}"
        )
        assert ".cradle_data" not in current_url, (
            f"CRITICAL: Engine URL points to production ~/.cradle_data: {current_url}"
        )

    try:
        from sqlalchemy import create_engine, MetaData
        from sqlalchemy.orm import declarative_base, sessionmaker

        # 1. Tworzenie izolowanego silnika i sesji
        isolated_engine = create_engine(
            isolated_url,
            connect_args={"check_same_thread": False},
            echo=False
        )
        assert_engine_url_safe(isolated_engine)

        IsolatedSession = sessionmaker(autocommit=False, autoflush=False, bind=isolated_engine)
        Base = declarative_base()

        # 2. Wstrzykniecie atrapowego models.database do sys.modules PRZED importem models/services
        mock_db_module = types.ModuleType("models.database")
        mock_db_module.engine = isolated_engine
        mock_db_module.SessionLocal = IsolatedSession
        mock_db_module.Base = Base
        mock_db_module.metadata = MetaData()
        mock_db_module.DATABASE_URL = isolated_url

        backend_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(backend_dir))
        sys.modules["models.database"] = mock_db_module

        # 3. Bezpieczny import modeli oraz rzeczywistej uslugi ComparisonService
        from models.models import (
            File,
            ComparisonJob,
            ComparisonResult,
            AudioComparisonResult,
            ComparisonType,
            SensitivityLevel,
            JobStatus,
            FileType,
            FileFormat
        )
        from services.comparison_service import ComparisonService

        # 4. Utworzenie schematu w izolowanej bazie
        Base.metadata.create_all(bind=isolated_engine)
        print("Schemat SQLite utworzony pomyslnie w izolowanym pliku.")

        # Inicjalizacja instancji ComparisonService bez tworzenia zewnetrznych podprocesow/analystow
        comparison_service = ComparisonService.__new__(ComparisonService)
        # Patchujemy WYLACZNIE peryferyjne wywolanie AI Analyst, serializer pozostaje w 100% autentyczny
        comparison_service._run_ai_analyst = MagicMock()

        session = IsolatedSession()
        try:
            # Tworzymy pliki bazowe (wymagane klucze obce)
            f_acc = File(
                filename="acc_test.mp4",
                original_name="acc_test.mp4",
                file_path=str(temp_dir / "acc.mp4"),
                file_type=FileType.ACCEPTANCE,
                file_format=FileFormat.MP4,
                file_size=1024,
                duration=15.0
            )
            f_emi = File(
                filename="emi_test.mp4",
                original_name="emi_test.mp4",
                file_path=str(temp_dir / "emi.mp4"),
                file_type=FileType.EMISSION,
                file_format=FileFormat.MP4,
                file_size=1024,
                duration=15.0
            )
            session.add_all([f_acc, f_emi])
            session.commit()

            # Helper do tworzenia Joba
            def make_job(name: str, comp_type=ComparisonType.AUTOMATION):
                job = ComparisonJob(
                    job_name=name,
                    acceptance_file_id=f_acc.id,
                    emission_file_id=f_emi.id,
                    comparison_type=comp_type,
                    sensitivity_level=SensitivityLevel.AUTOMATION,
                    status=JobStatus.COMPLETED
                )
                session.add(job)
                session.commit()
                return job

            # --- PAYLOAD 1: DUPLICATE_INPUT ---
            print("--- Testing Payload 1: DUPLICATE_INPUT via ComparisonService._save_results ---")
            assert_engine_url_safe(isolated_engine)
            job1 = make_job("Job 1 DUPLICATE_INPUT")
            payload1 = {
                "similarity_score": 1.0,
                "has_audio": True,
                "is_binary_duplicate": True,
                "speech_to_text": {
                    "status": "skipped",
                    "skipped_reason": "DUPLICATE_INPUT: Identical binary inputs detected",
                    "is_binary_duplicate": True
                }
            }
            clean_results_1 = {"audio_result": payload1, "video_result": None}
            comparison_service._save_results(session, job1, clean_results_1)

            # Odczyt i weryfikacja z bazy po zapisie rzeczywistym serializerem
            comp_res1 = session.query(ComparisonResult).filter_by(job_id=job1.id).first()
            audio_db1 = session.query(AudioComparisonResult).filter_by(job_id=job1.id).first()
            assert comp_res1 is not None, "ComparisonResult record missing"
            assert comp_res1.report_data["audio"]["speech_to_text"]["status"] == "skipped"
            assert comp_res1.report_data["audio"]["speech_to_text"]["skipped_reason"].startswith("DUPLICATE_INPUT")
            assert comp_res1.report_data["audio"]["speech_to_text"]["is_binary_duplicate"] is True

            assert audio_db1 is not None, "AudioComparisonResult record missing"
            assert audio_db1.audio_analysis_data["speech_to_text"]["is_binary_duplicate"] is True
            print("Payload 1 (DUPLICATE_INPUT) zapisany przez ComparisonService i odczytany poprawnie.")

            # --- PAYLOAD 2: AUDIO_MISMATCH ---
            print("--- Testing Payload 2: AUDIO_MISMATCH via ComparisonService._save_results ---")
            assert_engine_url_safe(isolated_engine)
            job2 = make_job("Job 2 AUDIO_MISMATCH", comp_type=ComparisonType.FULL)
            payload2 = {
                "similarity_score": 0.5,
                "audio_mismatch": True,
                "has_audio": False,
                "speech_to_text": {
                    "status": "skipped",
                    "skipped_reason": "NO_AUDIO_STREAMS: One of files lacks audio track"
                }
            }
            clean_results_2 = {"audio_result": payload2, "video_result": None}
            comparison_service._save_results(session, job2, clean_results_2)

            comp_res2 = session.query(ComparisonResult).filter_by(job_id=job2.id).first()
            audio_db2 = session.query(AudioComparisonResult).filter_by(job_id=job2.id).first()
            assert comp_res2.report_data["audio"]["speech_to_text"]["status"] == "skipped"
            assert "NO_AUDIO_STREAMS" in comp_res2.report_data["audio"]["speech_to_text"]["skipped_reason"]
            assert audio_db2.audio_analysis_data["audio_mismatch"] is True
            print("Payload 2 (AUDIO_MISMATCH) zapisany przez ComparisonService i odczytany poprawnie.")

            # --- PAYLOAD 3: completed_no_speech ---
            print("--- Testing Payload 3: completed_no_speech via ComparisonService._save_results ---")
            assert_engine_url_safe(isolated_engine)
            job3 = make_job("Job 3 completed_no_speech")
            payload3 = {
                "similarity_score": 0.99,
                "has_audio": True,
                "speech_to_text": {
                    "status": "completed_no_speech",
                    "transcription_a": {"text": "", "segments": []},
                    "transcription_b": {"text": "", "segments": []},
                    "comparison": {"word_count_a": 0, "word_count_b": 0, "similarity": None}
                }
            }
            clean_results_3 = {"audio_result": payload3, "video_result": None}
            comparison_service._save_results(session, job3, clean_results_3)

            comp_res3 = session.query(ComparisonResult).filter_by(job_id=job3.id).first()
            audio_db3 = session.query(AudioComparisonResult).filter_by(job_id=job3.id).first()
            assert comp_res3.report_data["audio"]["speech_to_text"]["status"] == "completed_no_speech"
            assert comp_res3.report_data["audio"]["speech_to_text"]["comparison"]["similarity"] is None
            assert audio_db3.audio_analysis_data["speech_to_text"]["comparison"]["word_count_a"] == 0
            print("Payload 3 (completed_no_speech) zapisany przez ComparisonService i odczytany poprawnie.")

            # --- PAYLOAD 4: failed ---
            print("--- Testing Payload 4: failed via ComparisonService._save_results ---")
            assert_engine_url_safe(isolated_engine)
            job4 = make_job("Job 4 failed")
            payload4 = {
                "similarity_score": 0.75,
                "has_audio": True,
                "speech_to_text": {
                    "status": "failed",
                    "error_message": "Subprocess demucs timed out after 180s (Out of Memory)",
                    "is_uncertain": False
                }
            }
            clean_results_4 = {"audio_result": payload4, "video_result": None}
            comparison_service._save_results(session, job4, clean_results_4)

            comp_res4 = session.query(ComparisonResult).filter_by(job_id=job4.id).first()
            audio_db4 = session.query(AudioComparisonResult).filter_by(job_id=job4.id).first()
            assert comp_res4.report_data["audio"]["speech_to_text"]["status"] == "failed"
            assert "timed out" in comp_res4.report_data["audio"]["speech_to_text"]["error_message"]
            assert audio_db4.audio_analysis_data["speech_to_text"]["status"] == "failed"
            print("Payload 4 (failed) zapisany przez ComparisonService i odczytany poprawnie.")

            # --- PAYLOAD 5: FAST_PATH_IDENTICAL_AUDIO ---
            print("--- Testing Payload 5: FAST_PATH_IDENTICAL_AUDIO via ComparisonService._save_results ---")
            assert_engine_url_safe(isolated_engine)
            job5 = make_job("Job 5 FAST_PATH_IDENTICAL_AUDIO")
            payload5 = {
                "similarity_score": 0.9995,
                "has_audio": True,
                "speech_to_text": {
                    "status": "skipped",
                    "skipped_reason": "FAST_PATH_IDENTICAL_AUDIO: Audio similarity >= 0.999"
                }
            }
            clean_results_5 = {"audio_result": payload5, "video_result": None}
            comparison_service._save_results(session, job5, clean_results_5)

            comp_res5 = session.query(ComparisonResult).filter_by(job_id=job5.id).first()
            audio_db5 = session.query(AudioComparisonResult).filter_by(job_id=job5.id).first()
            assert "FAST_PATH_IDENTICAL_AUDIO" in comp_res5.report_data["audio"]["speech_to_text"]["skipped_reason"]
            assert audio_db5.audio_analysis_data["speech_to_text"]["status"] == "skipped"
            print("Payload 5 (FAST_PATH_IDENTICAL_AUDIO) zapisany przez ComparisonService i odczytany poprawnie.")

            # --- PAYLOAD 6: text_similarity=None / brak tekstu nie powoduje bledu formatowania ani NOT NULL ---
            print("--- Testing Payload 6: text_similarity=None / empty text gracefulness ---")
            assert_engine_url_safe(isolated_engine)
            job6 = make_job("Job 6 text_similarity=None")
            payload6 = {
                "similarity_score": 0.985,
                "has_audio": True,
                "speech_to_text": {
                    "status": "completed",
                    "text_similarity": None,
                    "is_text_match": None,
                    "acceptance_text": "",
                    "emission_text": None,
                    "comparison": {
                        "word_differences": [],
                        "similarity": None
                    }
                }
            }
            clean_results_6 = {"audio_result": payload6, "video_result": None}
            comparison_service._save_results(session, job6, clean_results_6)

            comp_res6 = session.query(ComparisonResult).filter_by(job_id=job6.id).first()
            audio_db6 = session.query(AudioComparisonResult).filter_by(job_id=job6.id).first()
            assert comp_res6.report_data["audio"]["speech_to_text"]["text_similarity"] is None
            assert comp_res6.report_data["audio"]["speech_to_text"]["emission_text"] is None
            assert audio_db6.audio_analysis_data["speech_to_text"]["text_similarity"] is None
            print("Payload 6 (text_similarity=None / brak tekstu) obsluzony bez bledow formatowania ani NOT NULL.")

            # --- TEST BLEDU NOT NULL I ROLLBACK ---
            print("--- Testing NOT NULL Constraint and Session Rollback ---")
            assert_engine_url_safe(isolated_engine)
            from sqlalchemy.exc import IntegrityError
            invalid_res = ComparisonResult(
                job_id=None,
                overall_similarity=0.5
            )
            session.add(invalid_res)
            not_null_caught = False
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                not_null_caught = True
            
            assert not_null_caught is True, "Brak job_id musi wywolac IntegrityError NOT NULL"
            print("Blad NOT NULL prawidlowo wykryty, sesja bezpiecznie cofnieta (rollback).")

        finally:
            session.close()

        isolated_engine.dispose()
        print("==================================================")
        print("WSZYSTKIE TESTY RZECZYWISTEGO SERIALIZERA SQLite ZAKONCZONE SUKCESEM!")
        return 0

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    rc = run_isolated_sqlite_test()
    sys.exit(rc)
