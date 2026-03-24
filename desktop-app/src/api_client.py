import aiohttp
import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)

class APIClient:
    """
    Client for communicating with the New Video Compare backend API.
    Handles file uploads and job creation.
    """
    
    def __init__(self, base_url="http://localhost:8001/api/v1"):
        self.base_url = base_url.rstrip("/")
        self.session = None

    async def _get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=7200)  # 2 hours total timeout
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def upload_file(self, file_path: str, file_type: str = None, cradle_id: str = None):
        """
        Upload a file to the backend
        
        Args:
            file_path: Path to the file to upload
            file_type: 'acceptance' or 'emission' (optional)
            cradle_id: Cradle ID associated with the file (optional)
            
        Returns:
            Dict containing upload response (success, file_id, filename, etc.)
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.error(f"File not found: {file_path}")
                return {"success": False, "error": f"File not found: {file_path}"}
            
            url = f"{self.base_url}/files/upload/stream"
            session = await self._get_session()
            
            params = {"filename": path.name}
            if file_type:
                params["file_type"] = file_type
            if cradle_id:
                params["cradle_id"] = cradle_id
            
            logger.info(f"📤 Stream uploading file: {path.name} to {url}")
            
            # Async file reading generator to avoid blocking the client event loop
            async def file_sender(file_path):
                import asyncio
                loop = asyncio.get_running_loop()
                with open(file_path, 'rb') as f:
                    while True:
                        chunk = await loop.run_in_executor(None, f.read, 1024 * 1024) # 1MB chunks
                        if not chunk:
                            break
                        yield chunk

            async with session.post(url, params=params, data=file_sender(path)) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    logger.info(f"✅ Upload successful: {result.get('filename')} (ID: {result.get('file_id')})")
                    return result
                else:
                    text = await response.text()
                    logger.error(f"❌ Upload failed (HTTP {response.status}): {text}")
                    return {"success": False, "error": f"HTTP {response.status}: {text}"}
                    
        except Exception as e:
            logger.error(f"❌ Upload exception: {str(e)}")
            return {"success": False, "error": str(e)}

    async def create_comparison_job(self, acceptance_id: int, emission_id: int, 
                                    cradle_id: str = None, 
                                    job_name: str = None,
                                    client_name: str = None,
                                    comparison_type: str = "automation"):
        """
        Create a new comparison job
        
        Args:
            acceptance_id: ID of the uploaded acceptance file
            emission_id: ID of the uploaded emission file
            cradle_id: Cradle ID (optional)
            job_name: Name for the job (optional)
            comparison_type: 'full', 'video_only', 'audio_only', or 'automation'
            
        Returns:
            Dict containing job creation response
        """
        try:
            url = f"{self.base_url}/compare/"
            session = await self._get_session()
            
            payload = {
                "acceptance_file_id": acceptance_id,
                "emission_file_id": emission_id,
                "comparison_type": comparison_type,
                "sensitivity_level": "automation" if comparison_type == "automation" else "high",
                "processing_config": {}
            }
            
            if cradle_id:
                payload["cradle_id"] = cradle_id
            if job_name:
                payload["job_name"] = job_name
            if client_name:
                payload["client_name"] = client_name
            
            logger.info(f"🚀 Creating job: {payload}")
            
            async with session.post(url, json=payload) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    logger.info(f"✅ Job created: ID {result.get('id')}")
                    return result
                else:
                    text = await response.text()
                    logger.error(f"❌ Job creation failed (HTTP {response.status}): {text}")
                    return {"success": False, "error": f"HTTP {response.status}: {text}"}
                    
        except Exception as e:
            logger.error(f"❌ Job creation exception: {str(e)}")
            return {"success": False, "error": str(e)}

    async def get_job_status(self, job_id: int):
        """Get status of a specific job"""
        try:
            url = f"{self.base_url}/compare/{job_id}"
            session = await self._get_session()
            
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"success": False, "error": f"HTTP {response.status}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def log_system_event(self, component: str, action: str, message: str, is_error: bool = True, cradle_id: str = None, details: dict = None):
        """Send a log to the backend dashboard"""
        try:
            url = f"{self.base_url}/dashboard/logs"
            session = await self._get_session()
            
            payload = {
                "component": component,
                "action": action,
                "message": message,
                "is_error": is_error
            }
            if cradle_id: payload["cradle_id"] = cradle_id
            if details: payload["details"] = details
            
            async with session.post(url, json=payload) as response:
                if response.status not in [200, 201]:
                    logger.warning(f"Failed to send log to dashboard: {await response.text()}")
        except Exception as e:
            logger.warning(f"Exception sending log to dashboard: {str(e)}")
