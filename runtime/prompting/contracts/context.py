from __future__ import annotations

from pydantic import BaseModel, Field

from runtime.prompting.contracts.base import PromptMode, PromptPhase, RequestFamily


class TrackedDocument(BaseModel):
    document_id: str
    path: str
    role: str
    summary: str | None = None


class FocusSpan(BaseModel):
    document_id: str
    start: int | None = None
    end: int | None = None
    label: str | None = None


class OperationState(BaseModel):
    operation_id: str
    operation_type: str
    status: str
    summary: str


class RuntimeCapabilities(BaseModel):
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list)
    subagent_types: list[str] = Field(default_factory=list)


class PromptContext(BaseModel):
    mode: PromptMode
    phase: PromptPhase
    request_family: RequestFamily
    user_id: str | None = None
    session_id: str | int | None = None
    workspace_id: str | None = None
    profile_id: str | None = None
    current_date: str
    latest_user_text: str = ""
    language: str | None = None
    output_style: str | None = None
    tracked_documents: list[TrackedDocument] = Field(default_factory=list)
    active_focus_spans: list[FocusSpan] = Field(default_factory=list)
    pending_operations: list[OperationState] = Field(default_factory=list)
    applied_operations: list[OperationState] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    runtime_capabilities: RuntimeCapabilities = Field(default_factory=RuntimeCapabilities)
    permission_mode: str | None = None
    session_goal: str | None = None
    turn_goal: str | None = None
    recent_decisions: list[str] = Field(default_factory=list)
    extra: dict[str, object] = Field(default_factory=dict)
