from __future__ import annotations

from runtime.agent.session_runtime import AgentSessionRuntime
from runtime.agent.tool_permission_service import ToolPermissionService
from runtime.agent.tooling_schema_service import ToolingSchemaService
from service.agent.contracts import ToolingPermissionCommand, ToolingSchemaCommand, ToolPermissionView


class AgentToolingService:
    @classmethod
    async def get_schema(cls, query: ToolingSchemaCommand):
        agent = AgentSessionRuntime.resolve_agent(query.agent_id)
        tools = ToolingSchemaService.get_tools_for_execution(agent=agent)
        permission = ToolPermissionService.get_effective_permissions(
            agent_id=agent.id,
            mode=query.mode,
            surface=query.surface,
            tool_names=[tool.entity.name for tool in tools],
        )
        return ToolingSchemaService.list_visible_tools(
            agent=agent,
            mode=query.mode,
            surface=query.surface,
            permission=permission,
        )

    @classmethod
    async def get_permission(cls, query: ToolingPermissionCommand) -> ToolPermissionView:
        agent = AgentSessionRuntime.resolve_agent(query.agent_id)
        tools = ToolingSchemaService.get_tools_for_execution(agent=agent)
        return ToolPermissionService.get_effective_permissions(
            agent_id=agent.id,
            mode=query.mode,
            surface=query.surface,
            tool_names=[tool.entity.name for tool in tools],
        )
