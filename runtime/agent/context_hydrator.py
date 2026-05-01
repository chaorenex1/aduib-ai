from __future__ import annotations

from datetime import date

from runtime.agent.memory_retrieval_service import MemoryRetrievalService
from runtime.agent.session_state_store import AgentSessionStateStore
from runtime.entities.anthropic_entities import AnthropicMessageRequest
from runtime.prompting.adapters import AnthropicMessagesPromptAdapter
from runtime.prompting.integration.build_for_agent import build_agent_continued_turn, build_agent_first_turn
from runtime.prompting.integration.build_for_chat import build_chat_continued_turn, build_chat_first_turn
from service.agent.contracts import AgentCompressionState, AgentMemoryState


class ContextHydrator:
    @classmethod
    async def hydrate(
        cls,
        *,
        agent,
        session_id: int,
        user_id: str | None,
        mode: str,
        surface: str,
        request: AnthropicMessageRequest,
        tools,
        permission,
    ) -> tuple[AnthropicMessageRequest, dict[str, object], AgentCompressionState, AgentMemoryState]:
        session_state = AgentSessionStateStore.load(session_id)
        latest_user_text = ""
        if request.messages:
            last_message = request.messages[-1]
            if isinstance(last_message.content, str):
                latest_user_text = last_message.content

        memory_state = AgentMemoryState()
        memory_attachment = None
        if getattr(agent, "enabled_memory", 0) == 1 and user_id:
            memory_attachment, strategy = await MemoryRetrievalService.retrieve_for_turn(
                mode=mode,
                user_id=str(user_id),
                latest_user_text=latest_user_text,
                session_messages=request.messages,
            )
            memory_state.retrieval_strategy = strategy

        extras = {
            "current_date": date.today().isoformat(),
            "turn_goal": latest_user_text or None,
            "session_goal": session_state.session_goal,
            "permission_mode": "tool_gated" if permission.allowed_tool_names else "read_only",
            "env_info": {"surface": surface},
            "session_guidance": ["Preserve the active mode contract and use tools only when allowed."],
            "summarize_tool_results": True,
            "memory_attachment": memory_attachment,
            "execution_topology": f"{mode}:{surface}",
            "subagent_types": list(session_state.extra.get("subagent_types", [])),
        }

        if mode == "chat":
            builder = build_chat_continued_turn if session_state.turn_count else build_chat_first_turn
            compiled, trace = builder(
                request=request,
                session_state=session_state.model_dump(mode="python"),
                extras=extras,
            )
        else:
            ctx = type("HydratedCtx", (), {"user_id": user_id, "agent_id": agent.id, "session_id": session_id})()
            builder = build_agent_continued_turn if session_state.turn_count else build_agent_first_turn
            compiled, trace = builder(
                request=request,
                agent=agent,
                ctx=ctx,
                tools=tools,
                session_state=session_state.model_dump(mode="python"),
                extras=extras,
            )

        hydrated_request = AnthropicMessagesPromptAdapter().apply(request.model_copy(deep=True), compiled)
        next_state = session_state.model_copy(
            update={
                "turn_count": session_state.turn_count + 1,
                "last_trace_id": trace.trace_id,
                "session_goal": session_state.session_goal or (latest_user_text[:200] if latest_user_text else None),
                "extra": {**session_state.extra, "mode": mode, "surface": surface},
                "memory_state": memory_state.model_dump(mode="python"),
            }
        )
        AgentSessionStateStore.save(session_id, next_state)

        return hydrated_request, next_state.model_dump(mode="python"), AgentCompressionState(), memory_state
