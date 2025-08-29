import asyncio
import websockets
import json
import logging
from file_handler import FileHandler

class WebSocketServer:
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.clients = set()
        self.logger = logging.getLogger(__name__)
        
        # Initialize file handler
        self.file_handler = FileHandler()

    async def register_client(self, websocket):
        self.clients.add(websocket)
        self.logger.info(f"Client connected. Total clients: {len(self.clients)}")

    async def unregister_client(self, websocket):
        self.clients.discard(websocket)
        self.logger.info(f"Client disconnected. Total clients: {len(self.clients)}")

    async def handle_message(self, websocket, message):
        try:
            data = json.loads(message)
            action = data.get('action', 'unknown')
            self.logger.info(f"Received: {data}")
            
            # Route messages based on action
            if action == 'extension_connected':
                await self.handle_extension_connected(websocket, data)
            elif action == 'FILES_DETECTED':
                await self.handle_files_detected(websocket, data)
            elif action == 'CONSOLE_TEST':
                await self.handle_console_test(websocket, data)
            else:
                await self.handle_unknown_action(websocket, data)
                
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON: {str(e)}"
            self.logger.error(error_msg)
            await websocket.send(json.dumps({"status": "error", "message": error_msg}))
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(error_msg)
            await websocket.send(json.dumps({"status": "error", "message": error_msg}))

    async def handle_extension_connected(self, websocket, data):
        """Handle extension connection"""
        response = {
            "status": "success",
            "message": "Desktop app ready for file processing",
            "timestamp": data.get('timestamp')
        }
        await websocket.send(json.dumps(response))

    async def handle_files_detected(self, websocket, data):
        """Handle FILES_DETECTED - delegate to file handler"""
        self.logger.info("🎯 FILES_DETECTED received - starting download process...")
        
        try:
            await self.file_handler.handle_files_detected(websocket, data)
        except Exception as e:
            self.logger.error(f"❌ Error in file handler: {str(e)}")
            await websocket.send(json.dumps({
                "action": "DOWNLOAD_ERROR",
                "error": f"File handler error: {str(e)}"
            }))

    async def handle_console_test(self, websocket, data):
        """Handle console test messages"""
        response = {
            "status": "success",
            "message": f"Desktop app received: {data.get('action', 'unknown')}",
            "test_data": data
        }
        await websocket.send(json.dumps(response))

    async def handle_unknown_action(self, websocket, data):
        """Handle unknown actions"""
        response = {
            "status": "warning",
            "message": f"Unknown action: {data.get('action', 'none')}",
            "received_data": data
        }
        await websocket.send(json.dumps(response))

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