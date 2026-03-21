from __future__ import annotations

import logging
from typing import Any

from libs.contextVar_wrapper_enhanced import ContextVarWrapper

logger = logging.getLogger(__name__)

event_manager_context = ContextVarWrapper.create("event_manager")

# Event name → Celery task name mapping
_EVENT_TASK_MAP: dict[str, str] = {
    "paragraph_rag_from_web_memo": "event.paragraph_rag_from_web_memo",
    "qa_rag_from_conversation_message": "event.qa_rag_from_conversation_message",
    "memory_stored": "event.memory_stored",
    "memory_domain_from_conversation": "event.memory_domain_from_conversation",
    "memory_topic_from_conversation": "event.memory_topic_from_conversation",
    "memory_retrieval_logged": "event.memory_retrieval_logged",
    "learning_signal_persist": "event.learning_signal_persist",
    "learning_signal_persist_batch": "event.learning_signal_persist_batch",
}


class EventManager:
    """Celery-backed event dispatcher.

    emit() serializes the payload and dispatches a Celery task to a worker process.
    subscribe() is kept as a no-op decorator for backward compatibility.
    start() / stop() are no-ops; Celery workers are managed externally.
    """

    def emit(self, event: str, **kwargs: Any) -> None:
        """Sync emit: dispatch event as a Celery task. All kwargs must be JSON-serializable."""
        task_name = _EVENT_TASK_MAP.get(event)
        if not task_name:
            logger.warning("No Celery task registered for event '%s'", event)
            return
        from runtime.tasks.celery_app import celery_app

        celery_app.send_task(task_name, kwargs=kwargs)

    async def emit_async(self, event: str, **kwargs: Any) -> None:
        """Async-compatible emit; delegates to sync emit."""
        self.emit(event, **kwargs)

    def subscribe(self, event: str):
        """No-op decorator retained for backward compatibility."""

        def decorator(func):
            return func

        return decorator

    def start(self) -> None:
        """No-op: Celery workers are managed by an external process."""

    async def stop(self) -> None:
        """No-op: Celery workers are managed by an external process."""
