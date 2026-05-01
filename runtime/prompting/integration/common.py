from __future__ import annotations

from datetime import date

from models import Agent
from runtime.agent.adapters.request_adapter import RequestAdapter
from runtime.agent.agent_type import AgentExecutionContext
from runtime.entities import AnthropicMessageRequest, ChatCompletionRequest, LLMRequest, ResponseRequest
from runtime.prompting.compiler.prompt_compiler import PromptCompiler
from runtime.prompting.contracts.compiled import CompiledPrompt
from runtime.prompting.contracts.context import PromptContext, RuntimeCapabilities
from runtime.prompting.contracts.trace import PromptTrace
from runtime.tool.base.tool import Tool


def request_family_for(request: LLMRequest) -> str:
    if isinstance(request, ChatCompletionRequest):
        return "openai_chat"
    if isinstance(request, AnthropicMessageRequest):
        return "anthropic_messages"
    if isinstance(request, ResponseRequest):
        return "openai_responses"
    raise TypeError(f"Unsupported request type for prompt compilation: {type(request)!r}")


def build_prompt_context(
    *,
    mode: str,
    phase: str,
    request: LLMRequest,
    agent: Agent | None = None,
    ctx: AgentExecutionContext | None = None,
    tools: list[Tool] | None = None,
    session_state: dict[str, object] | None = None,
    extras: dict[str, object] | None = None,
) -> PromptContext:
    session_state = session_state or {}
    extras = extras or {}
    tool_names = [tool.entity.name for tool in (tools or []) if getattr(tool, "entity", None) is not None]
    capabilities = RuntimeCapabilities(
        tools=tool_names,
        skills=list(extras.get("skills", session_state.get("skills", []))),
        mcp_servers=list(extras.get("mcp_servers", session_state.get("mcp_servers", []))),
        subagent_types=list(extras.get("subagent_types", session_state.get("subagent_types", []))),
    )
    merged_extra = {**session_state.get("extra", {}), **extras}
    merged_extra.setdefault(
        "env_info",
        {
            "cwd": merged_extra.get("cwd"),
            "platform": merged_extra.get("platform"),
            "shell": merged_extra.get("shell"),
        },
    )
    return PromptContext(
        mode=mode,
        phase=phase,
        request_family=request_family_for(request),
        user_id=str(getattr(ctx, "user_id", None) or getattr(agent, "user_id", None) or "") or None,
        session_id=getattr(ctx, "session_id", None),
        workspace_id=str(merged_extra.get("workspace_id") or "") or None,
        profile_id=str(merged_extra.get("profile_id") or f"default_{mode}"),
        current_date=str(merged_extra.get("current_date") or date.today().isoformat()),
        latest_user_text=RequestAdapter(request).latest_user_text(),
        language=str(merged_extra.get("language") or "") or None,
        output_style=str(merged_extra.get("output_style") or "") or None,
        tracked_documents=list(session_state.get("tracked_documents", [])),
        active_focus_spans=list(session_state.get("active_focus_spans", [])),
        pending_operations=list(session_state.get("pending_operations", [])),
        applied_operations=list(session_state.get("applied_operations", [])),
        artifact_refs=list(session_state.get("artifact_refs", [])),
        runtime_capabilities=capabilities,
        permission_mode=str(merged_extra.get("permission_mode") or "") or None,
        session_goal=str(merged_extra.get("session_goal") or "") or None,
        turn_goal=str(merged_extra.get("turn_goal") or "") or None,
        recent_decisions=list(session_state.get("recent_decisions", [])),
        extra={
            **merged_extra,
            "agent_name": getattr(agent, "name", None),
            "prompt_template": getattr(agent, "prompt_template", None),
            "token_budget": merged_extra.get("token_budget")
            or (getattr(agent, "agent_parameters", {}) or {}).get("thinking_budget"),
        },
    )


def compile_prompt(
    *,
    mode: str,
    phase: str,
    request: LLMRequest,
    agent: Agent | None = None,
    ctx: AgentExecutionContext | None = None,
    tools: list[Tool] | None = None,
    session_state: dict[str, object] | None = None,
    extras: dict[str, object] | None = None,
) -> tuple[CompiledPrompt, PromptTrace]:
    prompt_context = build_prompt_context(
        mode=mode,
        phase=phase,
        request=request,
        agent=agent,
        ctx=ctx,
        tools=tools,
        session_state=session_state,
        extras=extras,
    )
    return PromptCompiler().compile(prompt_context)
