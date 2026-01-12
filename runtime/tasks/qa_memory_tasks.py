from __future__ import annotations

from typing import Any, Sequence

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


@celery_app.task(
    bind=True,
    name="runtime.tasks.qa_memory_tasks.create_candidate_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def create_candidate_task(
    self,
    project_id: str,
    question: str,
    answer: str,
    summary: str | None = None,
    tags: Sequence[str] | None = None,
    metadata: dict[str, Any] | None = None,
    source: str | None = None,
    author: str | None = None,
    confidence: float = 0.5,
) -> dict[str, Any]:
    """
    Background task for creating QA memory candidates.
    Offloads LLM tag generation and vector indexing from the request path.
    """
    logger.info(
        "Creating QA candidate in background: project=%s, question_len=%d",
        project_id,
        len(question),
    )
    record = QAMemoryService.create_candidate(
        project_id=project_id,
        question=question,
        answer=answer,
        summary=summary,
        tags=list(tags) if tags else None,
        metadata=metadata,
        source=source,
        author=author,
        confidence=confidence,
    )
    logger.info("QA candidate created: qa_id=%s", record.id)
    return {
        "qa_id": str(record.id),
        "project_id": record.project_id,
        "status": record.status,
        "level": record.level,
    }
