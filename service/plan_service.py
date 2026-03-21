import datetime
from typing import Any, Optional

from libs.context import get_current_user_id
from models import AgentPlan, AgentTodo, ConversationMessage, EventLog, get_db
from service.error.error import PlanStateError

PLAN_STATUSES = {"draft", "active", "completed", "cancelled", "archived"}
TODO_STATUSES = {"pending", "in_progress", "completed", "failed", "blocked"}


class PlanService:
    @classmethod
    def create_plan(cls, payload: dict[str, Any], message_id: Optional[str], actor: str) -> dict[str, Any]:
        context = cls._resolve_context(message_id, payload)
        title = cls._coalesce(payload, "title", "name")
        body = cls._coalesce(payload, "body", "content", default="")
        if not title:
            raise PlanStateError("title is required")
        if not body:
            raise PlanStateError("body is required")

        status = cls._normalize_plan_status(payload.get("status") or "active")
        change_reason = cls._coalesce(payload, "change_reason", "create_reason", default="plan created")

        with get_db() as session:
            plan = AgentPlan(
                agent_id=context["agent_id"],
                session_id=context["session_id"],
                user_id=context["user_id"],
                title=title,
                body=body,
                status=status,
                change_log=[
                    cls._build_change_log(
                        actor=actor,
                        reason=change_reason,
                        fields=["title", "body", "status"],
                    )
                ],
            )
            session.add(plan)
            session.flush()
            cls._append_event(
                session=session,
                event_type="plan_created",
                actor=actor,
                target_id=str(plan.id),
                session_id=context["session_id"],
                request_id=message_id,
                payload={"title": plan.title, "status": plan.status},
            )
            session.commit()
            session.refresh(plan)
            return cls._serialize_plan(plan)

    @classmethod
    def update_plan(cls, payload: dict[str, Any], message_id: Optional[str], actor: str) -> dict[str, Any]:
        context = cls._resolve_context(message_id, payload)
        plan_id = payload.get("plan_id") or payload.get("id")
        title_lookup = cls._coalesce(payload, "title", "name")
        change_reason = cls._coalesce(payload, "change_reason")
        if not change_reason:
            raise PlanStateError("change_reason is required")

        with get_db() as session:
            plan = cls._find_plan(session, plan_id=plan_id, title=title_lookup, context=context)
            changed_fields: list[str] = []

            for field, value in cls._plan_update_fields(payload).items():
                if value is None:
                    continue
                setattr(plan, field, value)
                changed_fields.append(field)

            if not changed_fields:
                raise PlanStateError("no supported plan fields were provided to update")

            plan.change_log = list(plan.change_log or []) + [
                cls._build_change_log(actor=actor, reason=change_reason, fields=changed_fields)
            ]
            cls._append_event(
                session=session,
                event_type="plan_updated",
                actor=actor,
                target_id=str(plan.id),
                session_id=context["session_id"] or plan.session_id,
                request_id=message_id,
                payload={"changed_fields": changed_fields, "change_reason": change_reason},
            )
            session.commit()
            session.refresh(plan)
            return cls._serialize_plan(plan)

    @classmethod
    def list_plans(cls, payload: dict[str, Any], message_id: Optional[str]) -> list[dict[str, Any]]:
        context = cls._resolve_context(message_id, payload)
        include_archived = bool(payload.get("include_archived", False))
        status = payload.get("status")
        title_contains = payload.get("title_contains")
        include_body = bool(payload.get("include_body", False))

        with get_db() as session:
            query = session.query(AgentPlan)
            if context["agent_id"] is not None:
                query = query.filter(AgentPlan.agent_id == context["agent_id"])
            if context["session_id"] is not None:
                query = query.filter(AgentPlan.session_id == context["session_id"])
            if context["user_id"]:
                query = query.filter(AgentPlan.user_id == context["user_id"])
            if status:
                query = query.filter(AgentPlan.status == cls._normalize_plan_status(status))
            elif not include_archived:
                query = query.filter(AgentPlan.status != "archived")
            if title_contains:
                query = query.filter(AgentPlan.title.ilike(f"%{title_contains}%"))

            rows = query.order_by(AgentPlan.updated_at.desc(), AgentPlan.id.desc()).all()
            return [cls._serialize_plan(row, include_body=include_body) for row in rows]

    @classmethod
    def delete_plan(cls, payload: dict[str, Any], message_id: Optional[str], actor: str) -> dict[str, Any]:
        context = cls._resolve_context(message_id, payload)
        plan_id = payload.get("plan_id") or payload.get("id")
        title_lookup = cls._coalesce(payload, "title", "name")
        deletion_reason = cls._coalesce(payload, "deletion_reason")
        if not deletion_reason:
            raise PlanStateError("deletion_reason is required")

        with get_db() as session:
            plan = cls._find_plan(session, plan_id=plan_id, title=title_lookup, context=context)
            summary = cls._serialize_plan(plan, include_body=False)
            cls._append_event(
                session=session,
                event_type="plan_deleted",
                actor=actor,
                target_id=str(plan.id),
                session_id=context["session_id"] or plan.session_id,
                request_id=message_id,
                payload={"deletion_reason": deletion_reason, "title": plan.title},
            )
            session.delete(plan)
            session.commit()
            return {"deleted": True, "deletion_reason": deletion_reason, "plan": summary}

    @classmethod
    def add_todo(cls, payload: dict[str, Any], message_id: Optional[str], actor: str) -> dict[str, Any]:
        context = cls._resolve_context(message_id, payload)
        title = cls._coalesce(payload, "title", "subject")
        if not title:
            raise PlanStateError("title is required")

        status = cls._normalize_todo_status(payload.get("status") or "pending")
        depends_on = cls._normalize_int_list(payload.get("depends_on"))
        evidence = cls._normalize_json_list(payload.get("evidence"), allow_none=True)

        cls._validate_todo_transition_inputs(
            status=status,
            evidence=evidence,
            failure_reason=payload.get("failure_reason"),
            failure_evidence=payload.get("failure_evidence"),
            blocked_reason=payload.get("blocked_reason"),
        )

        with get_db() as session:
            cls._ensure_in_progress_limit(session, context=context, next_status=status)
            todo = AgentTodo(
                agent_id=context["agent_id"],
                session_id=context["session_id"],
                user_id=context["user_id"],
                title=title,
                status=status,
                completion_condition=payload.get("completion_condition"),
                blocked_reason=payload.get("blocked_reason"),
                failure_reason=payload.get("failure_reason"),
                failure_evidence=payload.get("failure_evidence"),
                depends_on=depends_on,
                evidence=evidence,
                change_log=[
                    cls._build_change_log(
                        actor=actor,
                        reason=cls._coalesce(payload, "change_reason", "create_reason", default="todo created"),
                        fields=[
                            "title",
                            "status",
                            "completion_condition",
                            "depends_on",
                        ],
                    )
                ],
            )
            session.add(todo)
            session.flush()
            cls._append_event(
                session=session,
                event_type="todo_created",
                actor=actor,
                target_id=str(todo.id),
                session_id=context["session_id"],
                request_id=message_id,
                payload={"title": todo.title, "status": todo.status},
            )
            session.commit()
            session.refresh(todo)
            return cls._serialize_todo(todo)

    @classmethod
    def update_todo(cls, payload: dict[str, Any], message_id: Optional[str], actor: str) -> dict[str, Any]:
        context = cls._resolve_context(message_id, payload)
        todo_id = payload.get("todo_id") or payload.get("id")
        if todo_id is None:
            raise PlanStateError("todo_id is required")

        status = payload.get("status")
        normalized_status = cls._normalize_todo_status(status) if status is not None else None
        change_reason = cls._coalesce(payload, "change_reason", default=f"todo {todo_id} updated")
        evidence = cls._normalize_json_list(payload.get("evidence"), allow_none=True)

        cls._validate_todo_transition_inputs(
            status=normalized_status,
            evidence=evidence,
            failure_reason=payload.get("failure_reason"),
            failure_evidence=payload.get("failure_evidence"),
            blocked_reason=payload.get("blocked_reason"),
        )

        with get_db() as session:
            todo = cls._find_todo(session, todo_id=int(todo_id), context=context)
            cls._ensure_in_progress_limit(
                session=session,
                context=context,
                next_status=normalized_status,
                current_todo=todo,
            )

            changed_fields: list[str] = []
            updates = cls._todo_update_fields(payload, normalized_status, evidence)
            for field, value in updates.items():
                if value is None:
                    continue
                setattr(todo, field, value)
                changed_fields.append(field)

            if not changed_fields:
                raise PlanStateError("no supported todo fields were provided to update")

            todo.change_log = list(todo.change_log or []) + [
                cls._build_change_log(actor=actor, reason=change_reason, fields=changed_fields)
            ]
            cls._append_event(
                session=session,
                event_type="todo_updated",
                actor=actor,
                target_id=str(todo.id),
                session_id=context["session_id"] or todo.session_id,
                request_id=message_id,
                payload={"changed_fields": changed_fields, "change_reason": change_reason},
            )
            session.commit()
            session.refresh(todo)
            return cls._serialize_todo(todo)

    @classmethod
    def list_todos(cls, payload: dict[str, Any], message_id: Optional[str]) -> list[dict[str, Any]]:
        context = cls._resolve_context(message_id, payload)
        status = payload.get("status")

        with get_db() as session:
            query = session.query(AgentTodo)
            if context["agent_id"] is not None:
                query = query.filter(AgentTodo.agent_id == context["agent_id"])
            if context["session_id"] is not None:
                query = query.filter(AgentTodo.session_id == context["session_id"])
            if context["user_id"]:
                query = query.filter(AgentTodo.user_id == context["user_id"])
            if status:
                query = query.filter(AgentTodo.status == cls._normalize_todo_status(status))

            rows = query.order_by(AgentTodo.created_at.asc(), AgentTodo.id.asc()).all()
            return [cls._serialize_todo(row) for row in rows]

    @classmethod
    def delete_todo(cls, payload: dict[str, Any], message_id: Optional[str], actor: str) -> dict[str, Any]:
        context = cls._resolve_context(message_id, payload)
        todo_id = payload.get("todo_id") or payload.get("id")
        deletion_reason = cls._coalesce(payload, "deletion_reason")
        if todo_id is None:
            raise PlanStateError("todo_id is required")
        if not deletion_reason:
            raise PlanStateError("deletion_reason is required")

        with get_db() as session:
            todo = cls._find_todo(session, todo_id=int(todo_id), context=context)
            summary = cls._serialize_todo(todo)
            cls._append_event(
                session=session,
                event_type="todo_deleted",
                actor=actor,
                target_id=str(todo.id),
                session_id=context["session_id"] or todo.session_id,
                request_id=message_id,
                payload={"deletion_reason": deletion_reason, "title": todo.title},
            )
            session.delete(todo)
            session.commit()
            return {"deleted": True, "deletion_reason": deletion_reason, "todo": summary}

    @classmethod
    def _resolve_context(cls, message_id: Optional[str], payload: dict[str, Any]) -> dict[str, Any]:
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
    def _append_event(
        *,
        session,
        event_type: str,
        actor: str,
        target_id: str,
        session_id: Optional[int],
        request_id: Optional[str],
        payload: dict[str, Any],
    ) -> None:
        session.add(
            EventLog(
                session_id=str(session_id) if session_id is not None else None,
                request_id=request_id,
                event_type=event_type,
                actor=actor,
                target_id=target_id,
                payload=payload,
            )
        )

    @staticmethod
    def _build_change_log(*, actor: str, reason: str, fields: list[str]) -> dict[str, Any]:
        return {
            "changed_at": datetime.datetime.now().isoformat(),
            "actor": actor,
            "reason": reason,
            "fields": fields,
        }

    @classmethod
    def _find_plan(cls, session, *, plan_id: Any, title: Optional[str], context: dict[str, Any]) -> AgentPlan:
        query = session.query(AgentPlan)
        if context["agent_id"] is not None:
            query = query.filter(AgentPlan.agent_id == context["agent_id"])
        if context["session_id"] is not None:
            query = query.filter(AgentPlan.session_id == context["session_id"])
        if context["user_id"]:
            query = query.filter(AgentPlan.user_id == context["user_id"])

        plan = None
        if plan_id is not None:
            plan = query.filter(AgentPlan.id == int(plan_id)).first()
        elif title:
            plan = query.filter(AgentPlan.title == title).order_by(AgentPlan.updated_at.desc()).first()
        if not plan:
            raise PlanStateError("plan not found")
        return plan

    @classmethod
    def _find_todo(cls, session, *, todo_id: int, context: dict[str, Any]) -> AgentTodo:
        query = session.query(AgentTodo).filter(AgentTodo.id == todo_id)
        if context["agent_id"] is not None:
            query = query.filter(AgentTodo.agent_id == context["agent_id"])
        if context["session_id"] is not None:
            query = query.filter(AgentTodo.session_id == context["session_id"])
        if context["user_id"]:
            query = query.filter(AgentTodo.user_id == context["user_id"])
        todo = query.first()
        if not todo:
            raise PlanStateError("todo not found")
        return todo

    @classmethod
    def _ensure_in_progress_limit(
        cls,
        *,
        session,
        context: dict[str, Any],
        next_status: Optional[str],
        current_todo: Optional[AgentTodo] = None,
    ) -> None:
        if next_status != "in_progress":
            return
        if current_todo is not None and current_todo.status == "in_progress":
            return

        query = session.query(AgentTodo).filter(AgentTodo.status == "in_progress")
        if context["agent_id"] is not None:
            query = query.filter(AgentTodo.agent_id == context["agent_id"])
        if context["session_id"] is not None:
            query = query.filter(AgentTodo.session_id == context["session_id"])
        if context["user_id"]:
            query = query.filter(AgentTodo.user_id == context["user_id"])
        if query.count() >= 3:
            raise PlanStateError("at most 3 todos may be in_progress at the same time")

    @classmethod
    def _validate_todo_transition_inputs(
        cls,
        *,
        status: Optional[str],
        evidence: Any,
        failure_reason: Any,
        failure_evidence: Any,
        blocked_reason: Any,
    ) -> None:
        _ = failure_evidence
        if status == "completed" and not evidence:
            raise PlanStateError("evidence is required when marking a todo completed")
        if status == "failed" and not failure_reason:
            raise PlanStateError("failure_reason is required when marking a todo failed")
        if status == "blocked" and not blocked_reason:
            raise PlanStateError("blocked_reason is required when marking a todo blocked")

    @classmethod
    def _plan_update_fields(cls, payload: dict[str, Any]) -> dict[str, Any]:
        fields = {
            "title": cls._coalesce(payload, "title", "name"),
            "body": cls._coalesce(payload, "body", "content"),
            "status": cls._normalize_plan_status(payload["status"]) if payload.get("status") is not None else None,
        }
        return fields

    @classmethod
    def _todo_update_fields(
        cls,
        payload: dict[str, Any],
        normalized_status: Optional[str],
        evidence: Any,
    ) -> dict[str, Any]:
        fields = {
            "title": cls._coalesce(payload, "title", "subject"),
            "status": normalized_status,
            "completion_condition": payload.get("completion_condition"),
            "blocked_reason": payload.get("blocked_reason"),
            "failure_reason": payload.get("failure_reason"),
            "failure_evidence": payload.get("failure_evidence"),
            "depends_on": cls._normalize_int_list(payload["depends_on"]) if "depends_on" in payload else None,
            "evidence": evidence,
        }
        return fields

    @staticmethod
    def _serialize_plan(plan: AgentPlan, *, include_body: bool = True) -> dict[str, Any]:
        data = {
            "id": plan.id,
            "agent_id": plan.agent_id,
            "session_id": plan.session_id,
            "user_id": plan.user_id,
            "title": plan.title,
            "status": plan.status,
            "change_log": plan.change_log or [],
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        }
        if include_body:
            data["body"] = plan.body
        return data

    @staticmethod
    def _serialize_todo(todo: AgentTodo) -> dict[str, Any]:
        return {
            "id": todo.id,
            "agent_id": todo.agent_id,
            "session_id": todo.session_id,
            "user_id": todo.user_id,
            "title": todo.title,
            "status": todo.status,
            "completion_condition": todo.completion_condition,
            "blocked_reason": todo.blocked_reason,
            "failure_reason": todo.failure_reason,
            "depends_on": todo.depends_on or [],
            "evidence": todo.evidence,
            "change_log": todo.change_log or [],
            "created_at": todo.created_at.isoformat() if todo.created_at else None,
            "updated_at": todo.updated_at.isoformat() if todo.updated_at else None,
        }

    @staticmethod
    def _coalesce(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
        for key in keys:
            value = payload.get(key)
            if value is not None:
                return value
        return default

    @staticmethod
    def _normalize_plan_status(value: Any) -> str:
        status = str(value).strip().lower()
        if status not in PLAN_STATUSES:
            raise PlanStateError(f"invalid plan status: {value}")
        return status

    @staticmethod
    def _normalize_todo_status(value: Any) -> str:
        status = str(value).strip().lower()
        if status not in TODO_STATUSES:
            raise PlanStateError(f"invalid todo status: {value}")
        return status

    @staticmethod
    def _normalize_optional_int(value: Any) -> Optional[int]:
        if value in (None, ""):
            return None
        return int(value)

    @staticmethod
    def _normalize_text_list(value: Any) -> list[str]:
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise PlanStateError("expected a list of strings")
        return [str(item) for item in value]

    @staticmethod
    def _normalize_json_list(value: Any, *, allow_none: bool = False) -> Optional[list[Any]]:
        if value is None:
            return None if allow_none else []
        if value == "":
            return [] if not allow_none else None
        if not isinstance(value, list):
            raise PlanStateError("expected a list")
        return value

    @staticmethod
    def _normalize_int_list(value: Any) -> list[int]:
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise PlanStateError("depends_on must be a list")
        return [int(item) for item in value]
