from __future__ import annotations

import datetime
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger

from libs.context import get_current_user_id
from models import ConversationMessage, CronJob, get_db
from runtime.task.command_runtime import CommandTaskError, normalize_execution_payload


class CronJobError(ValueError):
    """Raised when cron job operations are invalid."""


class CronJobService:
    @classmethod
    def create(cls, payload: dict[str, Any], message_id: str | None = None) -> dict[str, Any]:
        context = cls._resolve_context(message_id, payload)
        normalized = cls._normalize_payload(payload)
        next_run_at = cls.compute_next_run(normalized["schedule"], normalized["timezone"])

        with get_db() as session:
            cron_job = CronJob(
                name=normalized["name"],
                message_id=message_id,
                user_id=context["user_id"],
                agent_id=context["agent_id"],
                session_id=context["session_id"],
                schedule=normalized["schedule"],
                timezone=normalized["timezone"],
                enabled=normalized["enabled"],
                execution_type=normalized["execution_type"],
                command=normalized["command"],
                script_path=normalized["script_path"],
                timeout_seconds=normalized["timeout_seconds"],
                next_run_at=next_run_at,
            )
            session.add(cron_job)
            session.commit()
            session.refresh(cron_job)
            serialized = cls._serialize_cron(cron_job)

        from runtime.tasks.cron_scheduler import cron_scheduler

        if normalized["enabled"]:
            next_registered = cron_scheduler.register_cron(cron_job.id)
            if next_registered is not None:
                cls.update_next_run(cron_job.id, next_registered)
                serialized["next_run_at"] = next_registered.isoformat()
        return serialized

    @classmethod
    def list(cls, payload: dict[str, Any], message_id: str | None = None) -> list[dict[str, Any]]:
        context = cls._resolve_context(message_id, payload)
        include_disabled = bool(payload.get("include_disabled", False))

        with get_db() as session:
            query = session.query(CronJob)
            if context["agent_id"] is not None:
                query = query.filter(CronJob.agent_id == context["agent_id"])
            if context["session_id"] is not None:
                query = query.filter(CronJob.session_id == context["session_id"])
            if context["user_id"]:
                query = query.filter(CronJob.user_id == context["user_id"])
            if not include_disabled:
                query = query.filter(CronJob.enabled.is_(True))

            rows = query.order_by(CronJob.updated_at.desc(), CronJob.id.desc()).all()
            return [cls._serialize_cron(row) for row in rows]

    @classmethod
    def delete(cls, payload: dict[str, Any], message_id: str | None = None) -> dict[str, Any]:
        context = cls._resolve_context(message_id, payload)
        cron_id = payload.get("cron_id") or payload.get("id")
        if cron_id is None:
            raise CronJobError("cron_id is required")

        from runtime.tasks.cron_scheduler import cron_scheduler

        with get_db() as session:
            query = session.query(CronJob).filter(CronJob.id == int(cron_id))
            if context["agent_id"] is not None:
                query = query.filter(CronJob.agent_id == context["agent_id"])
            if context["session_id"] is not None:
                query = query.filter(CronJob.session_id == context["session_id"])
            if context["user_id"]:
                query = query.filter(CronJob.user_id == context["user_id"])
            cron_job = query.first()
            if not cron_job:
                raise CronJobError("cron not found")
            summary = cls._serialize_cron(cron_job)
            session.delete(cron_job)
            session.commit()

        cron_scheduler.remove_cron(int(cron_id))
        return {"deleted": True, "cron": summary}

    @classmethod
    def get_record(cls, cron_id: int) -> CronJob | None:
        with get_db() as session:
            cron_job = session.query(CronJob).filter(CronJob.id == int(cron_id)).first()
            if cron_job:
                session.expunge(cron_job)
            return cron_job

    @classmethod
    def update_next_run(cls, cron_id: int, next_run_at: datetime.datetime | None) -> None:
        with get_db() as session:
            cron_job = session.query(CronJob).filter(CronJob.id == int(cron_id)).first()
            if not cron_job:
                return
            cron_job.next_run_at = cls._normalize_datetime(next_run_at)
            session.commit()

    @classmethod
    def mark_triggered(
        cls,
        cron_id: int,
        *,
        last_task_id: int | None,
        last_run_at: datetime.datetime,
        next_run_at: datetime.datetime | None,
    ) -> None:
        with get_db() as session:
            cron_job = session.query(CronJob).filter(CronJob.id == int(cron_id)).first()
            if not cron_job:
                return
            cron_job.last_task_id = last_task_id
            cron_job.last_run_at = cls._normalize_datetime(last_run_at)
            cron_job.next_run_at = cls._normalize_datetime(next_run_at)
            session.commit()

    @classmethod
    def compute_next_run(cls, schedule: str, timezone_name: str) -> datetime.datetime | None:
        timezone = ZoneInfo(timezone_name)
        now = datetime.datetime.now(timezone)
        trigger = CronTrigger.from_crontab(schedule, timezone=timezone)
        return cls._normalize_datetime(trigger.get_next_fire_time(None, now))

    @classmethod
    def _normalize_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        name = payload.get("name") or payload.get("title")
        if not isinstance(name, str) or not name.strip():
            raise CronJobError("name is required")

        schedule = payload.get("schedule")
        if not isinstance(schedule, str) or not schedule.strip():
            raise CronJobError("schedule is required")

        timezone_name = payload.get("timezone") or "UTC"
        try:
            ZoneInfo(timezone_name)
        except Exception as exc:
            raise CronJobError(f"invalid timezone: {timezone_name}") from exc

        timeout_seconds = payload.get("timeout_seconds")
        if timeout_seconds is not None:
            timeout_seconds = int(timeout_seconds)
            if timeout_seconds < 1:
                raise CronJobError("timeout_seconds must be at least 1")

        cls.compute_next_run(schedule.strip(), timezone_name)
        try:
            execution = normalize_execution_payload(payload, script_prefix="cron_jobs")
        except CommandTaskError as exc:
            raise CronJobError(str(exc)) from exc

        return {
            "name": name.strip(),
            "schedule": schedule.strip(),
            "timezone": timezone_name,
            "enabled": bool(payload.get("enabled", True)),
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
    def _normalize_datetime(value: datetime.datetime | None) -> datetime.datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(datetime.UTC).replace(tzinfo=None)

    @staticmethod
    def _serialize_cron(cron_job: CronJob) -> dict[str, Any]:
        return {
            "id": cron_job.id,
            "name": cron_job.name,
            "message_id": cron_job.message_id,
            "user_id": cron_job.user_id,
            "agent_id": cron_job.agent_id,
            "session_id": cron_job.session_id,
            "schedule": cron_job.schedule,
            "timezone": cron_job.timezone,
            "enabled": cron_job.enabled,
            "execution_type": cron_job.execution_type,
            "command": cron_job.command,
            "script_path": cron_job.script_path,
            "timeout_seconds": cron_job.timeout_seconds,
            "last_task_id": cron_job.last_task_id,
            "last_run_at": cron_job.last_run_at.isoformat() if cron_job.last_run_at else None,
            "next_run_at": cron_job.next_run_at.isoformat() if cron_job.next_run_at else None,
            "created_at": cron_job.created_at.isoformat() if cron_job.created_at else None,
            "updated_at": cron_job.updated_at.isoformat() if cron_job.updated_at else None,
        }
