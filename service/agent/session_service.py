from __future__ import annotations

from runtime.agent.session_runtime import AgentSessionRuntime
from service.agent.contracts import AgentSessionCreateCommand, AgentSessionResult, AgentSessionUpdateCommand


class AgentSessionService:
    @classmethod
    async def create_session(cls, payload: AgentSessionCreateCommand) -> AgentSessionResult:
        agent = AgentSessionRuntime.resolve_agent(payload.agent_id)
        resolved = AgentSessionRuntime.create_session(
            agent=agent,
            mode=payload.mode,
            surface=payload.surface,
            title=payload.title,
            description=payload.description,
        )
        return AgentSessionResult(
            session_id=resolved.session.id,
            agent_id=resolved.agent.id,
            user_id=resolved.user_id,
            mode=payload.mode,
            surface=payload.surface,
            title=resolved.session.name,
            description=resolved.session.description,
            status=resolved.session.status,
        )

    @classmethod
    async def update_title(cls, session_id: int, payload: AgentSessionUpdateCommand) -> AgentSessionResult:
        session = AgentSessionRuntime.update_title(session_id, payload.title)
        agent = AgentSessionRuntime.resolve_agent(session.agent_id)
        return AgentSessionResult(
            session_id=session.id,
            agent_id=agent.id,
            user_id=session.user_id,
            mode="agent",
            surface="web",
            title=session.name,
            description=session.description,
            status=session.status,
        )

    @classmethod
    async def delete_session(cls, session_id: int) -> AgentSessionResult:
        session = AgentSessionRuntime.delete_session(session_id)
        agent = AgentSessionRuntime.resolve_agent(session.agent_id)
        return AgentSessionResult(
            session_id=session.id,
            agent_id=agent.id,
            user_id=session.user_id,
            mode="agent",
            surface="web",
            title=session.name,
            description=session.description,
            status=session.status,
        )
