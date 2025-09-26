#!/usr/bin/env python3
"""
Health Check Script for New Video Compare Celery Workers
Monitors worker status, queue health, and Redis connectivity
"""
import sys
import os
import json
import time
from typing import Dict, Any, List
import logging

# Add project root to path
sys.path.insert(0, "/app")

try:
    import redis
    from celery import Celery
    from backend.celery_config import celery_app
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class HealthChecker:
    """Health check utility for Celery infrastructure"""

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        self.celery = celery_app

    def check_redis_connectivity(self) -> Dict[str, Any]:
        """Check Redis server connectivity"""
        try:
            r = redis.from_url(self.redis_url)

            # Basic connectivity test
            ping_result = r.ping()
            if not ping_result:
                return {"status": "error", "message": "Redis ping failed"}

            # Memory usage check
            info = r.info("memory")
            used_memory = info.get("used_memory", 0)
            max_memory = info.get("maxmemory", 0)

            memory_usage = 0
            if max_memory > 0:
                memory_usage = (used_memory / max_memory) * 100

            # Connection count
            clients_info = r.info("clients")
            connected_clients = clients_info.get("connected_clients", 0)

            return {
                "status": "healthy",
                "ping": True,
                "memory_usage_percent": round(memory_usage, 2),
                "used_memory_mb": round(used_memory / 1024 / 1024, 2),
                "connected_clients": connected_clients,
                "redis_version": r.info().get("redis_version", "unknown"),
            }

        except redis.ConnectionError:
            return {"status": "error", "message": "Redis connection failed"}
        except Exception as e:
            return {"status": "error", "message": f"Redis check failed: {str(e)}"}

    def check_celery_workers(self) -> Dict[str, Any]:
        """Check active Celery workers"""
        try:
            # Get active workers
            inspect = self.celery.control.inspect()

            # Check if inspect is available
            active_workers = inspect.active()
            if active_workers is None:
                return {"status": "error", "message": "No Celery workers responding"}

            # Get worker statistics
            stats = inspect.stats() or {}
            registered_tasks = inspect.registered() or {}

            worker_info = {}
            for worker_name in active_workers.keys():
                worker_stats = stats.get(worker_name, {})
                worker_tasks = registered_tasks.get(worker_name, [])

                worker_info[worker_name] = {
                    "active_tasks": len(active_workers.get(worker_name, [])),
                    "total_tasks": worker_stats.get("total", {}),
                    "registered_tasks_count": len(worker_tasks),
                    "pool_info": worker_stats.get("pool", {}),
                    "rusage": worker_stats.get("rusage", {}),
                }

            return {
                "status": "healthy",
                "workers_count": len(active_workers),
                "workers": worker_info,
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Celery workers check failed: {str(e)}",
            }

    def check_queue_health(self) -> Dict[str, Any]:
        """Check message queue health"""
        try:
            r = redis.from_url(self.redis_url)

            # Check queue lengths
            queues = [
                "video_processing",
                "audio_processing",
                "comparison",
                "default",
                "priority",
            ]
            queue_info = {}

            total_pending = 0
            for queue_name in queues:
                queue_key = f"celery:{queue_name}"
                length = r.llen(queue_key)
                queue_info[queue_name] = {
                    "pending_tasks": length,
                    "queue_key": queue_key,
                }
                total_pending += length

            # Check for failed tasks (simple heuristic)
            failed_tasks = 0
            try:
                failed_key = "celery-task-meta-*"
                failed_tasks = len(r.keys(failed_key))
            except:
                pass

            return {
                "status": "healthy",
                "total_pending_tasks": total_pending,
                "queues": queue_info,
                "estimated_failed_tasks": failed_tasks,
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Queue health check failed: {str(e)}",
            }

    def check_application_health(self) -> Dict[str, Any]:
        """Check overall application health"""
        try:
            # Check if required directories exist and are writable
            required_dirs = ["/app/media", "/app/temp", "/app/logs"]
            dir_status = {}

            for dir_path in required_dirs:
                if os.path.exists(dir_path):
                    is_writable = os.access(dir_path, os.W_OK)
                    dir_status[dir_path] = {"exists": True, "writable": is_writable}
                else:
                    dir_status[dir_path] = {"exists": False, "writable": False}

            # Check Python modules
            required_modules = ["cv2", "numpy", "librosa", "ffmpeg"]
            module_status = {}

            for module_name in required_modules:
                try:
                    __import__(module_name)
                    module_status[module_name] = True
                except ImportError:
                    module_status[module_name] = False

            return {
                "status": "healthy",
                "directories": dir_status,
                "required_modules": module_status,
                "python_version": sys.version,
                "container_hostname": os.getenv("HOSTNAME", "unknown"),
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Application health check failed: {str(e)}",
            }

    def run_full_health_check(self) -> Dict[str, Any]:
        """Run comprehensive health check"""
        start_time = time.time()

        results = {
            "timestamp": time.time(),
            "overall_status": "healthy",
            "checks": {
                "redis": self.check_redis_connectivity(),
                "celery_workers": self.check_celery_workers(),
                "queue_health": self.check_queue_health(),
                "application": self.check_application_health(),
            },
            "duration_seconds": 0,
        }

        # Determine overall status
        for check_name, check_result in results["checks"].items():
            if check_result.get("status") == "error":
                results["overall_status"] = "unhealthy"
                logger.error(
                    f"Health check failed: {check_name} - {check_result.get('message')}"
                )
                break

        results["duration_seconds"] = round(time.time() - start_time, 2)
        return results


def main():
    """Main health check function"""
    if len(sys.argv) > 1:
        check_type = sys.argv[1]
    else:
        check_type = "full"

    health_checker = HealthChecker()

    try:
        if check_type == "redis":
            result = health_checker.check_redis_connectivity()
        elif check_type == "celery":
            result = health_checker.check_celery_workers()
        elif check_type == "queue":
            result = health_checker.check_queue_health()
        elif check_type == "app":
            result = health_checker.check_application_health()
        else:
            result = health_checker.run_full_health_check()

        # Output results
        if (
            result.get("overall_status") == "healthy"
            or result.get("status") == "healthy"
        ):
            print(f"✅ Health check passed: {json.dumps(result, indent=2)}")
            sys.exit(0)
        else:
            print(f"❌ Health check failed: {json.dumps(result, indent=2)}")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Health check error: {str(e)}")
        logger.exception("Health check exception")
        sys.exit(1)


if __name__ == "__main__":
    main()
