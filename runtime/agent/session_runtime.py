from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import TypeAdapter

from libs.context import get_current_user_id
from models import Agent, ConversationMessage, get_db
from models.agent import AgentSession
from runtime.agent.adapters.response_text_extractor import ResponseTextExtractor
from runtime.agent.session_state_store import AgentSessionStateStore
from runtime.agent.session_types import AgentSessionState, ResolvedAgentSession
from runtime.entities.anthropic_entities import AnthropicContentBlock, AnthropicMessage
from service import ConversationMessageService
from service.agent.errors import (
    AgentAccessDeniedError,
    AgentNotFoundError,
    AgentSessionConflictError,
    AgentSessionNotFoundError,
)
from service.memory.repository.session_message_repository import SessionMessageRepository

BLOCKS_ADAPTER = TypeAdapter(list[AnthropicContentBlock])
SUPERVISOR_AGENT_NAME = "supervisor_agent_v3"


class AgentSessionRuntime:
    @classmethod
    def resolve_agent(cls, agent_id: int | None) -> Agent:
        with get_db() as session:
            query = session.query(Agent).filter(Agent.deleted == 0)
            if agent_id is not None:
                entity = query.filter(Agent.id == agent_id).first()
            else:
                entity = query.filter(Agent.name == SUPERVISOR_AGENT_NAME).first()
            if entity is None:
                raise AgentNotFoundError("agent not found")
            cls._ensure_agent_owner(entity)
            return entity

    @classmethod
    def get_or_create_session(
        cls,
        *,
        agent: Agent,
        session_id: int | None,
        mode: str,
        surface: str,
        title: str | None = None,
        description: str | None = None,
    ) -> ResolvedAgentSession:
        if session_id is not None:
            return cls.bind_existing_session(agent=agent, session_id=session_id, mode=mode, surface=surface)
        return cls.create_session(agent=agent, mode=mode, surface=surface, title=title, description=description)

    @classmethod
    def create_session(
        cls,
        *,
        agent: Agent,
        mode: str,
        surface: str,
        title: str | None = None,
        description: str | None = None,
    ) -> ResolvedAgentSession:
        user_id = cls.current_user_id()
        with get_db() as session:
            entity = AgentSession(
                agent_id=agent.id,
                user_id=user_id,
                name=(title or "").strip() or None,
                description=(description or "").strip() or "",
                status="active",
                context=json.dumps({"mode": mode, "surface": surface}, ensure_ascii=False),
            )
            session.add(entity)
            session.commit()
            session.refresh(entity)
        AgentSessionStateStore.save(entity.id, AgentSessionState(extra={"mode": mode, "surface": surface}))
        return ResolvedAgentSession(agent=agent, session=entity, user_id=user_id, mode=mode, surface=surface)

    @classmethod
    def bind_existing_session(cls, *, agent: Agent, session_id: int, mode: str, surface: str) -> ResolvedAgentSession:
        with get_db() as session:
            entity = (
                session.query(AgentSession)
                .filter(AgentSession.id == session_id, AgentSession.deleted == 0)
                .first()
            )
            if entity is None:
                raise AgentSessionNotFoundError("agent session not found")
            if entity.agent_id != agent.id:
                raise AgentSessionConflictError("agent session does not belong to the selected agent")
            cls._ensure_session_owner(entity)
            return ResolvedAgentSession(
                agent=agent,
                session=entity,
                user_id=entity.user_id,
                mode=mode,
                surface=surface,
            )

    @classmethod
    def load_history_as_anthropic_messages(
        cls,
        *,
        session_id: int,
        user_id: str | None,
        agent_id: int,
    ) -> list[AnthropicMessage]:
        rows = SessionMessageRepository.list_session_messages(
            agent_session_id=session_id,
            user_id=str(user_id or ""),
            agent_id=str(agent_id),
        )
        history: list[AnthropicMessage] = []
        for row in rows:
            role = str(row.get("role") or "assistant")
            content = cls._restore_content(row.get("content"))
            history.append(AnthropicMessage(role="assistant" if role == "assistant" else "user", content=content))
        return history

    @classmethod
    def update_title(cls, session_id: int, title: str) -> AgentSession:
        with get_db() as session:
            entity = (
                session.query(AgentSession)
                .filter(AgentSession.id == session_id, AgentSession.deleted == 0)
                .first()
            )
            if entity is None:
                raise AgentSessionNotFoundError("agent session not found")
            cls._ensure_session_owner(entity)
            entity.name = title
            entity.updated_at = datetime.now()
            session.commit()
            session.refresh(entity)
            return entity

    @classmethod
    def delete_session(cls, session_id: int) -> AgentSession:
        with get_db() as session:
            entity = (
                session.query(AgentSession)
                .filter(AgentSession.id == session_id, AgentSession.deleted == 0)
                .first()
            )
            if entity is None:
                raise AgentSessionNotFoundError("agent session not found")
            cls._ensure_session_owner(entity)
            entity.deleted = 1
            entity.status = "deleted"
            entity.updated_at = datetime.now()
            session.commit()
            session.refresh(entity)
            return entity

    @classmethod
    def persist_input_turn(
        cls,
        *,
        session_id: int,
        agent_id: int,
        user_id: str | None,
        model_name: str,
        provider_name: str,
        message: AnthropicMessage,
        system_prompt: str | None = None,
    ) -> None:
        conversation_message = ConversationMessage(
            message_id=f"input-{uuid4().hex}",
            model_name=model_name,
            provider_name=provider_name,
            role="tool" if cls._contains_tool_result(message) else message.role,
            content=cls._serialize_content(message.content),
            system_prompt=system_prompt or "",
            user_id=str(user_id or "") or None,
            agent_id=agent_id,
            agent_session_id=session_id,
            state="success",
        )
        ConversationMessageService.add_conversation_message(conversation_message)

    @classmethod
    def persist_assistant_turn(
        cls,
        *,
        session_id: int,
        agent_id: int,
        user_id: str | None,
        model_name: str,
        provider_name: str,
        response,
        system_prompt: str | None = None,
    ) -> None:
        content = getattr(response, "content", None)
        message_id = str(getattr(response, "id", "") or f"assistant-{uuid4().hex}")
        conversation_message = ConversationMessage(
            message_id=message_id,
            model_name=model_name,
            provider_name=provider_name,
            role="assistant",
            content=cls._serialize_content(content),
            system_prompt=system_prompt or "",
            user_id=str(user_id or "") or None,
            agent_id=agent_id,
            agent_session_id=session_id,
            state="success",
        )
        ConversationMessageService.add_conversation_message(conversation_message)

    @classmethod
    def current_user_id(cls) -> str | None:
        value = get_current_user_id()
        return str(value) if value is not None else None

    @classmethod
    def _ensure_agent_owner(cls, agent: Agent) -> None:
        current_user_id = cls.current_user_id()
        owner = str(getattr(agent, "user_id", "") or "").strip()
        if owner and current_user_id and owner != current_user_id:
            raise AgentAccessDeniedError("agent does not belong to the current user")

    @classmethod
    def _ensure_session_owner(cls, session: AgentSession) -> None:
        current_user_id = cls.current_user_id()
        owner = str(getattr(session, "user_id", "") or "").strip()
        if owner and current_user_id and owner != current_user_id:
            raise AgentAccessDeniedError("agent session does not belong to the current user")

    @staticmethod
    def _contains_tool_result(message: AnthropicMessage) -> bool:
        content = message.content
        if isinstance(content, list):
            return any(getattr(item, "type", None) == "tool_result" for item in content)
        return False

    @classmethod
    def _serialize_content(cls, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            payload = {"kind": "anthropic_blocks", "blocks": [cls._dump_block(item) for item in content]}
            return json.dumps(payload, ensure_ascii=False)
        return ResponseTextExtractor.flatten_content(content)

    @staticmethod
    def _dump_block(item: Any) -> dict[str, Any]:
        if hasattr(item, "model_dump"):
            return item.model_dump(mode="python", exclude_none=True)
        if isinstance(item, dict):
            return dict(item)
        return {"type": "text", "text": ResponseTextExtractor.flatten_content(item)}

    @classmethod
    def _restore_content(cls, value: Any) -> str | list[AnthropicContentBlock]:
        text = str(value or "")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return text
        if isinstance(payload, dict) and payload.get("kind") == "anthropic_blocks":
            blocks = payload.get("blocks") or []
            try:
                return BLOCKS_ADAPTER.validate_python(blocks)
            except Exception:
                return text
        return text
