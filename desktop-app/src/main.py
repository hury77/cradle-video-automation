import asyncio
import logging
from websocket_server import server

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('../logs/app.log', mode='a')
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Main application entry point"""
    try:
        logger.info("Starting Cardle-Video-Automation Desktop App")
        
        # Start WebSocket server
        await server.start_server()
        
    except KeyboardInterrupt:
        logger.info("Application shutting down...")
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Desktop App stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")