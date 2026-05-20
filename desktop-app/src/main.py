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

def load_env():
    """Manual .env loader looking in app root and project root"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    paths = [
        os.path.join(current_dir, '../.env'),        # desktop-app/.env
        os.path.join(current_dir, '../../.env'),      # project-root/.env
    ]
    for env_path in paths:
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            parts = line.split('=', 1)
                            if len(parts) == 2:
                                key, val = parts
                                key = key.strip()
                                val = val.strip().strip('"').strip("'")
                                os.environ[key] = val
                print(f"Loaded environment from: {os.path.abspath(env_path)}")
            except Exception as e:
                print(f"Failed to read env file {env_path}: {e}")

async def main():
    """Main application entry point"""
    # Load .env file at startup
    load_env()
    
    # Get WebSocket port from environment (default: 8765)
    ws_port_str = os.environ.get("DESKTOP_WS_PORT", "8765")
    try:
        ws_port = int(ws_port_str)
    except ValueError:
        logger.warning(f"⚠️ Invalid DESKTOP_WS_PORT: {ws_port_str}. Using default 8765.")
        ws_port = 8765

    while True:
        try:
            logger.info(f"Starting Cradle-Video-Automation Desktop App on port {ws_port}")
            
            # Start WebSocket server
            await server.start_server(port=ws_port)
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