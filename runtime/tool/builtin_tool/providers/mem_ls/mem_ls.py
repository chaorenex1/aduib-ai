from __future__ import annotations

from typing import Any

import anyio

from runtime.memory.committed_tree import (
    CommittedMemoryTree,
    MemoryTreeError,
)
from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.common import parse_bool, parse_int
from runtime.tool.entities import ToolInvokeResult


class MemLsTool(BuiltinTool):
    async def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> ToolInvokeResult:
        return await anyio.to_thread.run_sync(self._list_sync, tool_parameters)

    def _list_sync(self, tool_parameters: dict[str, Any]) -> ToolInvokeResult:
        try:
            data = CommittedMemoryTree.list_entries(
                path=str(tool_parameters.get("path") or ""),
                recursive=parse_bool(tool_parameters.get("recursive"), default=False),
                include_files=parse_bool(tool_parameters.get("include_files"), default=True),
                include_dirs=parse_bool(tool_parameters.get("include_dirs"), default=True),
                max_results=parse_int(tool_parameters.get("max_results"), default=None),
            )
            return ToolInvokeResult(name=self.entity.name, data=data)
        except (MemoryTreeError, ValueError) as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))
