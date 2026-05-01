from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from models.agent import Agent, AgentSession


class RuntimeModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid", use_enum_values=True)


class ResolvedAgentSession(RuntimeModel):
    agent: Agent
    session: AgentSession
    user_id: str | None = None
    mode: str
    surface: str


class AgentSessionState(RuntimeModel):
    turn_count: int = 0
    last_trace_id: str | None = None
    session_goal: str | None = None
    recent_decisions: list[str] = Field(default_factory=list)
    pending_client_actions: list[dict[str, Any]] = Field(default_factory=list)
    memory_state: dict[str, Any] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)
