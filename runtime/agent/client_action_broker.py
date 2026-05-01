from __future__ import annotations

from service.agent.contracts import ToolSchemaView


class ClientActionBroker:
    @classmethod
    def emit_tool_approval_request(
        cls, *, tool_call: dict[str, object], tool_schema: dict[str, ToolSchemaView]
    ) -> dict[str, object]:
        schema = tool_schema.get(str(tool_call["tool_name"]))
        return {
            "type": "approval_request",
            "tool_use_id": tool_call["tool_use_id"],
            "tool_name": tool_call["tool_name"],
            "input": tool_call.get("tool_input") or {},
            "schema": schema.model_dump(mode="python") if schema else None,
        }

    @classmethod
    def emit_tool_execution_request(
        cls, *, tool_call: dict[str, object], tool_schema: dict[str, ToolSchemaView]
    ) -> dict[str, object]:
        schema = tool_schema.get(str(tool_call["tool_name"]))
        return {
            "type": "tool_execution_request",
            "tool_use_id": tool_call["tool_use_id"],
            "tool_name": tool_call["tool_name"],
            "input": tool_call.get("tool_input") or {},
            "schema": schema.model_dump(mode="python") if schema else None,
        }
