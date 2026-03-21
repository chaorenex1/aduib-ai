from __future__ import annotations

import asyncio
import logging

from runtime.tasks.dispatcher import TaskDispatcher
from runtime.tasks.celery_app import celery_app
from service.task_job_service import TaskJobError, TaskJobService

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="runtime.tasks.task_job_runner.execute_task_job",
    acks_late=True,
    track_started=True,
)
def execute_task_job(self, task_job_id: int) -> dict:
    try:
        TaskJobService.mark_running(task_job_id, celery_task_id=self.request.id)
        task_data = TaskJobService.get(task_job_id, sync_state=False)
        result = asyncio.run(TaskDispatcher().dispatch(_DictTaskJob(task_data)))

        if result.success:
            TaskJobService.mark_completed(task_job_id, result.output, meta=result.meta)
        else:
            TaskJobService.mark_failed(task_job_id, result.error or "task execution failed")

        return {
            "task_job_id": task_job_id,
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "meta": result.meta,
        }
    except TaskJobError as exc:
        logger.error("Task job %s failed before execution: %s", task_job_id, exc, exc_info=True)
        TaskJobService.mark_failed(task_job_id, str(exc))
        raise
    except Exception as exc:
        logger.error("Task job %s failed: %s", task_job_id, exc, exc_info=True)
        TaskJobService.mark_failed(task_job_id, str(exc))
        raise


class _DictTaskJob:
    def __init__(self, payload: dict) -> None:
        self.id = payload["id"]
        self.message_id = payload.get("message_id")
        self.user_id = payload.get("user_id")
        self.agent_id = payload.get("agent_id")
        self.session_id = payload.get("session_id")
        self.execution_type = payload.get("execution_type")
        self.command = payload.get("command")
        self.script_path = payload.get("script_path")
        self.timeout_seconds = payload.get("timeout_seconds")
