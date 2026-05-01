from models import Agent
from runtime.agent.agent_type import AgentExecutionContext
from runtime.entities.llm_entities import LLMRequest
from runtime.prompting.contracts.compiled import CompiledPrompt
from runtime.prompting.contracts.trace import PromptTrace
from runtime.prompting.integration.common import compile_prompt
from runtime.tool.base.tool import Tool


def build_agent_first_turn(
    *,
    request: LLMRequest,
    agent: Agent,
    ctx: AgentExecutionContext,
    tools: list[Tool] | None = None,
    session_state: dict[str, object] | None = None,
    extras: dict[str, object] | None = None,
) -> tuple[CompiledPrompt, PromptTrace]:
    return compile_prompt(
        mode="agent",
        phase="first_turn",
        request=request,
        agent=agent,
        ctx=ctx,
        tools=tools,
        session_state=session_state,
        extras=extras,
    )


def build_agent_continued_turn(
    *,
    request: LLMRequest,
    agent: Agent,
    ctx: AgentExecutionContext,
    tools: list[Tool] | None = None,
    session_state: dict[str, object] | None = None,
    extras: dict[str, object] | None = None,
) -> tuple[CompiledPrompt, PromptTrace]:
    return compile_prompt(
        mode="agent",
        phase="continued_turn",
        request=request,
        agent=agent,
        ctx=ctx,
        tools=tools,
        session_state=session_state,
        extras=extras,
    )
