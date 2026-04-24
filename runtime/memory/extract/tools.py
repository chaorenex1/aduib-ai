from __future__ import annotations

import hashlib
import json

import anyio

from runtime.tool.builtin_tool.providers.mem_glob.mem_glob import MemGlobTool
from runtime.tool.builtin_tool.providers.mem_ls.mem_ls import MemLsTool
from runtime.tool.builtin_tool.providers.mem_read.mem_read import MemReadTool
from runtime.tool.entities import ToolEntity, ToolProviderType
from runtime.tool.tool_manager import ToolManager
from service.memory.base.contracts import PlannerToolRequest, PlannerToolUseResult

SUPPORTED_PLANNER_TOOLS = ("ls", "read", "find")
PLANNER_TOOL_TO_BUILTIN = {
    "ls": "mem-ls",
    "read": "mem-read",
    "find": "mem-glob",
}


class PlannerToolExecutor:
    def __init__(self) -> None:
        self.tool_manager = ToolManager.__new__(ToolManager)

    async def execute(self, request: PlannerToolRequest, *, message_id: str | None = None) -> PlannerToolUseResult:
        builtin_tool_name = PLANNER_TOOL_TO_BUILTIN.get(request.tool)
        if not builtin_tool_name:
            raise ValueError(f"unsupported planner tool: {request.tool}")

        result = await self.tool_manager.invoke_tool(
            tool_name=builtin_tool_name,
            tool_arguments=request.args,
            tool_provider="builtin",
            tool_call_id=self._tool_call_id(request),
            message_id=message_id,
        )
        if result is None:
            raise ValueError(f"builtin tool returned no result: {builtin_tool_name}")
        if not result.success:
            raise ValueError(result.error or f"builtin tool failed: {builtin_tool_name}")

        data = result.data
        if isinstance(data, dict):
            normalized = data
        else:
            normalized = {"value": data}

        return PlannerToolUseResult(
            tool=request.tool,
            args=request.args,
            result=normalized,
        )

    def execute_sync(self, request: PlannerToolRequest, *, message_id: str | None = None) -> PlannerToolUseResult:
        return anyio.run(self.execute, request, message_id)

    @staticmethod
    def _tool_call_id(request: PlannerToolRequest) -> str:
        encoded = json.dumps(request.args, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
        return f"planner_{request.tool}_{digest}"


class _PlannerBuiltinToolController:
    def __init__(self) -> None:
        self.tools = {
            "mem-ls": _build_builtin_tool(MemLsTool, "mem-ls"),
            "mem-read": _build_builtin_tool(MemReadTool, "mem-read"),
            "mem-glob": _build_builtin_tool(MemGlobTool, "mem-glob"),
        }

    def get_tool(self, tool_name: str):
        return self.tools.get(tool_name)

    def get_tools(self, filter_names: list[str] | None = None):
        if filter_names:
            return [tool for name, tool in self.tools.items() if name in filter_names]
        return list(self.tools.values())


def _build_builtin_tool(tool_cls: type, name: str):
    return tool_cls(
        entity=ToolEntity(
            name=name,
            description=name,
            parameters={},
            provider="builtin_provider",
            type=ToolProviderType.BUILTIN,
            configs={},
        )
    )
