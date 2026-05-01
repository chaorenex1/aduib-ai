from __future__ import annotations

from runtime.agent.client_action_broker import ClientActionBroker
from runtime.agent.context_hydrator import ContextHydrator
from runtime.agent.memory_write_coordinator import MemoryWriteCoordinator
from runtime.agent.model_facade import AgentModelFacade
from runtime.agent.model_output_parser import ModelOutputParser
from runtime.agent.server_tool_executor import ServerToolExecutor
from runtime.agent.session_runtime import AgentSessionRuntime
from runtime.agent.session_state_store import AgentSessionStateStore
from runtime.agent.streaming_policy import StreamingPolicyResolver
from runtime.agent.thinking_policy import ThinkingPolicyResolver
from runtime.entities.anthropic_entities import AnthropicMessage, AnthropicTextBlock, AnthropicToolResultBlock
from service.agent.contracts import AgentTurnResult, AgentTurnState
from service.agent.errors import AgentValidationError


class AgentLoopKernel:
    @classmethod
    async def run(
        cls,
        *,
        agent,
        session_id: int,
        user_id: str | None,
        mode: str,
        surface: str,
        request,
        latest_input,
        tools,
        tool_schema,
        permission,
    ) -> AgentTurnResult:
        provider_name = cls._provider_name(request.model)
        AgentSessionRuntime.persist_input_turn(
            session_id=session_id,
            agent_id=agent.id,
            user_id=user_id,
            model_name=request.model,
            provider_name=provider_name,
            message=latest_input,
            system_prompt=cls._system_text(request.system),
        )
        hydrated_request, _session_state, compression_state, memory_state = await ContextHydrator.hydrate(
            agent=agent,
            session_id=session_id,
            user_id=user_id,
            mode=mode,
            surface=surface,
            request=request,
            tools=tools,
            permission=permission,
        )
        if mode == "agent" and tools:
            hydrated_request.tools = [tool.entity.convert_to_anthropic_tool() for tool in tools]

        thinking_mode = ThinkingPolicyResolver.resolve(mode=mode, request=hydrated_request, agent_name=agent.name)
        stream_mode = StreamingPolicyResolver.resolve(request=hydrated_request)
        if stream_mode == "streaming":
            raise AgentValidationError("streaming is not implemented for the unified agent kernel yet")

        current_request = hydrated_request
        tool_results_payload: list[dict[str, object]] = []
        for _ in range(8):
            response = await AgentModelFacade.invoke_non_streaming(
                current_request,
                agent=agent,
                session_id=session_id,
                user_id=user_id,
            )
            AgentSessionRuntime.persist_assistant_turn(
                session_id=session_id,
                agent_id=agent.id,
                user_id=user_id,
                model_name=current_request.model,
                provider_name=provider_name,
                response=response,
                system_prompt=cls._system_text(current_request.system),
            )
            tool_calls = ModelOutputParser.extract_tool_calls(response, tools=tools)
            if not tool_calls:
                write_task_id = await MemoryWriteCoordinator.maybe_schedule_write(
                    mode=mode,
                    session_id=session_id,
                    user_id=user_id,
                    agent_id=agent.id,
                    agent_enabled_memory=bool(getattr(agent, "enabled_memory", 0) == 1),
                )
                state = AgentTurnState(
                    phase="completed",
                    branch="completion",
                    thinking_mode=thinking_mode,
                    stream_mode=stream_mode,
                    can_continue=False,
                    compression=compression_state,
                    pending_client_actions=[],
                    memory=memory_state.model_copy(
                        update={
                            "writeback_scheduled": bool(write_task_id),
                            "write_task_id": write_task_id,
                        }
                    ),
                )
                AgentSessionStateStore.patch(
                    session_id,
                    {
                        "pending_client_actions": [],
                        "memory_state": state.memory.model_dump(mode="python"),
                    },
                )
                return AgentTurnResult(
                    agent_id=agent.id,
                    session_id=session_id,
                    mode=mode,
                    surface=surface,
                    response=response,
                    state=state,
                    client_actions=[],
                    tool_results=tool_results_payload,
                )

            if mode == "chat":
                raise AgentValidationError("chat mode does not allow tool_use responses")

            if surface == "desktop":
                actions = []
                schema_map = {item.name: item for item in tool_schema}
                phase = "awaiting_client_tool_result"
                for call in tool_calls:
                    if call["tool_name"] in permission.approval_required_tool_names:
                        actions.append(
                            ClientActionBroker.emit_tool_approval_request(
                                tool_call=call,
                                tool_schema=schema_map,
                            )
                        )
                        phase = "awaiting_user_approval"
                    else:
                        actions.append(
                            ClientActionBroker.emit_tool_execution_request(
                                tool_call=call,
                                tool_schema=schema_map,
                            )
                        )
                state = AgentTurnState(
                    phase=phase,
                    branch="tool",
                    thinking_mode=thinking_mode,
                    stream_mode=stream_mode,
                    can_continue=True,
                    compression=compression_state,
                    pending_client_actions=actions,
                    memory=memory_state,
                )
                AgentSessionStateStore.patch(session_id, {"pending_client_actions": actions})
                return AgentTurnResult(
                    agent_id=agent.id,
                    session_id=session_id,
                    mode=mode,
                    surface=surface,
                    response=response,
                    state=state,
                    client_actions=actions,
                    tool_results=tool_results_payload,
                )

            executable = [call for call in tool_calls if call["tool_name"] in permission.allowed_tool_names]
            server_results = await ServerToolExecutor.execute_tool_calls(
                tool_calls=executable,
                agent_id=agent.id,
                session_id=session_id,
                user_id=user_id,
            )
            tool_results_payload.extend(server_results)
            current_request.messages.append(
                AnthropicMessage(
                    role="user",
                    content=[
                        AnthropicToolResultBlock(
                            tool_use_id=str(item["tool_use_id"]),
                            content=str(item["output"]),
                            is_error=bool(item["is_error"]),
                        )
                        for item in server_results
                    ]
                    or [AnthropicTextBlock(text="No tool results available")],
                )
            )

        raise AgentValidationError("agent tool loop exceeded max rounds")

    @staticmethod
    def _provider_name(model_name: str) -> str:
        lowered = str(model_name or "").lower()
        if "claude" in lowered:
            return "anthropic"
        if "gpt" in lowered or lowered.startswith("o"):
            return "openai"
        return "unknown"

    @staticmethod
    def _system_text(system) -> str:
        if isinstance(system, str):
            return system
        if isinstance(system, list):
            return "\n".join(str(getattr(item, "text", "") or "") for item in system)
        return ""
