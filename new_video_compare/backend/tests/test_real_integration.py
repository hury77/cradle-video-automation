# backend/tests/test_real_integration.py
import os
import requests
import json
import asyncio
import websockets
from pathlib import Path


def find_cradle_files(cradle_id):
    """Znajdź pliki akcept i emis w katalogu CradleID"""
    media_path = Path("media/downloads") / str(cradle_id)

    if not media_path.exists():
        print(f"❌ Katalog {media_path} nie istnieje!")
        return None, None

    files = list(media_path.glob("*"))
    video_files = [
        f for f in files if f.suffix.lower() in [".mp4", ".mov", ".mxf", ".avi"]
    ]

    print(f"📁 Znaleziono {len(video_files)} plików wideo w {media_path}")
    for f in video_files:
        print(f"   📄 {f.name}")

    if len(video_files) < 2:
        print("❌ Potrzeba minimum 2 plików wideo (akcept + emis)")
        return None, None

    # Inteligentne wykrywanie akcept vs emis
    akcept_file = None
    emis_file = None

    for file in video_files:
        name_lower = file.name.lower()
        if "akcept" in name_lower or "accept" in name_lower:
            akcept_file = str(file)
        elif "emis" in name_lower or "emission" in name_lower:
            emis_file = str(file)

    # Jeśli nie znaleziono po nazwach, weź pierwsze 2
    if not akcept_file or not emis_file:
        print("⚠️  Nie rozpoznano plików po nazwach, biorę pierwsze 2")
        akcept_file = str(video_files[0])
        emis_file = str(video_files[1])

    print(f"✅ AKCEPT: {Path(akcept_file).name}")
    print(f"✅ EMIS:   {Path(emis_file).name}")

    return akcept_file, emis_file


async def monitor_job_progress(job_id):
    """Monitor postępu przez WebSocket"""
    uri = "ws://127.0.0.1:8001/ws/connect"

    try:
        async with websockets.connect(uri) as websocket:
            print(f"🔌 Połączono z WebSocket")

            # Odbierz welcome message
            welcome = await websocket.recv()
            print(
                f"📨 Welcome: {json.loads(welcome).get('data', {}).get('message', 'Connected')}"
            )

            # Subskrybuj job
            subscribe_msg = {"action": "subscribe_job", "data": {"job_id": job_id}}
            await websocket.send(json.dumps(subscribe_msg))
            print(f"📡 Subskrybuję job {job_id}")

            # Słuchaj przez 5 minut
            timeout_count = 0
            updates_received = 0

            while timeout_count < 60:  # 5 min = 300s / 5s = 60 timeouts
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)

                    if data.get("action") == "job_subscribed":
                        print(f"✅ Subskrypcja potwierdzona")
                        continue

                    if data.get("action") == "progress_update":
                        updates_received += 1
                        progress_data = data.get("data", {})
                        stage = progress_data.get("stage", "unknown")
                        percent = progress_data.get("overall_percent", 0)
                        details = progress_data.get("details", "")

                        print(f"📊 [{stage}] {percent:.1f}% - {details}")

                        if percent >= 100 or stage == "completed":
                            print("🎉 Zadanie ukończone!")
                            break

                    timeout_count = 0  # Reset timeout po otrzymaniu wiadomości

                except asyncio.TimeoutError:
                    timeout_count += 1
                    if timeout_count % 12 == 0:  # Co minutę
                        print(f"⏱️  Czekam na aktualizacje... ({timeout_count * 5}s)")

            print(f"📈 Otrzymano {updates_received} aktualizacji postępu")

    except Exception as e:
        print(f"❌ WebSocket error: {e}")


def create_comparison_job(cradle_id):
    """Stwórz zadanie porównania używając auto-pair"""
    # Znajdę pliki (for info only)
    akcept_file, emis_file = find_cradle_files(cradle_id)

    if not akcept_file or not emis_file:
        print("❌ Nie znaleziono plików lokalnie")
        return None

    # Użyj auto-pair endpoint
    url = f"http://127.0.0.1:8001/api/v1/compare/auto-pair/{cradle_id}"

    data = {"job_name": f"Integration_Test_{cradle_id}", "comparison_type": "full"}

    print(f"🚀 Tworzę zadanie przez auto-pair...")
    print(f"   🏷️  Job Name: {data['job_name']}")
    print(f"   🔍 Cradle ID: {cradle_id}")
    print(f"   📥 Lokalnie znalezione pliki:")
    print(f"      Akcept: {Path(akcept_file).name}")
    print(f"      Emis:   {Path(emis_file).name}")

    try:
        response = requests.post(url, data=data, timeout=30)
        print(f"📡 Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            job_id = result.get("id")  # Zmienione z "job_id" na "id"
            print(f"✅ Zadanie utworzone: {job_id}")
            print(f"📋 Status: {result.get('status', 'unknown')}")
            return job_id
        else:
            print(f"❌ Błąd API: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Błąd połączenia: {e}")
        return None


def check_api_endpoints():
    """Sprawdź podstawowe endpointy API"""
    base_url = "http://127.0.0.1:8001"

    endpoints = [
        ("/health", "API Health"),
        ("/ws/health", "WebSocket Health"),
        ("/ws/stats", "WebSocket Stats"),
    ]

    print("🔍 Sprawdzam endpointy API...")
    for endpoint, name in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            status = (
                "✅ OK" if response.status_code == 200 else f"❌ {response.status_code}"
            )
            print(f"   {name}: {status}")
        except Exception as e:
            print(f"   {name}: ❌ Error - {e}")


if __name__ == "__main__":
    print("🎯 New Video Compare - Integration Test z Prawdziwymi Plikami")
    print("=" * 60)

    # Twój CradleID
    cradle_id = "123456"

    print(f"📁 Testuję CradleID: {cradle_id}")

    # Sprawdź API endpoints
    check_api_endpoints()

    # Sprawdź czy główny serwer działa
    try:
        health = requests.get("http://127.0.0.1:8001/health", timeout=5)
        if health.status_code == 200:
            print(f"🏥 Główny serwer: ✅ OK")
        else:
            print(f"🏥 Główny serwer: ❌ Status {health.status_code}")
    except Exception as e:
        print("❌ Serwer nie odpowiada! Sprawdź czy działa:")
        print("   python3 -m uvicorn backend.main:app --reload --port 8001")
        exit(1)

    print("-" * 60)

    # Stwórz zadanie
    job_id = create_comparison_job(cradle_id)

    if job_id:
        print(f"\n🔄 Monitoruję postęp zadania {job_id}...")
        print("⏱️  Naciśnij Ctrl+C aby przerwać monitoring")

        try:
            asyncio.run(monitor_job_progress(job_id))
            print("\n🎉 Test integracyjny zakończony pomyślnie!")
        except KeyboardInterrupt:
            print("\n⛔ Test przerwany przez użytkownika")
        except Exception as e:
            print(f"\n❌ Błąd podczas monitoringu: {e}")
    else:
        print("❌ Nie udało się utworzyć zadania - sprawdź logi serwera")
        print("\n💡 Możliwe przyczyny:")
        print("   - Brak Celery workers (Redis + workers)")
        print("   - Błędne ścieżki do plików")
        print("   - Brakujące dependencies")
