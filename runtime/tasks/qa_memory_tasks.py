from __future__ import annotations

from celery.utils.log import get_task_logger

from runtime.tasks.celery_app import celery_app
from service import QAMemoryService

logger = get_task_logger(__name__)


@celery_app.task(bind=True, name="runtime.tasks.qa_memory_tasks.expire_qa_memory_task", autoretry_for=(Exception,))
def expire_qa_memory_task(self, batch_size: int = 200) -> dict[str, int]:
    """
    Sweep QA memories whose TTL has elapsed and downgrade or deprecate them.
    """
    expired = QAMemoryService.expire_expired_memories(batch_size=batch_size)
    logger.info("Expired %s QA memories in this sweep", expired)
    return {"expired": expired}
