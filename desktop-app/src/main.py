import asyncio
import logging
from websocket_server import server

# Setup logging
import os

# Setup logging
current_dir = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.join(current_dir, '../logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'app.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, mode='a')
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Main application entry point"""
    while True:
        try:
            logger.info("Starting Cardle-Video-Automation Desktop App")
            
            # Start WebSocket server
            await server.start_server()
            break # If server stops gracefully
            
        except KeyboardInterrupt:
            logger.info("Application shutting down...")
            break
        except Exception as e:
            logger.error(f"❌ CRITICAL Application error: {str(e)}")
            logger.info("🔄 Restarting server in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Desktop App stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")