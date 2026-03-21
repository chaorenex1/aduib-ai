from __future__ import annotations

import datetime
from typing import Any

from libs.context import get_current_user_id
from models import ConversationMessage, TaskJob, get_db
from runtime.tasks.command_runtime import CommandTaskError, normalize_execution_payload
from utils.encoders import jsonable_encoder


class TaskJobError(ValueError):
    """Raised when task job operations are invalid."""


class TaskJobService:
    @classmethod
    def create(cls, payload: dict[str, Any], message_id: str | None = None) -> dict[str, Any]:
        context = cls._resolve_context(message_id, payload)
        normalized = cls._normalize_payload(payload)

        with get_db() as session:
            task_job = TaskJob(
                name=normalized["name"],
                source=normalized["source"],
                cron_id=normalized["cron_id"],
                message_id=message_id,
                user_id=context["user_id"],
                agent_id=context["agent_id"],
                session_id=context["session_id"],
                execution_type=normalized["execution_type"],
                command=normalized["command"],
                script_path=normalized["script_path"],
                timeout_seconds=normalized["timeout_seconds"],
                status="pending",
            )
            session.add(task_job)
            session.commit()
            session.refresh(task_job)
            task_id = task_job.id

        from runtime.tasks.task_job_runner import execute_task_job

        async_result = execute_task_job.delay(task_id)

        with get_db() as session:
            task_job = session.query(TaskJob).filter(TaskJob.id == task_id).first()
            task_job.celery_task_id = async_result.id
            session.commit()
            session.refresh(task_job)
            return cls._serialize_task(task_job)

    @classmethod
    def create_from_cron(cls, cron_job) -> dict[str, Any]:
        payload = {
            "name": cron_job.name,
            "source": "cron",
            "cron_id": cron_job.id,
            "execution_type": cron_job.execution_type,
            "command": cron_job.command,
            "script_path": cron_job.script_path,
            "timeout_seconds": cron_job.timeout_seconds,
            "agent_id": cron_job.agent_id,
            "session_id": cron_job.session_id,
            "user_id": cron_job.user_id,
        }
        return cls.create(payload, message_id=cron_job.message_id)

    @classmethod
    def get(cls, task_id: int, *, sync_state: bool = True) -> dict[str, Any]:
        if sync_state:
            cls.sync_state(task_id)
        with get_db() as session:
            task_job = session.query(TaskJob).filter(TaskJob.id == int(task_id)).first()
            if not task_job:
                raise TaskJobError("task not found")
            return cls._serialize_task(task_job)

    @classmethod
    def cancel(cls, task_id: int) -> dict[str, Any]:
        from runtime.tasks.celery_app import celery_app

        with get_db() as session:
            task_job = session.query(TaskJob).filter(TaskJob.id == int(task_id)).first()
            if not task_job:
                raise TaskJobError("task not found")

            now = datetime.datetime.now()
            task_job.cancellation_requested = True
            task_job.cancel_requested_at = now
            if task_job.celery_task_id:
                celery_app.control.revoke(task_job.celery_task_id, terminate=False)

            if task_job.status == "pending":
                task_job.status = "cancelled"
                task_job.finished_at = now
                task_job.error = "cancelled by user"

            session.commit()
            session.refresh(task_job)
            return cls._serialize_task(task_job)

    @classmethod
    def sync_state(cls, task_id: int) -> None:
        from runtime.tasks.celery_app import celery_app

        with get_db() as session:
            task_job = session.query(TaskJob).filter(TaskJob.id == int(task_id)).first()
            if not task_job or not task_job.celery_task_id:
                return
            if task_job.status in {"completed", "failed", "cancelled"}:
                return

            result = celery_app.AsyncResult(task_job.celery_task_id)
            state = result.state
            now = datetime.datetime.now()
            if state == "STARTED" and task_job.status == "pending":
                task_job.status = "running"
                task_job.started_at = task_job.started_at or now
            elif state == "FAILURE":
                task_job.status = "failed"
                task_job.error = str(result.result)
                task_job.finished_at = now
            elif state == "REVOKED":
                task_job.status = "cancelled"
                task_job.error = task_job.error or "cancelled by user"
                task_job.finished_at = now
            elif state == "SUCCESS" and task_job.output_payload is None:
                task_job.status = "completed"
                task_job.output_payload = jsonable_encoder(result.result, exclude_none=True)
                task_job.finished_at = now
            session.commit()

    @classmethod
    def mark_running(cls, task_id: int, celery_task_id: str | None = None) -> None:
        with get_db() as session:
            task_job = session.query(TaskJob).filter(TaskJob.id == int(task_id)).first()
            if not task_job:
                raise TaskJobError("task not found")
            task_job.status = "running"
            task_job.started_at = task_job.started_at or datetime.datetime.now()
            if celery_task_id:
                task_job.celery_task_id = celery_task_id
            session.commit()

    @classmethod
    def mark_completed(cls, task_id: int, output: Any, *, meta: dict[str, Any] | None = None) -> None:
        with get_db() as session:
            task_job = session.query(TaskJob).filter(TaskJob.id == int(task_id)).first()
            if not task_job:
                raise TaskJobError("task not found")
            payload = {"output": jsonable_encoder(output, exclude_none=True)}
            if meta:
                payload["meta"] = jsonable_encoder(meta, exclude_none=True)
            task_job.status = "completed"
            task_job.output_payload = payload
            task_job.error = None
            task_job.finished_at = datetime.datetime.now()
            session.commit()

    @classmethod
    def mark_failed(cls, task_id: int, error: str) -> None:
        with get_db() as session:
            task_job = session.query(TaskJob).filter(TaskJob.id == int(task_id)).first()
            if not task_job:
                raise TaskJobError("task not found")
            task_job.status = "failed"
            task_job.error = error
            task_job.finished_at = datetime.datetime.now()
            session.commit()

    @classmethod
    def _normalize_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        timeout_seconds = payload.get("timeout_seconds")
        if timeout_seconds is not None:
            timeout_seconds = int(timeout_seconds)
            if timeout_seconds < 1:
                raise TaskJobError("timeout_seconds must be at least 1")

        source = (payload.get("source") or "manual").lower()
        if source not in {"manual", "cron"}:
            raise TaskJobError(f"unsupported source: {source}")

        try:
            execution = normalize_execution_payload(payload, script_prefix="task_jobs")
        except CommandTaskError as exc:
            raise TaskJobError(str(exc)) from exc

        return {
            "name": payload.get("name") or payload.get("title"),
            "source": source,
            "cron_id": cls._normalize_optional_int(payload.get("cron_id")),
            "execution_type": execution["execution_type"],
            "command": execution["command"],
            "script_path": execution["script_path"],
            "timeout_seconds": timeout_seconds,
        }

    @classmethod
    def _resolve_context(cls, message_id: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        explicit_agent_id = cls._normalize_optional_int(payload.get("agent_id"))
        explicit_session_id = cls._normalize_optional_int(payload.get("session_id"))
        explicit_user_id = payload.get("user_id") or get_current_user_id()

        resolved = {
            "agent_id": explicit_agent_id,
            "session_id": explicit_session_id,
            "user_id": explicit_user_id,
        }
        if not message_id:
            return resolved

        with get_db() as session:
            message = (
                session.query(ConversationMessage)
                .filter(ConversationMessage.message_id == message_id)
                .order_by(ConversationMessage.created_at.desc())
                .first()
            )
            if message:
                resolved["agent_id"] = resolved["agent_id"] if resolved["agent_id"] is not None else message.agent_id
                resolved["session_id"] = (
                    resolved["session_id"] if resolved["session_id"] is not None else message.agent_session_id
                )
                resolved["user_id"] = resolved["user_id"] or message.user_id
        return resolved

    @staticmethod
    def _normalize_optional_int(value: Any) -> int | None:
        if value in (None, "", False):
            return None
        return int(value)

    @staticmethod
    def _serialize_task(task_job: TaskJob) -> dict[str, Any]:
        return {
            "id": task_job.id,
            "name": task_job.name,
            "source": task_job.source,
            "cron_id": task_job.cron_id,
            "message_id": task_job.message_id,
            "user_id": task_job.user_id,
            "agent_id": task_job.agent_id,
            "session_id": task_job.session_id,
            "execution_type": task_job.execution_type,
            "command": task_job.command,
            "script_path": task_job.script_path,
            "timeout_seconds": task_job.timeout_seconds,
            "status": task_job.status,
            "output_payload": task_job.output_payload,
            "error": task_job.error,
            "celery_task_id": task_job.celery_task_id,
            "cancellation_requested": task_job.cancellation_requested,
            "created_at": task_job.created_at.isoformat() if task_job.created_at else None,
            "started_at": task_job.started_at.isoformat() if task_job.started_at else None,
            "finished_at": task_job.finished_at.isoformat() if task_job.finished_at else None,
            "cancel_requested_at": task_job.cancel_requested_at.isoformat() if task_job.cancel_requested_at else None,
            "updated_at": task_job.updated_at.isoformat() if task_job.updated_at else None,
        }
