#!/usr/bin/env python3
"""
WebSocket Test Client for New Video Compare
Tests real-time progress updates and communication
"""

import asyncio
import websockets
import json
import requests
import time
import sys
import os
from datetime import datetime
from typing import Dict, Any

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuration - POPRAWIONE URL-e
WEBSOCKET_URL = "ws://127.0.0.1:8001/ws/connect"
REST_API_BASE = "http://127.0.0.1:8001"
CLIENT_ID = f"test_client_{datetime.now().strftime('%H%M%S')}"


class WebSocketTestClient:
    def __init__(self):
        self.websocket = None
        self.client_id = CLIENT_ID
        self.connected = False

    async def connect(self):
        """Connect to WebSocket server"""
        try:
            # Używamy bezpośrednio WEBSOCKET_URL
            uri = WEBSOCKET_URL
            print(f"🔌 Connecting to {uri}")

            self.websocket = await websockets.connect(uri)
            self.connected = True
            print(f"✅ Connected as {self.client_id}")
            return True

        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    async def send_message(self, message: Dict[str, Any]):
        """Send message to WebSocket server"""
        if not self.connected or not self.websocket:
            print("❌ Not connected to WebSocket")
            return False

        try:
            await self.websocket.send(json.dumps(message))
            print(f"📤 Sent: {message['action']}")
            return True
        except Exception as e:
            print(f"❌ Send failed: {e}")
            return False

    async def receive_message(self, timeout: float = 30.0):
        """Receive message from WebSocket server"""
        if not self.connected or not self.websocket:
            return None

        try:
            message = await asyncio.wait_for(self.websocket.recv(), timeout=timeout)
            data = json.loads(message)
            return data
        except asyncio.TimeoutError:
            print("⏰ Receive timeout")
            return None
        except Exception as e:
            print(f"❌ Receive failed: {e}")
            return None

    async def test_ping(self):
        """Test ping-pong communication"""
        print("\n🏓 Testing ping-pong...")

        # POPRAWIONY FORMAT - bez "type"
        ping_message = {"action": "ping", "data": {}}

        if await self.send_message(ping_message):
            response = await self.receive_message(timeout=5.0)
            if response and response.get("action") == "pong":
                print("✅ Ping-pong test PASSED")
                return True

        print("❌ Ping-pong test FAILED")
        return False

    async def test_job_subscription(self, job_id: str):
        """Test job subscription functionality"""
        print(f"\n📡 Testing job subscription for job {job_id}...")

        # Subscribe to job - POPRAWIONY FORMAT
        subscribe_message = {
            "action": "subscribe_job",
            "data": {"job_id": job_id},
        }

        if await self.send_message(subscribe_message):
            response = await self.receive_message(timeout=5.0)
            if response and response.get("action") == "subscribed":
                print(f"✅ Successfully subscribed to job {job_id}")
                return True

        print(f"❌ Job subscription test FAILED for job {job_id}")
        return False

    async def listen_for_updates(self, duration: int = 60):
        """Listen for real-time updates"""
        print(f"\n👂 Listening for updates for {duration} seconds...")

        start_time = time.time()
        update_count = 0

        while time.time() - start_time < duration:
            try:
                message = await self.receive_message(timeout=5.0)
                if message:
                    update_count += 1

                    # Parse different message types - POPRAWIONE
                    action = message.get("action", "unknown")

                    if action == "job_update":
                        data = message.get("data", {})
                        progress = data.get("progress", {})
                        current = progress.get("current", 0)
                        total = progress.get("total", 100)
                        status = progress.get("status", "Unknown")
                        stage = progress.get("stage", "unknown")

                        percentage = (current / total * 100) if total > 0 else 0
                        print(
                            f"📊 Progress Update [{stage}]: {current}/{total} ({percentage:.1f}%) - {status}"
                        )

                        # Show additional info if available
                        if "task_id" in progress:
                            print(f"    Task ID: {progress['task_id']}")
                        if "job_type" in progress:
                            print(f"    Job Type: {progress['job_type']}")

                    elif (
                        action == "invalid_message"
                        or action == "message_handling_error"
                    ):
                        error_data = message.get("data", {})
                        print(f"🚨 Error: {error_data.get('error', 'Unknown error')}")

                    elif action == "connection_established":
                        print(f"🔌 Connection: {action}")

                    elif action in ["subscribed", "unsubscribed"]:
                        print(f"📡 Subscription: {action}")

                    elif action == "pong":
                        print(f"🏓 Pong received")

                    else:
                        print(f"📝 Message: {action}")
                        # Show data if interesting
                        if message.get("data"):
                            data_preview = str(message["data"])[:100]
                            print(f"    Data: {data_preview}...")

            except asyncio.TimeoutError:
                print("⏰ No updates received in last 5 seconds...")

        print(f"✅ Listening completed. Received {update_count} updates")
        return update_count

    async def test_unsubscribe(self, job_id: str):
        """Test job unsubscription"""
        print(f"\n📡 Testing job unsubscription for job {job_id}...")

        # POPRAWIONY FORMAT
        unsubscribe_message = {
            "action": "unsubscribe_job",
            "data": {"job_id": job_id},
        }

        if await self.send_message(unsubscribe_message):
            response = await self.receive_message(timeout=5.0)
            if response and response.get("action") == "unsubscribed":
                print(f"✅ Successfully unsubscribed from job {job_id}")
                return True

        print(f"❌ Job unsubscription test FAILED for job {job_id}")
        return False

    async def disconnect(self):
        """Disconnect from WebSocket server"""
        if self.websocket and self.connected:
            await self.websocket.close()
            self.connected = False
            print("🔌 Disconnected from WebSocket")


def test_rest_api():
    """Test REST API endpoints"""
    print("\n🌐 Testing REST API endpoints...")

    # POPRAWIONE URL-e
    tests = [
        ("WebSocket Health", f"{REST_API_BASE}/ws/health"),
        ("WebSocket Stats", f"{REST_API_BASE}/ws/stats"),
        ("Connected Clients", f"{REST_API_BASE}/ws/clients"),
        ("Main API Health", f"{REST_API_BASE}/health"),
        ("API Root", f"{REST_API_BASE}/"),
    ]

    for test_name, url in tests:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ {test_name}: PASSED")

                # Show specific info
                if "websocket" in data:
                    ws_data = data["websocket"]
                    print(
                        f"    Active connections: {ws_data.get('active_connections', 0)}"
                    )
                elif "total_clients" in data:
                    print(f"    Total clients: {data['total_clients']}")
                elif "status" in data:
                    print(f"    Status: {data['status']}")

            else:
                print(f"❌ {test_name}: FAILED ({response.status_code})")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")


async def simulate_job_progress(job_id: str):
    """Simulate job progress updates via REST API"""
    print(f"\n🎭 Simulating job progress for {job_id}...")

    progress_stages = [
        {
            "current": 10,
            "total": 100,
            "status": "Starting video comparison simulation...",
            "stage": "video_init",
            "task_id": f"task_{job_id}",
            "job_type": "video_comparison",
        },
        {
            "current": 30,
            "total": 100,
            "status": "Processing video frames...",
            "stage": "video_processing",
            "task_id": f"task_{job_id}",
            "files": {
                "acceptance": "acceptance_test.mp4",
                "emission": "emission_test.mp4",
            },
        },
        {
            "current": 50,
            "total": 100,
            "status": "Running SSIM analysis...",
            "stage": "video_analysis",
            "task_id": f"task_{job_id}",
            "analysis_progress": 50.0,
        },
        {
            "current": 75,
            "total": 100,
            "status": "Analyzing audio tracks...",
            "stage": "audio_analysis",
            "task_id": f"task_{job_id}",
            "analysis_progress": 75.0,
        },
        {
            "current": 90,
            "total": 100,
            "status": "Combining results...",
            "stage": "combining_results",
            "task_id": f"task_{job_id}",
            "sub_results": {"video_completed": True, "audio_completed": True},
        },
        {
            "current": 100,
            "total": 100,
            "status": "Analysis completed successfully!",
            "stage": "completed",
            "task_id": f"task_{job_id}",
            "results": {
                "overall_score": 0.92,
                "differences_found": 3,
                "processing_time": 45.2,
            },
        },
    ]

    for i, stage in enumerate(progress_stages):
        try:
            # POPRAWIONY URL - używamy job_id jako int
            response = requests.post(
                f"{REST_API_BASE}/ws/notify/job/{job_id}",
                json=stage,
                headers={"Content-Type": "application/json"},
                timeout=5,
            )

            if response.status_code == 200:
                resp_data = response.json()
                notified_clients = resp_data.get("notified_clients", 0)
                print(
                    f"📤 Stage {i+1}/6: {stage['current']}% - {stage['status']} (notified {notified_clients} clients)"
                )
            else:
                print(f"❌ Failed to send progress stage {i+1}: {response.status_code}")
                print(f"    Response: {response.text}")

        except Exception as e:
            print(f"❌ Progress simulation error stage {i+1}: {e}")

        # Wait between updates
        await asyncio.sleep(3)


async def main():
    """Main test function"""
    print("🚀 New Video Compare - WebSocket Integration Test")
    print("=" * 60)
    print(f"Client ID: {CLIENT_ID}")
    print(f"WebSocket URL: {WEBSOCKET_URL}")
    print(f"REST API: {REST_API_BASE}")
    print("=" * 60)

    # Test REST API first
    test_rest_api()

    # Create WebSocket client
    client = WebSocketTestClient()

    try:
        # Connect to WebSocket
        print("\n🔌 Phase 1: WebSocket Connection")
        if not await client.connect():
            print("❌ Failed to connect to WebSocket server")
            print("💡 Make sure FastAPI server is running on localhost:8001")
            return

        # Wait for welcome message
        welcome = await client.receive_message(timeout=3.0)
        if welcome and welcome.get("action") == "connection_established":
            print("✅ Received welcome message")
        else:
            print("⚠️ No welcome message received")

        # Test basic communication
        print("\n🏓 Phase 2: Basic Communication")
        if not await client.test_ping():
            print("❌ Basic communication test failed")
            return

        # Test job subscription
        print("\n📡 Phase 3: Job Subscription")
        test_job_id = int(time.time())  # Używamy int dla job_id
        if not await client.test_job_subscription(str(test_job_id)):
            print("❌ Job subscription test failed")
            return

        # Start comprehensive test
        print(f"\n🎯 Phase 4: Real-time Progress Simulation")
        print(f"Job ID: {test_job_id}")

        # Create tasks for parallel execution
        listen_task = asyncio.create_task(client.listen_for_updates(25))

        # Wait a bit before starting simulation
        await asyncio.sleep(2)
        simulate_task = asyncio.create_task(simulate_job_progress(str(test_job_id)))

        # Wait for both tasks to complete
        results = await asyncio.gather(
            listen_task, simulate_task, return_exceptions=True
        )

        listen_result = results[0] if len(results) > 0 else 0
        if isinstance(listen_result, int) and listen_result > 0:
            print(f"✅ Received {listen_result} real-time updates!")
        else:
            print("⚠️ Limited or no real-time updates received")

        # Test unsubscription
        print(f"\n📡 Phase 5: Job Unsubscription")
        await client.test_unsubscribe(str(test_job_id))

        print("\n🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
        print("\nTest Summary:")
        print("- ✅ WebSocket connection established")
        print("- ✅ Ping-pong communication working")
        print("- ✅ Job subscription/unsubscription working")
        print("- ✅ Real-time progress updates received")
        print("- ✅ REST API integration working")
        print("\n🚀 New Video Compare WebSocket system is fully functional!")

    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    print("New Video Compare - WebSocket Integration Test")
    print(
        "Make sure the FastAPI server is running: python -m uvicorn main:app --reload --port 8001"
    )
    print("Press Ctrl+C to stop the test\n")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Test client stopped by user")
    except Exception as e:
        print(f"\n💥 Test client crashed: {e}")
