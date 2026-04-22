from __future__ import annotations

from typing import Any

import anyio

from runtime.memory.committed_tree import CommittedMemoryTree, MemoryTreeError
from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.common import parse_int
from runtime.tool.entities import ToolInvokeResult


class MemGlobTool(BuiltinTool):
    async def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> ToolInvokeResult:
        return await anyio.to_thread.run_sync(self._glob_sync, tool_parameters)

    def _glob_sync(self, tool_parameters: dict[str, Any]) -> ToolInvokeResult:
        try:
            query = tool_parameters.get("query")
            if not isinstance(query, str) or not query.strip():
                raise MemoryTreeError("query must be a non-empty string")
            data = CommittedMemoryTree.search_paths(
                query=query,
                path=str(tool_parameters.get("path") or ""),
                glob_pattern=tool_parameters.get("glob"),
                max_results=parse_int(tool_parameters.get("max_results"), default=None),
            )
            return ToolInvokeResult(name=self.entity.name, data=data)
        except (MemoryTreeError, ValueError) as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))
