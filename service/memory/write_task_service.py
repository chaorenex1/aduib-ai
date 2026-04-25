from __future__ import annotations

import datetime

from models import MemoryWriteTask
from runtime.tasks.celery_app import celery_app

from .base.builders import (
    build_task_request_idempotency_key,
    new_task_id,
    new_trace_id,
)
from .base.contracts import (
    ArchivedSourceRef,
    MemorySourceRef,
    MemoryTaskCreateCommand,
    MemoryWriteAccepted,
    MemoryWriteTaskResult,
    MemoryWriteTaskView,
)
from .base.enums import MemoryTaskFinalStatus, MemoryTaskPhase, MemoryTriggerType
from .base.errors import MemoryValidationError, MemoryWritePublishError, MemoryWriteTaskNotFoundError
from .repository import MemoryWriteTaskRepository

MEMORY_WRITE_TASK_NAME = "runtime.tasks.memory_write.execute"


class MemoryWriteTaskService:
    @classmethod
    async def accept_task_request(cls, payload: MemoryTaskCreateCommand) -> MemoryWriteAccepted:
        task_id = new_task_id()
        trace_id = new_trace_id()
        trigger_type = payload.trigger_type

        from runtime.memory.source_archive import MemorySourceArchiveRuntime

        archive_ref = None
        source_ref = payload.source_ref
        if trigger_type == MemoryTriggerType.SESSION_COMMIT:
            archive_ref = await MemorySourceArchiveRuntime.archive_session_commit(
                payload,
                task_id=task_id,
                trace_id=trace_id,
            )
        elif trigger_type == MemoryTriggerType.MEMORY_API:
            source_ref = cls._normalize_conversation_source_ref(payload)

        task = cls.create_task(
            task_id=task_id,
            trigger_type=trigger_type,
            user_id=payload.user_id,
            agent_id=payload.agent_id,
            project_id=payload.project_id,
            trace_id=trace_id,
            idempotency_key=build_task_request_idempotency_key(payload),
            source_ref=source_ref,
            archive_ref=archive_ref,
        )
        queued_task = cls._publish_task(task)
        return cls._accepted_response(queued_task)

    @classmethod
    def create_task(
        cls,
        *,
        task_id: str,
        trigger_type,
        user_id: str | None,
        agent_id: str | None,
        project_id: str | None,
        trace_id: str,
        idempotency_key: str,
        source_ref: MemorySourceRef,
        archive_ref: ArchivedSourceRef | None,
    ) -> MemoryWriteTaskView:
        existing = MemoryWriteTaskRepository.get_by_idempotency_key(idempotency_key)
        if existing:
            return cls._serialize_task(existing)

        task = MemoryWriteTask(
            task_id=task_id,
            trigger_type=trigger_type,
            user_id=user_id,
            agent_id=agent_id,
            project_id=project_id,
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            source_ref=source_ref.model_dump(mode="python", exclude_none=True),
            archive_ref=archive_ref.model_dump(mode="python", exclude_none=True) if archive_ref else None,
            phase=MemoryTaskPhase.ACCEPTED,
        )
        task = MemoryWriteTaskRepository.create(task)
        return cls._serialize_task(task)

    @classmethod
    def get_task(cls, task_id: str) -> MemoryWriteTaskView:
        task = MemoryWriteTaskRepository.get_by_task_id(task_id)
        if not task:
            raise MemoryWriteTaskNotFoundError("memory write task not found")
        return cls._serialize_task(task)

    @classmethod
    def get_task_result(cls, task_id: str) -> MemoryWriteTaskResult:
        task = cls.get_task(task_id)
        return MemoryWriteTaskResult(
            task_id=task.task_id,
            status=task.status,
            phase=task.phase,
            stage=task.stage,
            archive_ref=task.archive_ref,
            failure_message=task.failure_message,
        )

    @classmethod
    def mark_queued(cls, task_id: str) -> MemoryWriteTaskView:
        def _mutate(task: MemoryWriteTask) -> None:
            now = datetime.datetime.now()
            task.queued_at = now

        task = MemoryWriteTaskRepository.update_task(task_id, mutate=_mutate)
        if task is None:
            raise MemoryWriteTaskNotFoundError("memory write task not found")
        return cls._serialize_task(task)

    @staticmethod
    def get_queue_task_name() -> str:
        return MEMORY_WRITE_TASK_NAME

    @classmethod
    def _publish_task(cls, task: MemoryWriteTaskView) -> MemoryWriteTaskView:
        try:
            celery_app.send_task(
                cls.get_queue_task_name(),
                kwargs={"task_id": task.task_id},
            )
        except Exception as exc:
            cls.mark_publish_failed(task.task_id, str(exc))
            raise MemoryWritePublishError(str(exc), task_id=task.task_id) from exc

        return cls.mark_queued(task.task_id)

    @classmethod
    def mark_publish_failed(cls, task_id: str, error: str) -> MemoryWriteTaskView:
        def _mutate(task: MemoryWriteTask) -> None:
            now = datetime.datetime.now(datetime.UTC)
            task.status = MemoryTaskFinalStatus.FAILED
            task.failure_message = error
            task.completed_at = now

        task = MemoryWriteTaskRepository.update_task(task_id, mutate=_mutate)
        if task is None:
            raise MemoryWriteTaskNotFoundError("memory write task not found")
        return cls._serialize_task(task)

    @classmethod
    def mark_running(cls, task_id: str, *, phase: str) -> MemoryWriteTaskView:
        def _mutate(task: MemoryWriteTask) -> None:
            now = datetime.datetime.now(datetime.UTC)
            task.phase = phase
            task.started_at = task.started_at or now

        task = MemoryWriteTaskRepository.update_task(task_id, mutate=_mutate)
        if task is None:
            raise MemoryWriteTaskNotFoundError("memory write task not found")
        return cls._serialize_task(task)

    @classmethod
    def attach_archive_ref(cls, task_id: str, *, archive_ref: ArchivedSourceRef) -> MemoryWriteTaskView:
        def _mutate(task: MemoryWriteTask) -> None:
            task.archive_ref = archive_ref.model_dump(mode="python", exclude_none=True)

        task = MemoryWriteTaskRepository.update_task(task_id, mutate=_mutate)
        if task is None:
            raise MemoryWriteTaskNotFoundError("memory write task not found")
        return cls._serialize_task(task)

    @classmethod
    def clear_archive_ref(cls, task_id: str) -> MemoryWriteTaskView:
        def _mutate(task: MemoryWriteTask) -> None:
            task.archive_ref = None

        task = MemoryWriteTaskRepository.update_task(task_id, mutate=_mutate)
        if task is None:
            raise MemoryWriteTaskNotFoundError("memory write task not found")
        return cls._serialize_task(task)

    @classmethod
    def record_checkpoint(
        cls,
        task_id: str,
        *,
        phase: str,
    ) -> MemoryWriteTaskView:
        def _mutate(task: MemoryWriteTask) -> None:
            task.phase = phase

        task = MemoryWriteTaskRepository.update_task(task_id, mutate=_mutate)
        if task is None:
            raise MemoryWriteTaskNotFoundError("memory write task not found")
        return cls._serialize_task(task)

    @classmethod
    def mark_committed(cls, task_id: str) -> MemoryWriteTaskView:
        def _mutate(task: MemoryWriteTask) -> None:
            now = datetime.datetime.now(datetime.UTC)
            task.status = MemoryTaskFinalStatus.SUCCESS
            task.phase = MemoryTaskPhase.COMMITTED
            task.failure_message = None
            task.completed_at = now

        task = MemoryWriteTaskRepository.update_task(task_id, mutate=_mutate)
        if task is None:
            raise MemoryWriteTaskNotFoundError("memory write task not found")
        return cls._serialize_task(task)

    @classmethod
    def mark_needs_manual_recovery(
        cls,
        task_id: str,
        *,
        phase: str,
        error: str,
    ) -> MemoryWriteTaskView:
        def _mutate(task: MemoryWriteTask) -> None:
            now = datetime.datetime.now(datetime.UTC)
            task.status = MemoryTaskFinalStatus.FAILED
            task.phase = phase
            task.failure_message = error
            task.completed_at = now

        task = MemoryWriteTaskRepository.update_task(task_id, mutate=_mutate)
        if task is None:
            raise MemoryWriteTaskNotFoundError("memory write task not found")
        return cls._serialize_task(task)

    @staticmethod
    def _serialize_task(task: MemoryWriteTask) -> MemoryWriteTaskView:
        stage = _display_stage(task.phase)
        return MemoryWriteTaskView(
            task_id=task.task_id,
            trace_id=task.trace_id,
            trigger_type=task.trigger_type,
            user_id=task.user_id,
            agent_id=task.agent_id,
            project_id=task.project_id,
            status=task.status,
            phase=task.phase,
            stage=stage,
            source_ref=MemorySourceRef(**(task.source_ref or {})),
            archive_ref=ArchivedSourceRef(**task.archive_ref) if task.archive_ref else None,
            failure_message=task.failure_message,
            queued_at=task.queued_at.isoformat() if task.queued_at else None,
            started_at=task.started_at.isoformat() if task.started_at else None,
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
            created_at=task.created_at.isoformat() if task.created_at else None,
            updated_at=task.updated_at.isoformat() if task.updated_at else None,
        )

    @staticmethod
    def _accepted_response(task: MemoryWriteTaskView) -> MemoryWriteAccepted:
        return MemoryWriteAccepted(
            task_id=task.task_id,
            trace_id=task.trace_id,
            trigger_type=task.trigger_type,
            user_id=task.user_id,
            agent_id=task.agent_id,
            project_id=task.project_id,
            status=task.status,
            phase=task.phase,
            stage=task.stage,
            source_ref=task.source_ref,
            archive_ref=task.archive_ref,
        )

    @staticmethod
    def _normalize_conversation_source_ref(payload: MemoryTaskCreateCommand) -> MemorySourceRef:
        source_ref = payload.source_ref

        from .conversation_repository import ConversationRepository

        conversation = ConversationRepository.get_conversation(
            user_id=payload.user_id,
            conversation_id=source_ref.conversation_id,
        )
        if conversation is None:
            raise MemoryValidationError("conversation source_ref not found for user")
        _validate_conversation_scope(
            agent_id=payload.agent_id,
            project_id=payload.project_id,
            conversation=conversation,
        )

        return MemorySourceRef(
            type="conversation",
            conversation_id=conversation.conversation_id,
        )


def _validate_conversation_scope(*, agent_id: str | None, project_id: str | None, conversation) -> None:
    conversation_agent_id = getattr(conversation, "agent_id", None)
    conversation_project_id = getattr(conversation, "project_id", None)

    if agent_id is not None and conversation_agent_id is not None and agent_id != conversation_agent_id:
        raise MemoryValidationError("conversation source_ref agent_id does not match current scope")
    if project_id is not None and conversation_project_id is not None and project_id != conversation_project_id:
        raise MemoryValidationError("conversation source_ref project_id does not match current scope")


def _display_stage(phase: MemoryTaskPhase | str | None) -> str | None:
    if phase is None:
        return None
    raw = str(phase)
    if raw == str(MemoryTaskPhase.ACCEPTED):
        return "accepted"
    if raw == str(MemoryTaskPhase.PREPARE_EXTRACT_CONTEXT):
        return "extract_context"
    if raw == str(MemoryTaskPhase.EXTRACT_OPERATIONS):
        return "extract_operations"
    if raw == str(MemoryTaskPhase.MEMORY_UPDATER):
        return "memory_updater"
    if raw == str(MemoryTaskPhase.COMMITTED):
        return "committed"
    return raw
