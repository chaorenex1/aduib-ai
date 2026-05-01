from __future__ import annotations

from runtime.tool.tool_manager import ToolManager


class ServerToolExecutor:
    @classmethod
    async def execute_tool_calls(
        cls,
        *,
        tool_calls: list[dict[str, object]],
        agent_id: int,
        session_id: int,
        user_id: str | None,
    ) -> list[dict[str, object]]:
        manager = ToolManager()
        results: list[dict[str, object]] = []
        for call in tool_calls:
            tool_input = dict(call.get("tool_input") or {})
            tool_input.update(
                {
                    "agent_id": agent_id,
                    "session_id": session_id,
                    "user_id": user_id,
                }
            )
            result = await manager.invoke_tool(
                tool_name=str(call["tool_name"]),
                tool_arguments=tool_input,
                tool_provider=str(call["provider"]),
                tool_call_id=str(call["tool_use_id"]),
            )
            results.append(
                {
                    "tool_use_id": str(call["tool_use_id"]),
                    "tool_name": str(call["tool_name"]),
                    "output": result.to_normal() if result is not None else "",
                    "is_error": not (result is not None and result.success),
                }
            )
        return results
