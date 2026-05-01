from __future__ import annotations

import json

from models import get_db
from models.agent import AgentSession
from runtime.agent.session_types import AgentSessionState
from service.agent.errors import AgentSessionNotFoundError


class AgentSessionStateStore:
    @classmethod
    def load(cls, session_id: int) -> AgentSessionState:
        with get_db() as session:
            entity = (
                session.query(AgentSession)
                .filter(AgentSession.id == session_id, AgentSession.deleted == 0)
                .first()
            )
            if entity is None:
                raise AgentSessionNotFoundError("agent session not found")
            raw = str(entity.context or "").strip()
        if not raw:
            return AgentSessionState()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        return AgentSessionState.model_validate(data)

    @classmethod
    def save(cls, session_id: int, state: AgentSessionState) -> AgentSessionState:
        with get_db() as session:
            entity = (
                session.query(AgentSession)
                .filter(AgentSession.id == session_id, AgentSession.deleted == 0)
                .first()
            )
            if entity is None:
                raise AgentSessionNotFoundError("agent session not found")
            entity.context = json.dumps(state.model_dump(mode="python", exclude_none=True), ensure_ascii=False)
            session.commit()
        return state

    @classmethod
    def patch(cls, session_id: int, delta: dict[str, object]) -> AgentSessionState:
        state = cls.load(session_id)
        next_state = state.model_copy(update=delta)
        return cls.save(session_id, next_state)
