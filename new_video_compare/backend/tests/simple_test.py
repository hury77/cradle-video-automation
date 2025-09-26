# simple_test.py
import asyncio
import websockets
import json


async def simple_test():
    uri = "ws://127.0.0.1:8001/ws/connect"

    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")

            # Odbierz welcome message
            welcome = await websocket.recv()
            print(f"📨 Welcome: {welcome}")

            # Wyślij ping
            ping_msg = {"action": "ping", "data": {}}
            await websocket.send(json.dumps(ping_msg))
            print("📤 Sent ping")

            # Odbierz pong
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            print(f"📨 Response: {response}")

    except Exception as e:
        print(f"❌ Error: {e}")


asyncio.run(simple_test())
