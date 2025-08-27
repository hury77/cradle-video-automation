import asyncio
import logging
import os
from websocket_server import WebSocketServer

def setup_logging():
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(logs_dir, 'desktop-app.log')),
            logging.StreamHandler()
        ]
    )

async def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting Cardle-Video-Automation Desktop App")
    
    # Start WebSocket server
    server = WebSocketServer()
    await server.start()

if __name__ == "__main__":
    asyncio.run(main())