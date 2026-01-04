"""
Background Task: Automatic Task Cache Cleanup (P2)

Runs daily to clean up old task cache entries based on retention policy
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from service.task_cache_service import TaskCacheService

logger = logging.getLogger(__name__)


class TaskCacheCleanupScheduler:
    """
    Scheduler for automatic task cache cleanup

    Handles:
    - Daily cleanup of old tasks
    - Configurable retention period
    - Logging and monitoring
    """

    def __init__(self, retention_days: int = 90):
        """
        Initialize cleanup scheduler

        Args:
            retention_days: Number of days to retain tasks (default: 90)
        """
        self.retention_days = retention_days
        self.last_cleanup: Optional[datetime] = None
        self.total_cleaned = 0

    def should_run_cleanup(self, current_hour: int = 2) -> bool:
        """
        Check if cleanup should run now

        Args:
            current_hour: Hour of day to run cleanup (default: 2 AM)

        Returns:
            True if cleanup should run
        """
        now = datetime.now()

        # Run at specified hour
        if now.hour != current_hour:
            return False

        # Don't run if already ran today
        if self.last_cleanup and self.last_cleanup.date() == now.date():
            return False

        return True

    def run_cleanup(self) -> int:
        """
        Execute cleanup task

        Returns:
            Number of tasks deleted
        """
        logger.info(f"Starting task cache cleanup (retention: {self.retention_days} days)")

        try:
            deleted_count = TaskCacheService.clear_old_tasks(days=self.retention_days)

            self.last_cleanup = datetime.now()
            self.total_cleaned += deleted_count

            logger.info(
                f"Task cache cleanup completed: {deleted_count} tasks deleted "
                f"(total cleaned: {self.total_cleaned})"
            )

            # Clear stats cache to reflect updated counts
            try:
                from component.cache.redis_cache import redis_client
                redis_client.delete("task_cache:statistics")
                logger.debug("Cleared statistics cache after cleanup")
            except Exception as e:
                logger.warning(f"Failed to clear stats cache: {e}")

            return deleted_count

        except Exception as e:
            logger.error(f"Task cache cleanup failed: {e}", exc_info=True)
            raise

    def get_status(self) -> dict:
        """
        Get cleanup scheduler status

        Returns:
            Status dictionary with last_cleanup and total_cleaned
        """
        return {
            "enabled": True,
            "retention_days": self.retention_days,
            "last_cleanup": self.last_cleanup.isoformat() if self.last_cleanup else None,
            "total_cleaned": self.total_cleaned,
            "next_cleanup_hour": 2  # 2 AM
        }


# Global scheduler instance
cleanup_scheduler = TaskCacheCleanupScheduler(retention_days=90)


async def run_scheduled_cleanup():
    """
    Async function to run scheduled cleanup

    This can be called from FastAPI background tasks or APScheduler
    """
    if cleanup_scheduler.should_run_cleanup():
        deleted_count = cleanup_scheduler.run_cleanup()
        return {
            "status": "completed",
            "deleted_count": deleted_count,
            "timestamp": datetime.now().isoformat()
        }
    else:
        return {
            "status": "skipped",
            "reason": "Already ran today or wrong hour",
            "timestamp": datetime.now().isoformat()
        }


def get_cleanup_status() -> dict:
    """
    Get current cleanup scheduler status

    Returns:
        Cleanup status dictionary
    """
    return cleanup_scheduler.get_status()
