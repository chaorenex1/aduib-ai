from __future__ import annotations

from .builders import (
    build_memory_api_idempotency_key,
    build_task_request_idempotency_key,
    new_task_id,
    new_trace_id,
)
from .contracts import MemorySourceRef, MemoryTaskCreateCommand, MemoryWriteAccepted, MemoryWriteCommand
from .enums import MemoryTriggerType
from .errors import MemoryValidationError, MemoryWritePublishError
from .source_archive_service import MemorySourceArchiveService
from .write_task_service import MemoryWriteTaskService


class MemoryWriteIngestService:
    @classmethod
    async def accept_memory_write(cls, payload: MemoryWriteCommand) -> MemoryWriteAccepted:
        if not payload.content and not payload.file_content:
            raise MemoryValidationError("Either content or file must be provided for memory storage.")

        task_id = new_task_id()
        trace_id = new_trace_id()
        archive_ref = await MemorySourceArchiveService.archive_memory_api(payload, task_id=task_id, trace_id=trace_id)
        source_ref = MemorySourceRef(
            type=MemoryTriggerType.MEMORY_API.value,
            id=task_id,
            path=archive_ref.path,
        )
        task = MemoryWriteTaskService.create_task(
            task_id=task_id,
            trigger_type=MemoryTriggerType.MEMORY_API,
            user_id=payload.user_id,
            agent_id=payload.agent_id,
            project_id=payload.project_id,
            trace_id=trace_id,
            idempotency_key=build_memory_api_idempotency_key(payload),
            source_ref=source_ref,
            archive_ref=archive_ref,
        )
        try:
            queued_task = MemoryWriteTaskService.publish_task(task.task_id)
        except Exception as exc:
            raise MemoryWritePublishError(str(exc), task_id=task.task_id) from exc
        return cls._accepted_response(queued_task)

    @classmethod
    async def accept_task_request(cls, payload: MemoryTaskCreateCommand) -> MemoryWriteAccepted:
        task_id = new_task_id()
        trace_id = new_trace_id()
        archive_ref = None
        if payload.trigger_type == MemoryTriggerType.SESSION_COMMIT:
            archive_ref = await MemorySourceArchiveService.archive_session_commit(
                payload,
                task_id=task_id,
                trace_id=trace_id,
            )
        task = MemoryWriteTaskService.create_task(
            task_id=task_id,
            trigger_type=payload.trigger_type,
            user_id=payload.user_id,
            agent_id=payload.agent_id,
            project_id=payload.project_id,
            trace_id=trace_id,
            idempotency_key=build_task_request_idempotency_key(payload),
            source_ref=payload.source_ref,
            archive_ref=archive_ref,
        )
        try:
            queued_task = MemoryWriteTaskService.publish_task(task.task_id)
        except Exception as exc:
            raise MemoryWritePublishError(str(exc), task_id=task.task_id) from exc
        return cls._accepted_response(queued_task)

    @staticmethod
    def _accepted_response(task) -> MemoryWriteAccepted:
        return MemoryWriteAccepted(
            task_id=task.task_id,
            trace_id=task.trace_id,
            trigger_type=task.trigger_type,
            status=task.status,
            phase=task.phase,
            queue_status=task.queue_status,
            source_ref=task.source_ref,
            archive_ref=task.archive_ref,
        )
