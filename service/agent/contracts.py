from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from runtime.entities.anthropic_entities import (
    AnthropicMessage,
    AnthropicMessageRequest,
    AnthropicMessageResponse,
    AnthropicMetadata,
    AnthropicOutputConfig,
    AnthropicSystemBlock,
)
from runtime.entities.message_entities import ThinkingOptions


class AgentContract(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class AgentToolResult(AgentContract):
    tool_use_id: str = Field(..., min_length=1)
    tool_name: str = Field(..., min_length=1)
    output: str = ""
    is_error: bool = False


class AgentApprovalDecision(AgentContract):
    tool_use_id: str = Field(..., min_length=1)
    tool_name: str = Field(..., min_length=1)
    approved: bool
    reason: str | None = None


class AgentMessagesCommand(AgentContract):
    agent_id: int | None = Field(default=None, ge=1)
    session_id: int | None = Field(default=None, ge=1)
    mode: Literal["chat", "agent"] = "agent"
    surface: Literal["web", "desktop"] = "web"
    request: AnthropicMessageRequest


class AgentMessageTurnCommand(AgentContract):
    agent_id: int | None = Field(default=None, ge=1)
    session_id: int | None = Field(default=None, ge=1)
    mode: Literal["chat", "agent"] = "agent"
    surface: Literal["web", "desktop"] = "web"
    model: str = Field(..., min_length=1)
    user_text: str | None = None
    tool_results: list[AgentToolResult] = Field(default_factory=list)
    approval_decision: AgentApprovalDecision | None = None
    system: str | list[AnthropicSystemBlock] | None = None
    max_tokens: int = 4096
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    stream: bool = False
    stop_sequences: list[str] | None = None
    thinking: ThinkingOptions | None = None
    output_config: AnthropicOutputConfig | None = None
    metadata: AnthropicMetadata | None = None

    @model_validator(mode="after")
    def validate_turn_input(self) -> AgentMessageTurnCommand:
        populated = int(bool((self.user_text or "").strip())) + int(bool(self.tool_results)) + int(
            self.approval_decision is not None
        )
        if populated != 1:
            raise ValueError("exactly one of user_text, tool_results, or approval_decision is required")
        return self


class AgentSessionCreateCommand(AgentContract):
    agent_id: int | None = Field(default=None, ge=1)
    mode: Literal["chat", "agent"] = "agent"
    surface: Literal["web", "desktop"] = "web"
    title: str | None = None
    description: str | None = None


class AgentSessionUpdateCommand(AgentContract):
    title: str = Field(..., min_length=1, max_length=255)


class ToolingSchemaCommand(AgentContract):
    agent_id: int | None = Field(default=None, ge=1)
    mode: Literal["chat", "agent"] = "agent"
    surface: Literal["web", "desktop"] = "web"


class ToolingPermissionCommand(AgentContract):
    agent_id: int | None = Field(default=None, ge=1)
    mode: Literal["chat", "agent"] = "agent"
    surface: Literal["web", "desktop"] = "web"


class AgentBudgetState(AgentContract):
    input_tokens_est: int = 0
    continuation_allowed: bool = False
    continuation_count: int = 0
    target_tokens: int | None = None


class AgentCompressionState(AgentContract):
    strategy: Literal["none", "snip", "microcompact", "context_collapse", "autocompact"] = "none"
    summary_applied: bool = False
    compact_revision: int = 0


class AgentMemoryState(AgentContract):
    retrieval_strategy: Literal["none", "find", "search"] = "none"
    used_memory_ids: list[str] = Field(default_factory=list)
    writeback_scheduled: bool = False
    write_task_id: str | None = None


class AgentTurnState(AgentContract):
    phase: str
    branch: Literal["none", "completion", "tool"] = "none"
    thinking_mode: Literal["disabled", "adaptive", "enabled"] = "disabled"
    stream_mode: Literal["streaming", "non_streaming"] = "non_streaming"
    can_continue: bool = False
    budget: AgentBudgetState = Field(default_factory=AgentBudgetState)
    compression: AgentCompressionState = Field(default_factory=AgentCompressionState)
    pending_client_actions: list[dict[str, object]] = Field(default_factory=list)
    memory: AgentMemoryState = Field(default_factory=AgentMemoryState)


class AgentTurnResult(AgentContract):
    agent_id: int
    session_id: int
    mode: Literal["chat", "agent"]
    surface: Literal["web", "desktop"]
    response: AnthropicMessageResponse | None = None
    state: AgentTurnState
    client_actions: list[dict[str, object]] = Field(default_factory=list)
    tool_results: list[dict[str, object]] = Field(default_factory=list)


class AgentSessionResult(AgentContract):
    session_id: int
    agent_id: int
    user_id: str | None = None
    mode: Literal["chat", "agent"]
    surface: Literal["web", "desktop"]
    title: str | None = None
    description: str | None = None
    status: str


class ToolSchemaView(AgentContract):
    name: str
    description: str = ""
    provider: str = ""
    tool_type: str = ""
    input_schema: dict[str, object] = Field(default_factory=dict)
    execution_side: Literal["server", "client", "disabled"] = "disabled"
    requires_approval: bool = False


class ToolPermissionView(AgentContract):
    allowed_tool_names: list[str] = Field(default_factory=list)
    denied_tool_names: list[str] = Field(default_factory=list)
    approval_required_tool_names: list[str] = Field(default_factory=list)
    effective_scope: list[str] = Field(default_factory=list)
    reason: list[str] = Field(default_factory=list)


class ResolvedAgentInput(AgentContract):
    request: AnthropicMessageRequest
    latest_input: AnthropicMessage
    latest_user_text: str = ""
