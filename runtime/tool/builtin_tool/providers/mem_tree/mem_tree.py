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


class MemTreeTool(BuiltinTool):
    async def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> ToolInvokeResult:
        return await anyio.to_thread.run_sync(self._tree_sync, tool_parameters)

    def _tree_sync(self, tool_parameters: dict[str, Any]) -> ToolInvokeResult:
        try:
            max_depth = tool_parameters.get("max_depth")
            data = CommittedMemoryTree.build_tree(
                path=str(tool_parameters.get("path") or ""),
                include_dirs=parse_bool(tool_parameters.get("include_dirs"), default=True),
                include_content=parse_bool(tool_parameters.get("include_content"), default=True),
                max_depth=int(max_depth) if max_depth not in {None, ""} else None,
                max_files=parse_int(tool_parameters.get("max_files"), default=None),
                max_chars_per_file=parse_int(tool_parameters.get("max_chars_per_file"), default=None),
                max_total_chars=parse_int(tool_parameters.get("max_total_chars"), default=None),
            )
            return ToolInvokeResult(name=self.entity.name, data=data)
        except (MemoryTreeError, ValueError) as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))
