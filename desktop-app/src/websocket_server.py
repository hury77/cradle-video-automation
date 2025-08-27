import asyncio
import websockets
import json
import logging

class WebSocketServer:
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.clients = set()
        self.logger = logging.getLogger(__name__)

    async def register_client(self, websocket):
        self.clients.add(websocket)
        self.logger.info(f"Client connected. Total clients: {len(self.clients)}")

    async def unregister_client(self, websocket):
        self.clients.discard(websocket)
        self.logger.info(f"Client disconnected. Total clients: {len(self.clients)}")

    async def handle_message(self, websocket, message):
        try:
            data = json.loads(message)
            self.logger.info(f"Received: {data}")
            
            # Echo back for testing
            response = {
                "status": "success",
                "message": f"Desktop app received: {data.get('action', 'unknown')}"
            }
            await websocket.send(json.dumps(response))
            
        except json.JSONDecodeError:
            await websocket.send(json.dumps({"status": "error", "message": "Invalid JSON"}))

    async def handle_client(self, websocket):
        await self.register_client(websocket)
        try:
            async for message in websocket:
                await self.handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister_client(websocket)

    async def start(self):
        self.logger.info(f"Starting WebSocket server on {self.host}:{self.port}")
        async with websockets.serve(self.handle_client, self.host, self.port):
            self.logger.info("WebSocket server is running...")
            await asyncio.Future()  # Run forever