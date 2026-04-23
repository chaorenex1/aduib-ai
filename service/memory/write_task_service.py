from __future__ import annotations

import datetime

from models import MemoryWriteTask

from .base.contracts import ArchivedSourceRef, MemorySourceRef, MemoryWriteTaskResult, MemoryWriteTaskView
from .base.enums import MemoryQueueStatus, MemoryTaskPhase, MemoryTaskStatus
from .base.errors import MemoryWriteTaskNotFoundError, MemoryWriteTaskReplayError
from .repository import MemoryWriteTaskRepository

MEMORY_WRITE_TASK_NAME = "runtime.tasks.memory_write.execute"


class MemoryWriteTaskService:
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
        queue_payload: dict | None = None,
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
            queue_payload=queue_payload,
            status=MemoryTaskStatus.ACCEPTED,
            phase=MemoryTaskPhase.ACCEPTED,
            queue_status=MemoryQueueStatus.PUBLISH_PENDING,
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
            result_ref=task.result_ref,
            archive_ref=task.archive_ref,
            journal_ref=task.journal_ref,
            operator_notes=task.operator_notes,
            last_error=task.last_error,
        )

    @classmethod
    def prepare_replay(cls, task_id: str, actor: str | None = None) -> MemoryWriteTaskView:
        def _mutate(task: MemoryWriteTask) -> None:
            if task.queue_status != MemoryQueueStatus.PUBLISH_FAILED:
                raise MemoryWriteTaskReplayError("only publish_failed tasks can be replayed")
            now = datetime.datetime.now(datetime.UTC)
            task.replayed_by = actor
            task.replayed_at = now
            task.retry_count = int(task.retry_count or 0) + 1
            task.status = MemoryTaskStatus.ACCEPTED
            task.phase = MemoryTaskPhase.ACCEPTED
            task.queue_status = MemoryQueueStatus.PUBLISH_PENDING
            task.last_publish_error = None
            task.publish_failed_at = None

        task = MemoryWriteTaskRepository.update_task(task_id, mutate=_mutate)
        if task is None:
            raise MemoryWriteTaskNotFoundError("memory write task not found")
        return cls._serialize_task(task)

    @classmethod
    def mark_queued(cls, task_id: str, *, queue_payload: dict) -> MemoryWriteTaskView:
        def _mutate(task: MemoryWriteTask) -> None:
            now = datetime.datetime.now(datetime.UTC)
            task.status = MemoryTaskStatus.ACCEPTED
            task.phase = MemoryTaskPhase.ACCEPTED
            task.queue_status = MemoryQueueStatus.QUEUED
            task.queue_payload = queue_payload
            task.queued_at = now

        task = MemoryWriteTaskRepository.update_task(task_id, mutate=_mutate)
        if task is None:
            raise MemoryWriteTaskNotFoundError("memory write task not found")
        return cls._serialize_task(task)

    @staticmethod
    def get_queue_task_name() -> str:
        return MEMORY_WRITE_TASK_NAME

    @classmethod
    def mark_publish_failed(cls, task_id: str, error: str) -> MemoryWriteTaskView:
        def _mutate(task: MemoryWriteTask) -> None:
            now = datetime.datetime.now(datetime.UTC)
            task.status = MemoryTaskStatus.PUBLISH_FAILED
            task.queue_status = MemoryQueueStatus.PUBLISH_FAILED
            task.last_publish_error = error
            task.publish_failed_at = now
            task.last_error = error

        task = MemoryWriteTaskRepository.update_task(task_id, mutate=_mutate)
        if task is None:
            raise MemoryWriteTaskNotFoundError("memory write task not found")
        return cls._serialize_task(task)

    @classmethod
    def mark_running(cls, task_id: str, *, phase: str) -> MemoryWriteTaskView:
        def _mutate(task: MemoryWriteTask) -> None:
            now = datetime.datetime.now(datetime.UTC)
            task.status = MemoryTaskStatus.RUNNING
            task.phase = phase
            task.started_at = task.started_at or now

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
        result_ref: dict | None = None,
        operator_notes: str | None = None,
        journal_ref: str | None = None,
        rollback_metadata: dict | None = None,
    ) -> MemoryWriteTaskView:
        def _mutate(task: MemoryWriteTask) -> None:
            task.status = MemoryTaskStatus.RUNNING
            task.phase = phase
            if result_ref is not None:
                task.result_ref = result_ref
            resolved_journal_ref = journal_ref or (result_ref or {}).get("journal_ref")
            if resolved_journal_ref:
                task.journal_ref = resolved_journal_ref
            resolved_rollback_metadata = rollback_metadata or (result_ref or {}).get("rollback_metadata")
            if resolved_rollback_metadata is not None:
                task.rollback_metadata = resolved_rollback_metadata
            if operator_notes:
                task.operator_notes = operator_notes

        task = MemoryWriteTaskRepository.update_task(task_id, mutate=_mutate)
        if task is None:
            raise MemoryWriteTaskNotFoundError("memory write task not found")
        return cls._serialize_task(task)

    @classmethod
    def mark_committed(
        cls,
        task_id: str,
        *,
        result_ref: dict | None = None,
        operator_notes: str | None = None,
        journal_ref: str | None = None,
    ) -> MemoryWriteTaskView:
        def _mutate(task: MemoryWriteTask) -> None:
            now = datetime.datetime.now(datetime.UTC)
            task.status = MemoryTaskStatus.COMMITTED
            task.phase = MemoryTaskPhase.COMMITTED
            if result_ref is not None:
                task.result_ref = result_ref
            resolved_journal_ref = journal_ref or (result_ref or {}).get("journal_ref")
            if resolved_journal_ref:
                task.journal_ref = resolved_journal_ref
            if operator_notes:
                task.operator_notes = operator_notes
            task.last_error = None
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
        rollback_metadata: dict | None = None,
        journal_ref: str | None = None,
    ) -> MemoryWriteTaskView:
        def _mutate(task: MemoryWriteTask) -> None:
            now = datetime.datetime.now(datetime.UTC)
            task.status = MemoryTaskStatus.NEEDS_MANUAL_RECOVERY
            task.phase = phase
            task.last_error = error
            task.failure_message = error
            if rollback_metadata is not None:
                task.rollback_metadata = rollback_metadata
            if journal_ref:
                task.journal_ref = journal_ref
            task.completed_at = now

        task = MemoryWriteTaskRepository.update_task(task_id, mutate=_mutate)
        if task is None:
            raise MemoryWriteTaskNotFoundError("memory write task not found")
        return cls._serialize_task(task)

    @staticmethod
    def _serialize_task(task: MemoryWriteTask) -> MemoryWriteTaskView:
        return MemoryWriteTaskView(
            task_id=task.task_id,
            trace_id=task.trace_id,
            trigger_type=task.trigger_type,
            user_id=task.user_id,
            agent_id=task.agent_id,
            project_id=task.project_id,
            status=task.status,
            phase=task.phase,
            queue_status=task.queue_status,
            source_ref=MemorySourceRef(**(task.source_ref or {})),
            archive_ref=ArchivedSourceRef(**task.archive_ref) if task.archive_ref else None,
            queue_payload=task.queue_payload,
            result_ref=task.result_ref,
            retry_count=int(task.retry_count or 0),
            retry_budget=int(task.retry_budget or 0),
            last_publish_error=task.last_publish_error,
            failure_code=task.failure_code,
            failure_message=task.failure_message,
            last_error=task.last_error,
            rollback_metadata=task.rollback_metadata,
            journal_ref=task.journal_ref,
            operator_notes=task.operator_notes,
            replayed_by=task.replayed_by,
            replayed_at=task.replayed_at.isoformat() if task.replayed_at else None,
            queued_at=task.queued_at.isoformat() if task.queued_at else None,
            started_at=task.started_at.isoformat() if task.started_at else None,
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
            created_at=task.created_at.isoformat() if task.created_at else None,
            updated_at=task.updated_at.isoformat() if task.updated_at else None,
        )
