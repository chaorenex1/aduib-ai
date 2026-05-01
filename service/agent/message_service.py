from __future__ import annotations

from runtime.agent.input_orchestrator import InputOrchestrator
from runtime.agent.loop_kernel import AgentLoopKernel
from runtime.agent.session_runtime import AgentSessionRuntime
from runtime.agent.session_state_store import AgentSessionStateStore
from runtime.agent.tool_permission_service import ToolPermissionService
from runtime.agent.tooling_schema_service import ToolingSchemaService
from service.agent.contracts import AgentMessagesCommand, AgentMessageTurnCommand, AgentTurnResult
from service.agent.errors import AgentValidationError


class AgentMessageService:
    @classmethod
    async def handle_messages(cls, payload: AgentMessagesCommand) -> AgentTurnResult:
        agent = AgentSessionRuntime.resolve_agent(payload.agent_id)
        resolved_session = AgentSessionRuntime.get_or_create_session(
            agent=agent,
            session_id=payload.session_id,
            mode=payload.mode,
            surface=payload.surface,
        )
        resolved_input = InputOrchestrator.build_from_messages(payload)
        tools = ToolingSchemaService.get_tools_for_execution(agent=agent)
        permission = ToolPermissionService.get_effective_permissions(
            agent_id=agent.id,
            mode=payload.mode,
            surface=payload.surface,
            tool_names=[tool.entity.name for tool in tools],
        )
        tool_schema = ToolingSchemaService.list_visible_tools(
            agent=agent,
            mode=payload.mode,
            surface=payload.surface,
            permission=permission,
        )
        return await AgentLoopKernel.run(
            agent=agent,
            session_id=resolved_session.session.id,
            user_id=resolved_session.user_id,
            mode=payload.mode,
            surface=payload.surface,
            request=resolved_input.request,
            latest_input=resolved_input.latest_input,
            tools=tools,
            tool_schema=tool_schema,
            permission=permission,
        )

    @classmethod
    async def handle_message(cls, payload: AgentMessageTurnCommand) -> AgentTurnResult:
        agent = AgentSessionRuntime.resolve_agent(payload.agent_id)
        resolved_session = AgentSessionRuntime.get_or_create_session(
            agent=agent,
            session_id=payload.session_id,
            mode=payload.mode,
            surface=payload.surface,
        )
        cls._validate_client_turn(session_id=resolved_session.session.id, payload=payload)
        history = AgentSessionRuntime.load_history_as_anthropic_messages(
            session_id=resolved_session.session.id,
            user_id=resolved_session.user_id,
            agent_id=agent.id,
        )
        resolved_input = InputOrchestrator.build_from_message_turn(payload, history_messages=history)
        tools = ToolingSchemaService.get_tools_for_execution(agent=agent)
        permission = ToolPermissionService.get_effective_permissions(
            agent_id=agent.id,
            mode=payload.mode,
            surface=payload.surface,
            tool_names=[tool.entity.name for tool in tools],
        )
        tool_schema = ToolingSchemaService.list_visible_tools(
            agent=agent,
            mode=payload.mode,
            surface=payload.surface,
            permission=permission,
        )
        return await AgentLoopKernel.run(
            agent=agent,
            session_id=resolved_session.session.id,
            user_id=resolved_session.user_id,
            mode=payload.mode,
            surface=payload.surface,
            request=resolved_input.request,
            latest_input=resolved_input.latest_input,
            tools=tools,
            tool_schema=tool_schema,
            permission=permission,
        )

    @staticmethod
    def _validate_client_turn(*, session_id: int, payload: AgentMessageTurnCommand) -> None:
        if not payload.tool_results and payload.approval_decision is None:
            return

        state = AgentSessionStateStore.load(session_id)
        pending = {str(item.get("tool_use_id")): str(item.get("tool_name")) for item in state.pending_client_actions}
        if not pending:
            raise AgentValidationError("no pending client action exists for this session")

        if payload.approval_decision is not None:
            tool_use_id = payload.approval_decision.tool_use_id
            expected_name = pending.get(tool_use_id)
            if expected_name is None or expected_name != payload.approval_decision.tool_name:
                raise AgentValidationError("unknown or expired tool approval request")
            AgentSessionStateStore.patch(
                session_id,
                {
                    "pending_client_actions": [
                        item for item in state.pending_client_actions if item.get("tool_use_id") != tool_use_id
                    ]
                },
            )
            return

        for item in payload.tool_results:
            expected_name = pending.get(item.tool_use_id)
            if expected_name is None or expected_name != item.tool_name:
                raise AgentValidationError("unknown or expired client tool result")

        resolved_ids = {item.tool_use_id for item in payload.tool_results}
        AgentSessionStateStore.patch(
            session_id,
            {
                "pending_client_actions": [
                    item for item in state.pending_client_actions if item.get("tool_use_id") not in resolved_ids
                ]
            },
        )
