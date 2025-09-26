"""
WebSocket Handlers for New Video Compare
Real-time communication for progress updates and system notifications
"""

import json
import logging
from typing import Dict, Any, Set, Optional
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from models.schemas import DesktopAppMessage
from models.models import ComparisonJob, JobStatus
from models.database import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and message broadcasting"""

    def __init__(self):
        # Active connections by client_id
        self.active_connections: Dict[str, WebSocket] = {}
        # Job subscriptions - which clients are interested in which jobs
        self.job_subscriptions: Dict[int, Set[str]] = {}
        # Client metadata
        self.client_metadata: Dict[str, Dict[str, Any]] = {}

    async def connect(
        self, websocket: WebSocket, client_id: str, client_type: str = "web"
    ):
        """Accept new WebSocket connection"""
        try:
            await websocket.accept()
            self.active_connections[client_id] = websocket
            self.client_metadata[client_id] = {
                "client_type": client_type,
                "connected_at": datetime.now(),
                "last_activity": datetime.now(),
            }

            logger.info(f"WebSocket client connected: {client_id} ({client_type})")

            # Send welcome message
            welcome_message = DesktopAppMessage(
                action="connection_established",
                data={
                    "client_id": client_id,
                    "server_time": datetime.now().isoformat(),
                    "available_actions": [
                        "subscribe_job",
                        "unsubscribe_job",
                        "get_job_status",
                        "ping",
                    ],
                },
                timestamp=datetime.now(),
            )
            await self.send_message(client_id, welcome_message)

        except Exception as e:
            logger.error(f"Error connecting WebSocket client {client_id}: {str(e)}")
            raise

    async def disconnect(self, client_id: str):
        """Remove client connection and clean up subscriptions"""
        try:
            # Remove from active connections
            if client_id in self.active_connections:
                del self.active_connections[client_id]

            # Clean up job subscriptions
            for job_id, subscribers in self.job_subscriptions.items():
                subscribers.discard(client_id)

            # Remove empty subscription sets
            self.job_subscriptions = {
                job_id: subs
                for job_id, subs in self.job_subscriptions.items()
                if len(subs) > 0
            }

            # Remove client metadata
            if client_id in self.client_metadata:
                del self.client_metadata[client_id]

            logger.info(f"WebSocket client disconnected: {client_id}")

        except Exception as e:
            logger.error(f"Error disconnecting WebSocket client {client_id}: {str(e)}")

    async def send_message(self, client_id: str, message: DesktopAppMessage):
        """Send message to specific client"""
        try:
            if client_id not in self.active_connections:
                logger.warning(
                    f"Attempted to send message to disconnected client: {client_id}"
                )
                return False

            websocket = self.active_connections[client_id]
            message_dict = message.model_dump()

            # Ensure timestamp is set
            if message_dict.get("timestamp") is None:
                message_dict["timestamp"] = datetime.now().isoformat()

            await websocket.send_text(json.dumps(message_dict, default=str))

            # Update last activity
            if client_id in self.client_metadata:
                self.client_metadata[client_id]["last_activity"] = datetime.now()

            return True

        except WebSocketDisconnect:
            logger.info(f"Client {client_id} disconnected during message send")
            await self.disconnect(client_id)
            return False
        except Exception as e:
            logger.error(f"Error sending message to {client_id}: {str(e)}")
            return False

    async def broadcast_to_job_subscribers(
        self, job_id: int, message: DesktopAppMessage
    ):
        """Broadcast message to all clients subscribed to specific job"""
        try:
            if job_id not in self.job_subscriptions:
                logger.debug(f"No subscribers for job {job_id}")
                return 0

            subscribers = self.job_subscriptions[job_id].copy()
            successful_sends = 0

            for client_id in subscribers:
                success = await self.send_message(client_id, message)
                if success:
                    successful_sends += 1
                else:
                    # Remove failed client from subscription
                    self.job_subscriptions[job_id].discard(client_id)

            logger.debug(
                f"Broadcasted to {successful_sends}/{len(subscribers)} subscribers for job {job_id}"
            )
            return successful_sends

        except Exception as e:
            logger.error(f"Error broadcasting to job {job_id} subscribers: {str(e)}")
            return 0

    async def subscribe_to_job(self, client_id: str, job_id: int):
        """Subscribe client to job progress updates"""
        try:
            if client_id not in self.active_connections:
                return False

            if job_id not in self.job_subscriptions:
                self.job_subscriptions[job_id] = set()

            self.job_subscriptions[job_id].add(client_id)

            logger.info(f"Client {client_id} subscribed to job {job_id}")

            # Send current job status
            db = next(get_db())
            job = db.query(ComparisonJob).filter(ComparisonJob.id == job_id).first()

            if job:
                status_message = DesktopAppMessage(
                    action="job_status_update",
                    data={
                        "job_id": job_id,
                        "status": job.status.value if job.status else "unknown",
                        "progress": self._calculate_job_progress(job),
                        "created_at": (
                            job.created_at.isoformat() if job.created_at else None
                        ),
                        "updated_at": (
                            job.updated_at.isoformat() if job.updated_at else None
                        ),
                    },
                    timestamp=datetime.now(),
                )
                await self.send_message(client_id, status_message)

            return True

        except Exception as e:
            logger.error(
                f"Error subscribing client {client_id} to job {job_id}: {str(e)}"
            )
            return False

    async def unsubscribe_from_job(self, client_id: str, job_id: int):
        """Unsubscribe client from job updates"""
        try:
            if job_id in self.job_subscriptions:
                self.job_subscriptions[job_id].discard(client_id)

                # Remove empty subscription set
                if len(self.job_subscriptions[job_id]) == 0:
                    del self.job_subscriptions[job_id]

            logger.info(f"Client {client_id} unsubscribed from job {job_id}")
            return True

        except Exception as e:
            logger.error(
                f"Error unsubscribing client {client_id} from job {job_id}: {str(e)}"
            )
            return False

    def _calculate_job_progress(self, job: ComparisonJob) -> Dict[str, Any]:
        """Calculate job progress percentage and details"""
        progress = {
            "overall_percent": 0,
            "video_completed": job.video_completed or False,
            "audio_completed": job.audio_completed or False,
            "stage": "unknown",
        }

        if job.status == JobStatus.PENDING:
            progress["overall_percent"] = 0
            progress["stage"] = "pending"
        elif job.status == JobStatus.PROCESSING:
            if job.video_completed and job.audio_completed:
                progress["overall_percent"] = 90
                progress["stage"] = "finalizing"
            elif job.video_completed or job.audio_completed:
                progress["overall_percent"] = 50
                progress["stage"] = "processing"
            else:
                progress["overall_percent"] = 25
                progress["stage"] = "processing"
        elif job.status == JobStatus.COMPLETED:
            progress["overall_percent"] = 100
            progress["stage"] = "completed"
        elif job.status == JobStatus.FAILED:
            progress["overall_percent"] = 0
            progress["stage"] = "failed"

        return progress

    async def handle_message(self, client_id: str, message_data: dict):
        """Handle incoming WebSocket messages from clients"""
        try:
            # Parse message using schema
            message = DesktopAppMessage(**message_data)

            response_data = {"action": message.action, "success": False}

            if message.action == "ping":
                response_data = {
                    "action": "pong",
                    "success": True,
                    "server_time": datetime.now().isoformat(),
                }

            elif message.action == "subscribe_job":
                job_id = message.data.get("job_id")
                if job_id:
                    success = await self.subscribe_to_job(client_id, int(job_id))
                    response_data["success"] = success
                    response_data["data"] = {"job_id": job_id, "subscribed": success}

            elif message.action == "unsubscribe_job":
                job_id = message.data.get("job_id")
                if job_id:
                    success = await self.unsubscribe_from_job(client_id, int(job_id))
                    response_data["success"] = success
                    response_data["data"] = {"job_id": job_id, "unsubscribed": success}

            elif message.action == "get_job_status":
                job_id = message.data.get("job_id")
                if job_id:
                    db = next(get_db())
                    job = (
                        db.query(ComparisonJob)
                        .filter(ComparisonJob.id == int(job_id))
                        .first()
                    )
                    if job:
                        response_data["success"] = True
                        response_data["data"] = {
                            "job_id": job_id,
                            "status": job.status.value if job.status else "unknown",
                            "progress": self._calculate_job_progress(job),
                        }

            # Send response
            response_message = DesktopAppMessage(
                action=f"{message.action}_response",
                data=response_data,
                timestamp=datetime.now(),
            )
            await self.send_message(client_id, response_message)

        except Exception as e:
            logger.error(f"Error handling message from {client_id}: {str(e)}")

            # Send error response
            error_message = DesktopAppMessage(
                action="error",
                data={
                    "message": str(e),
                    "original_action": message_data.get("action", "unknown"),
                },
                timestamp=datetime.now(),
            )
            await self.send_message(client_id, error_message)


# Global connection manager instance
connection_manager = ConnectionManager()
