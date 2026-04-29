from __future__ import annotations

from typing import Any

from libs.context import get_current_user_id
from runtime.memory.manager import LegacyMemoryWriteDisabledError
from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.entities import ToolInvokeResult


class CreateMemoryTool(BuiltinTool):
    """Create a long-term memory entry."""

    async def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> ToolInvokeResult:
        try:
            content = self._require_non_empty_string(tool_parameters.get("content"), field_name="content")
            user_id = self._resolve_user_id(tool_parameters)
            from runtime.agent_manager import AgentManager

            agent_manager: AgentManager = tool_parameters.get("agent_manager")
            short_term = tool_parameters.get("short_term", False)
            if short_term:
                await agent_manager.memory_manager.add_memory(content)
            else:
                # Legacy long-term writes used runtime.memory.manager.store(); keep the
                # old path blocked until the createMemory tool is migrated.
                # await agent_manager.memory_manager.add_memory(content, long_term_memory=True)
                raise LegacyMemoryWriteDisabledError(
                    "Long-term memory creation via createMemory is disabled until migrated "
                    "to the new memory pipeline."
                )

            return ToolInvokeResult(
                name=self.entity.name,
                data={
                    "userId": user_id,
                },
                meta={"message_id": message_id},
            )
        except ValueError as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))
        except Exception as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))

    @staticmethod
    def _require_non_empty_string(value: object, *, field_name: str) -> str:
        if value is None:
            raise ValueError(f"'{field_name}' must be a non-empty string")
        text = str(value).strip()
        if not text:
            raise ValueError(f"'{field_name}' must be a non-empty string")
        return text

    @staticmethod
    def _resolve_user_id(tool_parameters: dict[str, Any]) -> str:
        user_id = tool_parameters.get("userId") or get_current_user_id()
        if user_id is None or not str(user_id).strip():
            raise ValueError("'userId' is required")
        return str(user_id).strip()
