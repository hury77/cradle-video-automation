from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    HTTPException,
    Body,
)
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional, Any
import json
import logging
from datetime import datetime
import asyncio

# Poprawione importy
from ws_handlers.handlers import connection_manager
from ws_handlers.progress_tracker import ProgressTracker, update_job_progress
from models.schemas import DesktopAppMessage
from models.database import get_db
from sqlalchemy.orm import Session

# Configure logging
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

# Use existing connection manager instance and create progress tracker
progress_tracker = ProgressTracker()


@router.websocket("/connect")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication with clients."""
    client_id = None
    try:
        # Connect and get client_id - używamy timestamp jako client_id
        client_id = f"client_{datetime.now().timestamp()}"
        await connection_manager.connect(websocket, client_id)
        logger.info(f"Client {client_id} connected")

        # USUNIĘTE DUPLIKOWANE WELCOME MESSAGE - handlers.py już wysyła

        while True:
            try:
                # Listen for incoming messages
                data = await websocket.receive_text()
                print(f"🔍 RAW MESSAGE: {data}")  # DEBUG

                message_data = json.loads(data)
                print(f"🔍 PARSED JSON: {message_data}")  # DEBUG

                logger.info(
                    f"🔍 DEBUG: Received message from {client_id}: {message_data}"
                )

                # Validate message format
                try:
                    message = DesktopAppMessage(**message_data)
                    print(
                        f"🔍 WEBSOCKET DEBUG: Successfully parsed message: {message.action}"
                    )  # DEBUG
                except Exception as e:
                    logger.error(f"Invalid message format from {client_id}: {e}")
                    print(f"🔍 VALIDATION ERROR: {e}")  # DEBUG
                    error_response = DesktopAppMessage(
                        action="invalid_message",
                        data={"error": f"Invalid message format: {str(e)}"},
                    )
                    await connection_manager.send_message(client_id, error_response)
                    continue

                # Handle different message types
                print(
                    f"🔍 WEBSOCKET DEBUG: About to handle message: {message.action}"
                )  # DEBUG
                await handle_websocket_message(message, client_id)

            except WebSocketDisconnect:
                logger.info(f"Client {client_id} disconnected")
                break
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error from {client_id}: {e}")
                print(f"🔍 JSON ERROR: {e}")  # DEBUG
                error_response = DesktopAppMessage(
                    action="json_error",
                    data={"error": "Invalid JSON format"},
                )
                await connection_manager.send_message(client_id, error_response)
            except Exception as e:
                logger.error(f"Error handling WebSocket message from {client_id}: {e}")
                print(f"🔍 GENERAL ERROR: {e}")  # DEBUG
                error_response = DesktopAppMessage(
                    action="processing_error", data={"error": str(e)}
                )
                await connection_manager.send_message(client_id, error_response)

    except Exception as e:
        logger.error(f"WebSocket connection error for {client_id}: {e}")
        print(f"🔍 CONNECTION ERROR: {e}")  # DEBUG
    finally:
        if client_id:
            await connection_manager.disconnect(client_id)


async def handle_websocket_message(message: DesktopAppMessage, client_id: str):
    """Handle incoming WebSocket messages based on action."""
    print(f"🔍 HANDLER: Starting to handle {message.action} from {client_id}")  # DEBUG
    logger.info(f"🔍 Handling message from {client_id}: action={message.action}")

    try:
        if message.action == "subscribe_job":
            print(f"🔍 HANDLER: Processing subscribe_job")  # DEBUG
            job_id = message.data.get("job_id")
            if job_id:
                await connection_manager.subscribe_to_job(client_id, int(job_id))
                response = DesktopAppMessage(
                    action="subscribed",
                    data={"job_id": job_id, "client_id": client_id},
                )
                await connection_manager.send_message(client_id, response)
                logger.info(f"Client {client_id} subscribed to job {job_id}")

        elif message.action == "unsubscribe_job":
            print(f"🔍 HANDLER: Processing unsubscribe_job")  # DEBUG
            job_id = message.data.get("job_id")
            if job_id:
                await connection_manager.unsubscribe_from_job(client_id, int(job_id))
                response = DesktopAppMessage(
                    action="unsubscribed",
                    data={"job_id": job_id, "client_id": client_id},
                )
                await connection_manager.send_message(client_id, response)
                logger.info(f"Client {client_id} unsubscribed from job {job_id}")

        elif message.action == "get_job_progress":
            print(f"🔍 HANDLER: Processing get_job_progress")  # DEBUG
            job_id = message.data.get("job_id")
            if job_id:
                progress_info = await progress_tracker.get_job_progress(int(job_id))
                response = DesktopAppMessage(
                    action="job_progress",
                    data={"job_id": job_id, "progress": progress_info},
                )
                await connection_manager.send_message(client_id, response)
                logger.info(f"Sent job progress for job {job_id} to {client_id}")

        elif message.action == "ping":
            print(f"🔍 HANDLER: Processing PING!")  # DEBUG
            logger.info(f"🏓 Received ping from {client_id}")
            response = DesktopAppMessage(
                action="pong",
                data={"timestamp": datetime.now().isoformat()},
            )
            print(f"🔍 HANDLER: About to send pong response")  # DEBUG
            await connection_manager.send_message(client_id, response)
            print(f"🔍 HANDLER: Pong sent successfully!")  # DEBUG
            logger.info(f"🏓 Sent pong to {client_id}")

        else:
            print(f"🔍 HANDLER: Unknown action: {message.action}")  # DEBUG
            logger.warning(f"Unknown action from {client_id}: {message.action}")
            response = DesktopAppMessage(
                action="unknown_action",
                data={
                    "received_action": message.action,
                    "error": "Action not supported",
                },
            )
            await connection_manager.send_message(client_id, response)

    except Exception as e:
        print(f"🔍 HANDLER ERROR: {e}")  # DEBUG
        logger.error(f"Error handling message from {client_id}: {e}")
        error_response = DesktopAppMessage(
            action="message_handling_error", data={"error": str(e)}
        )
        await connection_manager.send_message(client_id, error_response)


@router.post("/broadcast")
async def broadcast_message(message: DesktopAppMessage = Body(...)):
    """REST endpoint to broadcast a message to all connected clients."""
    try:
        # Broadcast to all connected clients
        broadcast_count = 0
        for client_id in connection_manager.active_connections.keys():
            try:
                await connection_manager.send_message(client_id, message)
                broadcast_count += 1
            except Exception as e:
                logger.error(f"Failed to send message to {client_id}: {e}")

        logger.info(f"Broadcasted message to {broadcast_count} clients")
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Message broadcasted to all clients",
                "recipients": broadcast_count,
            },
        )
    except Exception as e:
        logger.error(f"Error broadcasting message: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to broadcast message: {str(e)}"
        )


@router.post("/send/{client_id}")
async def send_personal_message(client_id: str, message: DesktopAppMessage = Body(...)):
    """REST endpoint to send a message to a specific client."""
    try:
        if client_id not in connection_manager.active_connections:
            raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

        await connection_manager.send_message(client_id, message)
        logger.info(f"Sent personal message to {client_id}")
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": f"Message sent to client {client_id}",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending message to {client_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")


@router.get("/clients")
async def get_connected_clients():
    """Get list of currently connected clients."""
    try:
        clients_info = []
        for client_id in connection_manager.active_connections.keys():
            metadata = connection_manager.client_metadata.get(client_id, {})

            # Find subscriptions for this client
            client_subscriptions = []
            for job_id, subscribers in connection_manager.job_subscriptions.items():
                if client_id in subscribers:
                    client_subscriptions.append(job_id)

            clients_info.append(
                {
                    "client_id": client_id,
                    "connected_at": metadata.get("connected_at"),
                    "client_type": metadata.get("client_type", "unknown"),
                    "subscriptions": client_subscriptions,
                }
            )

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "total_clients": len(clients_info),
                "clients": clients_info,
            },
        )
    except Exception as e:
        logger.error(f"Error getting connected clients: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get clients: {str(e)}")


@router.post("/subscribe/{client_id}/{job_id}")
async def subscribe_client_to_job(client_id: str, job_id: int):
    """REST endpoint to subscribe a client to job progress updates."""
    try:
        if client_id not in connection_manager.active_connections:
            raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

        await connection_manager.subscribe_to_job(client_id, job_id)
        logger.info(f"Client {client_id} subscribed to job {job_id} via REST")
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": f"Client {client_id} subscribed to job {job_id}",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error subscribing {client_id} to job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to subscribe: {str(e)}")


@router.delete("/subscribe/{client_id}/{job_id}")
async def unsubscribe_client_from_job(client_id: str, job_id: int):
    """REST endpoint to unsubscribe a client from job progress updates."""
    try:
        if client_id not in connection_manager.active_connections:
            raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

        await connection_manager.unsubscribe_from_job(client_id, job_id)
        logger.info(f"Client {client_id} unsubscribed from job {job_id} via REST")
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": f"Client {client_id} unsubscribed from job {job_id}",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unsubscribing {client_id} from job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to unsubscribe: {str(e)}")


@router.get("/job/{job_id}/progress")
async def get_job_progress(job_id: int):
    """REST endpoint to get current progress of a specific job."""
    try:
        progress_info = await progress_tracker.get_job_progress(job_id)
        if progress_info is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        return JSONResponse(
            status_code=200,
            content={"status": "success", "job_id": job_id, "progress": progress_info},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting progress for job {job_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get job progress: {str(e)}"
        )


@router.get("/stats")
async def get_system_stats():
    """Get system statistics including WebSocket connections and active jobs."""
    try:
        active_connections = len(connection_manager.active_connections)
        total_subscriptions = sum(
            len(subscribers)
            for subscribers in connection_manager.job_subscriptions.values()
        )

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "websocket": {
                    "active_connections": active_connections,
                    "total_subscriptions": total_subscriptions,
                    "clients": list(connection_manager.active_connections.keys()),
                },
                "jobs": {"active_jobs": len(progress_tracker.job_progress)},
            },
        )
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get system stats: {str(e)}"
        )


@router.post("/notify/job/{job_id}")
async def notify_job_progress(job_id: int, progress_data: Dict[str, Any] = Body(...)):
    """
    REST endpoint for Celery tasks to notify progress updates.
    This endpoint is called by Celery tasks to push progress updates to WebSocket clients.
    """
    try:
        # Extract data for update_job_progress
        current = progress_data.get("current", 0)
        total = progress_data.get("total", 100)
        percent = (current / total * 100) if total > 0 else 0.0
        stage = progress_data.get("stage", "unknown")
        step = progress_data.get("status", "")

        # Optional details
        details = {
            k: v
            for k, v in progress_data.items()
            if k not in ["current", "total", "stage", "status"]
        }

        print(
            f"🔍 PROGRESS DEBUG: Updating job {job_id} - {percent:.1f}% stage: {stage}"
        )  # DEBUG

        # Update progress using global function with proper signature
        await update_job_progress(
            job_id=job_id,
            stage=stage,
            percent=percent,
            step=step,
            details=details if details else None,
        )

        # Create progress message for WebSocket
        message = DesktopAppMessage(
            action="job_update",
            data={
                "job_id": job_id,
                "progress": progress_data,
                "timestamp": datetime.now().isoformat(),
            },
        )

        print(f"🔍 PROGRESS DEBUG: Broadcasting to subscribers...")  # DEBUG

        # Send to subscribed clients using broadcast_to_job_subscribers
        await connection_manager.broadcast_to_job_subscribers(job_id, message)

        # Count subscribers
        subscribers = connection_manager.job_subscriptions.get(job_id, set())

        print(f"🔍 PROGRESS DEBUG: Notified {len(subscribers)} subscribers")  # DEBUG

        logger.info(
            f"Notified {len(subscribers)} clients about job {job_id} progress: {percent:.1f}% ({stage})"
        )
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "job_id": job_id,
                "percent": percent,
                "stage": stage,
                "step": step,
                "notified_clients": len(subscribers),
                "clients": list(subscribers),
            },
        )
    except Exception as e:
        print(f"🔍 PROGRESS ERROR: {e}")  # DEBUG
        logger.error(f"Error notifying job progress for {job_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to notify progress: {str(e)}"
        )


@router.get("/health")
async def websocket_health_check():
    """Health check endpoint for WebSocket service."""
    try:
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "service": "websocket",
                "timestamp": datetime.now().isoformat(),
                "active_connections": len(connection_manager.active_connections),
                "version": "1.0.0",
            },
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "websocket",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        )
