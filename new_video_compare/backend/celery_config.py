"""
Celery Configuration for New Video Compare
Handles background task processing for video/audio comparison
"""

from celery import Celery
from kombu import Queue
import os
from config import settings  # ← Fixed import

# Celery application instance
celery_app = Celery(
    "new_video_compare",
    broker=settings.celery_broker_url,  # ← Fixed: lowercase + dedicated field
    backend=settings.celery_result_backend,  # ← Fixed: lowercase + dedicated field
    include=[
        "backend.tasks.video_tasks",
        "backend.tasks.audio_tasks",
        "backend.tasks.comparison_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task routing
    task_routes={
        "tasks.video.*": {"queue": "video_processing"},
        "tasks.audio.*": {"queue": "audio_processing"},
        "tasks.comparison.*": {"queue": "comparison"},
    },
    # Queue definitions
    task_default_queue="default",
    task_queues=(
        Queue("default"),
        Queue("video_processing"),
        Queue("audio_processing"),
        Queue("comparison"),
        Queue("priority", routing_key="priority"),
    ),
    # Performance settings
    worker_concurrency=settings.max_concurrent_jobs,  # ← Use config value
    task_compression="gzip",
    result_compression="gzip",
    # Task execution settings
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,  # 1 hour
    timezone="UTC",
    enable_utc=True,
    # Worker settings
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)


# Health check task
@celery_app.task
def health_check():
    """Health check task for monitoring"""
    import time

    return {
        "status": "healthy",
        "timestamp": time.time(),
        "worker_concurrency": settings.max_concurrent_jobs,
        "broker": settings.celery_broker_url,
        "backend": settings.celery_result_backend,
    }
