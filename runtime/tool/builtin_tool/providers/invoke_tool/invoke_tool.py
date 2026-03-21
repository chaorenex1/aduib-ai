from __future__ import annotations

import json
from typing import Any

from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.entities import ToolInvokeResult, ToolProviderType


class ToolExecutorTool(BuiltinTool):
    """Invoke a non-builtin tool through ToolManager."""

    async def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> ToolInvokeResult:
        try:
            tool_manager = tool_parameters.get("tool_manager")
            if tool_manager is None:
                raise ValueError("'tool_manager' is required")

            target_name = self._require_non_empty_string(
                tool_parameters.get("toolName") or tool_parameters.get("name"),
                field_name="toolName",
            )
            target_arguments = self._resolve_arguments(tool_parameters.get("arguments"))
            provider_type, resolved_name = self._resolve_target(
                tool_manager,
                target_name=target_name,
                raw_provider=tool_parameters.get("toolProvider") or tool_parameters.get("provider"),
            )

            result = await tool_manager.invoke_tool(
                tool_name=resolved_name,
                tool_arguments=target_arguments,
                tool_provider=provider_type.value,
                message_id=message_id,
            )
            if result is None:
                raise ValueError(f"Tool '{resolved_name}' returned no result")

            return ToolInvokeResult(
                name=self.entity.name,
                data=result.data,
                success=result.success,
                error=result.error,
                meta={
                    "message_id": message_id,
                    "targetToolName": resolved_name,
                    "targetProvider": provider_type.value,
                    "targetMeta": result.meta,
                },
                tool_call_id=result.tool_call_id,
            )
        except ValueError as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))
        except Exception as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))

    @staticmethod
    def _optional_string(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @classmethod
    def _require_non_empty_string(cls, value: object, *, field_name: str) -> str:
        text = cls._optional_string(value)
        if not text:
            raise ValueError(f"'{field_name}' must be a non-empty string")
        return text

    @staticmethod
    def _resolve_arguments(value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return {}
            try:
                decoded = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError("'arguments' must be a JSON object when provided as string") from exc
            if not isinstance(decoded, dict):
                raise ValueError("'arguments' must decode to a JSON object")
            return decoded
        raise ValueError("'arguments' must be an object")

    @classmethod
    def _resolve_provider_type(cls, raw_provider: object) -> ToolProviderType | None:
        provider = cls._optional_string(raw_provider)
        if not provider:
            return None
        normalized = provider.lower()
        if normalized == ToolProviderType.BUILTIN.value:
            raise ValueError("'Tool' only supports non-builtin tools")
        for item in (ToolProviderType.SKILL, ToolProviderType.LOCAL, ToolProviderType.MCP):
            if item.value == normalized:
                return item
        raise ValueError("'toolProvider' must be one of: skill, local, mcp")

    @classmethod
    def _resolve_target(cls, tool_manager, *, target_name: str, raw_provider: object) -> tuple[ToolProviderType, str]:
        requested_provider = cls._resolve_provider_type(raw_provider)

        if requested_provider == ToolProviderType.SKILL:
            tool = tool_manager.get_skill_controller().get_tool(target_name)
            if not tool:
                raise ValueError(f"Skill tool not found: '{target_name}'")
            return ToolProviderType.SKILL, tool.entity.name

        mcp_controller = tool_manager.get_tool_provider(ToolProviderType.MCP)
        if requested_provider in {ToolProviderType.LOCAL, ToolProviderType.MCP}:
            matches = cls._find_mcp_matches(mcp_controller, target_name)
            tool = next((item for item in matches if item[0] == requested_provider), None)
            if not tool:
                raise ValueError(f"{requested_provider.value} tool not found: '{target_name}'")
            return requested_provider, tool[1]

        matches: list[tuple[ToolProviderType, str]] = []
        skill_controller = tool_manager.get_skill_controller()
        if skill_controller:
            skill_tool = skill_controller.get_tool(target_name)
            if skill_tool:
                matches.append((ToolProviderType.SKILL, skill_tool.entity.name))
        if mcp_controller:
            matches.extend(cls._find_mcp_matches(mcp_controller, target_name))

        if not matches:
            raise ValueError(f"Non-builtin tool not found: '{target_name}'")
        unique_matches = list(dict.fromkeys(matches))
        if len(unique_matches) > 1:
            providers = ", ".join(provider.value for provider, _ in unique_matches)
            raise ValueError(f"Tool '{target_name}' is ambiguous; specify toolProvider explicitly: {providers}")
        return unique_matches[0]

    @staticmethod
    def _find_mcp_matches(mcp_controller, target_name: str) -> list[tuple[ToolProviderType, str]]:
        if mcp_controller is None:
            return []
        return [
            (tool.entity.type, tool.entity.name)
            for tool in mcp_controller.get_tools()
            if tool.entity.name == target_name and tool.entity.type in {ToolProviderType.LOCAL, ToolProviderType.MCP}
        ]
