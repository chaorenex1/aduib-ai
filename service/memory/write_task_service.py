from __future__ import annotations

import datetime

from models import MemoryWriteTask, get_db
from runtime.tasks.celery_app import celery_app

from .builders import build_queue_payload
from .contracts import ArchivedSourceRef, MemorySourceRef, MemoryWriteTaskResult, MemoryWriteTaskView
from .enums import MemoryQueueStatus, MemoryTaskPhase, MemoryTaskStatus
from .errors import MemoryWriteTaskNotFoundError, MemoryWriteTaskReplayError

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
        with get_db() as session:
            existing = (
                session.query(MemoryWriteTask)
                .filter(MemoryWriteTask.idempotency_key == idempotency_key)
                .order_by(MemoryWriteTask.created_at.desc())
                .first()
            )
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
            session.add(task)
            session.commit()
            session.refresh(task)
            return cls._serialize_task(task)

    @classmethod
    def get_task(cls, task_id: str) -> MemoryWriteTaskView:
        with get_db() as session:
            task = session.query(MemoryWriteTask).filter(MemoryWriteTask.task_id == task_id).first()
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
    def publish_task(cls, task_id: str) -> MemoryWriteTaskView:
        try:
            async_result = celery_app.send_task(MEMORY_WRITE_TASK_NAME, kwargs={"task_id": task_id})
        except Exception as exc:
            cls.mark_publish_failed(task_id, str(exc))
            raise

        queue_payload = build_queue_payload(celery_message_id=async_result.id)
        return cls.mark_queued(task_id, queue_payload=queue_payload)

    @classmethod
    def replay(cls, task_id: str, actor: str | None = None) -> MemoryWriteTaskView:
        with get_db() as session:
            task = session.query(MemoryWriteTask).filter(MemoryWriteTask.task_id == task_id).first()
            if not task:
                raise MemoryWriteTaskNotFoundError("memory write task not found")
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
            task.updated_at = now
            session.commit()

        return cls.publish_task(task_id)

    @classmethod
    def mark_queued(cls, task_id: str, *, queue_payload: dict) -> MemoryWriteTaskView:
        with get_db() as session:
            task = session.query(MemoryWriteTask).filter(MemoryWriteTask.task_id == task_id).first()
            if not task:
                raise MemoryWriteTaskNotFoundError("memory write task not found")
            now = datetime.datetime.now(datetime.UTC)
            task.status = MemoryTaskStatus.ACCEPTED
            task.phase = MemoryTaskPhase.ACCEPTED
            task.queue_status = MemoryQueueStatus.QUEUED
            task.queue_payload = queue_payload
            task.queued_at = now
            task.updated_at = now
            session.commit()
            session.refresh(task)
            return cls._serialize_task(task)

    @classmethod
    def mark_publish_failed(cls, task_id: str, error: str) -> MemoryWriteTaskView:
        with get_db() as session:
            task = session.query(MemoryWriteTask).filter(MemoryWriteTask.task_id == task_id).first()
            if not task:
                raise MemoryWriteTaskNotFoundError("memory write task not found")
            now = datetime.datetime.now(datetime.UTC)
            task.status = MemoryTaskStatus.PUBLISH_FAILED
            task.queue_status = MemoryQueueStatus.PUBLISH_FAILED
            task.last_publish_error = error
            task.publish_failed_at = now
            task.last_error = error
            task.updated_at = now
            session.commit()
            session.refresh(task)
            return cls._serialize_task(task)

    @classmethod
    def mark_running(cls, task_id: str, *, phase: str) -> MemoryWriteTaskView:
        with get_db() as session:
            task = session.query(MemoryWriteTask).filter(MemoryWriteTask.task_id == task_id).first()
            if not task:
                raise MemoryWriteTaskNotFoundError("memory write task not found")
            now = datetime.datetime.now(datetime.UTC)
            task.status = MemoryTaskStatus.RUNNING
            task.phase = phase
            task.started_at = task.started_at or now
            task.updated_at = now
            session.commit()
            session.refresh(task)
            return cls._serialize_task(task)

    @classmethod
    def record_checkpoint(
        cls,
        task_id: str,
        *,
        phase: str,
        result_ref: dict | None = None,
        operator_notes: str | None = None,
    ) -> MemoryWriteTaskView:
        with get_db() as session:
            task = session.query(MemoryWriteTask).filter(MemoryWriteTask.task_id == task_id).first()
            if not task:
                raise MemoryWriteTaskNotFoundError("memory write task not found")
            now = datetime.datetime.now(datetime.UTC)
            task.status = MemoryTaskStatus.RUNNING
            task.phase = phase
            if result_ref is not None:
                task.result_ref = result_ref
            if operator_notes:
                task.operator_notes = operator_notes
            task.updated_at = now
            session.commit()
            session.refresh(task)
            return cls._serialize_task(task)

    @classmethod
    def mark_committed(
        cls,
        task_id: str,
        *,
        result_ref: dict | None = None,
        operator_notes: str | None = None,
    ) -> MemoryWriteTaskView:
        with get_db() as session:
            task = session.query(MemoryWriteTask).filter(MemoryWriteTask.task_id == task_id).first()
            if not task:
                raise MemoryWriteTaskNotFoundError("memory write task not found")
            now = datetime.datetime.now(datetime.UTC)
            task.status = MemoryTaskStatus.COMMITTED
            task.phase = MemoryTaskPhase.COMMITTED
            if result_ref is not None:
                task.result_ref = result_ref
            if operator_notes:
                task.operator_notes = operator_notes
            task.last_error = None
            task.failure_message = None
            task.completed_at = now
            task.updated_at = now
            session.commit()
            session.refresh(task)
            return cls._serialize_task(task)

    @classmethod
    def mark_needs_manual_recovery(
        cls,
        task_id: str,
        *,
        phase: str,
        error: str,
        rollback_metadata: dict | None = None,
    ) -> MemoryWriteTaskView:
        with get_db() as session:
            task = session.query(MemoryWriteTask).filter(MemoryWriteTask.task_id == task_id).first()
            if not task:
                raise MemoryWriteTaskNotFoundError("memory write task not found")
            now = datetime.datetime.now(datetime.UTC)
            task.status = MemoryTaskStatus.NEEDS_MANUAL_RECOVERY
            task.phase = phase
            task.last_error = error
            task.failure_message = error
            task.rollback_metadata = rollback_metadata
            task.completed_at = now
            task.updated_at = now
            session.commit()
            session.refresh(task)
            return cls._serialize_task(task)

    @staticmethod
    def _serialize_task(task: MemoryWriteTask) -> MemoryWriteTaskView:
        return MemoryWriteTaskView(
            task_id=task.task_id,
            trace_id=task.trace_id,
            trigger_type=task.trigger_type,
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
