import asyncio
import websockets
import json
import logging
from file_handler import FileHandler
from video_compare_automator import VideoCompareAutomator
import time
from pathlib import Path

logger = logging.getLogger(__name__)

class WebSocketServer:
    def __init__(self):
        self.clients = set()
        self.file_handler = FileHandler()
        self.video_compare = VideoCompareAutomator()
        
    async def register(self, websocket):
        """Register a new client"""
        self.clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")
        
    async def unregister(self, websocket):
        """Unregister a client"""
        self.clients.discard(websocket)
        logger.info(f"Client disconnected. Total clients: {len(self.clients)}")
        
    async def handle_client(self, websocket, path):
        """Handle individual client connection"""
        await self.register(websocket)
        try:
            async for message in websocket:
                await self.handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Error handling client: {str(e)}")
        finally:
            await self.unregister(websocket)
            
    async def handle_message(self, websocket, message):
        """Handle incoming messages from clients"""
        try:
            logger.info(f"Received: {message}")
            data = json.loads(message)
            action = data.get('action')
            
            if action == 'extension_connected':
                logger.info("Extension connected")
                
            elif action == 'FILES_DETECTED':
                logger.info("🎯 FILES_DETECTED received - starting download process...")
                await self.file_handler.handle_files_detected(websocket, data)
                
            elif action == 'VIDEO_COMPARE_REQUEST':
                logger.info("🎬 VIDEO_COMPARE_REQUEST received - starting Video Compare...")
                await self.handle_video_compare_request(websocket, data)
                
            else:
                logger.warning(f"Unknown action: {action}")
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {message}")
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")

    async def handle_video_compare_request(self, websocket, data):
        """Handle Video Compare automation request"""
        try:
            cradle_id = data.get('cradleId')
            
            if not cradle_id:
                await self.send_error(websocket, "No CradleID provided for Video Compare")
                return
            
            # Build file paths
            base_path = Path.home() / "Downloads" / cradle_id
            
            # Find acceptance and emission files
            acceptance_file = None
            emission_file = None
            
            if base_path.exists():
                files = list(base_path.glob("*"))
                logger.info(f"📁 Files in {cradle_id} folder: {[f.name for f in files]}")
                
                for file_path in files:
                    file_name = file_path.name.lower()
                    if 'acceptance' in file_name or file_name.endswith('byhd.mp4') or file_name.endswith('byhdmod.mp4'):
                        acceptance_file = str(file_path)
                    elif 'emission' in file_name or file_name.endswith('.mov') or '_video-' in file_name.lower():
                        emission_file = str(file_path)
            
            if not acceptance_file or not emission_file:
                await self.send_error(websocket, f"Missing files in {cradle_id} folder. Found: {[f.name for f in files] if 'files' in locals() else 'No files'}")
                return
            
            logger.info(f"🎬 Starting Video Compare automation for {cradle_id}")
            logger.info(f"   Acceptance: {acceptance_file}")
            logger.info(f"   Emission: {emission_file}")
            
            # Send status update
            await self.send_status_update(websocket, "VIDEO_COMPARE_STARTED", {
                'cradle_id': cradle_id,
                'status': 'Starting Video Compare automation...'
            })
            
            # Run Video Compare automation
            result = await self.video_compare.upload_and_compare(
                cradle_id, acceptance_file, emission_file
            )
            
            # Send results
            await self.send_video_compare_results(websocket, result)
            
        except Exception as e:
            logger.error(f"❌ Video Compare request failed: {str(e)}")
            await self.send_error(websocket, f"Video Compare error: {str(e)}")

    async def send_video_compare_results(self, websocket, result):
        """Send Video Compare results to extension"""
        message = {
            'action': 'VIDEO_COMPARE_RESULTS',
            'data': result,
            'timestamp': int(time.time() * 1000)
        }
        await websocket.send(json.dumps(message))
        logger.info(f"📤 Sent Video Compare results: {result.get('success', False)}")

    async def send_status_update(self, websocket, action, data):
        """Send status update to extension"""
        message = {
            'action': action,
            'data': data,
            'timestamp': int(time.time() * 1000)
        }
        await websocket.send(json.dumps(message))

    async def send_error(self, websocket, error_message):
        """Send error message to extension"""
        message = {
            'action': 'ERROR',
            'error': error_message,
            'timestamp': int(time.time() * 1000)
        }
        await websocket.send(json.dumps(message))
        logger.error(f"📤 Sent error: {error_message}")
            
    async def start_server(self, host="localhost", port=8765):
        """Start the WebSocket server"""
        logger.info(f"Starting WebSocket server on {host}:{port}")
        
        async def handler(websocket, path):
            await self.handle_client(websocket, path)
            
        start_server = websockets.serve(handler, host, port)
        logger.info("WebSocket server is running...")
        
        await start_server
        
        # Keep server running
        await asyncio.Future()  # Run forever

# Server instance
server = WebSocketServer()

async def main():
    """Main server function"""
    try:
        await server.start_server()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as e:
        logger.error(f"Server error: {str(e)}")

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run server
    asyncio.run(main())