import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestClient")

async def test_api_request():
    uri = "ws://localhost:8765"
    cradle_id = "957577"  # Example ID,ensure this folder exists in Downloads with 2 video files for real test
    
    try:
        async with websockets.connect(uri) as websocket:
            logger.info(f"Connected to {uri}")
            
            # 1. Send connection message
            await websocket.send(json.dumps({"action": "extension_connected"}))
            response = await websocket.recv()
            logger.info(f"Received: {response}")
            
            # 2. Send VIDEO_COMPARE_API_REQUEST
            request = {
                "action": "VIDEO_COMPARE_API_REQUEST",
                "cradleId": cradle_id,
                "timestamp": 1234567890
            }
            logger.info(f"Sending request: {request}")
            await websocket.send(json.dumps(request))
            
            # 3. Wait for responses
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                logger.info(f"Received: {data}")
                
                if data.get("action") == "VIDEO_COMPARE_RESULTS":
                    logger.info("✅ Test Passed: Results received")
                    break
                
                if data.get("action") == "ERROR":
                    logger.error(f"❌ Test Failed: {data.get('error')}")
                    break
                    
    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_api_request())
