from __future__ import annotations

from runtime.tool.base.tool import Tool
from runtime.tool.tool_manager import ToolManager
from service.agent.contracts import ToolPermissionView, ToolSchemaView


class ToolingSchemaService:
    @classmethod
    def get_tools_for_execution(cls, *, agent) -> list[Tool]:
        manager = ToolManager()
        tools: list[Tool] = []
        for item in agent.tools or []:
            tool_name = str(item.get("tool_name") or "").strip()
            provider = str(item.get("tool_provider_type") or "").strip()
            if not tool_name or not provider:
                continue
            controller = manager.get_tool_provider(provider)
            if controller is None:
                continue
            tool = controller.get_tool(tool_name)
            if tool is not None:
                tools.append(tool)
        return tools

    @classmethod
    def list_visible_tools(
        cls,
        *,
        agent,
        mode: str,
        surface: str,
        permission: ToolPermissionView,
    ) -> list[ToolSchemaView]:
        tools = cls.get_tools_for_execution(agent=agent)
        execution_side = "disabled" if mode == "chat" else ("server" if surface == "web" else "client")
        visible: list[ToolSchemaView] = []
        for tool in tools:
            entity = tool.entity
            visible.append(
                ToolSchemaView(
                    name=entity.name,
                    description=entity.description or "",
                    provider=entity.provider or "",
                    tool_type=entity.type.value if getattr(entity, "type", None) is not None else "",
                    input_schema=entity.parameters or {},
                    execution_side=execution_side,
                    requires_approval=entity.name in permission.approval_required_tool_names,
                )
            )
        return visible
