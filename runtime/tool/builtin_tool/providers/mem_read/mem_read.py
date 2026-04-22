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


class MemReadTool(BuiltinTool):
    async def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> ToolInvokeResult:
        return await anyio.to_thread.run_sync(self._read_sync, tool_parameters)

    def _read_sync(self, tool_parameters: dict[str, Any]) -> ToolInvokeResult:
        try:
            path = tool_parameters.get("path")
            if not isinstance(path, str) or not path.strip():
                raise MemoryTreeError("path must be a non-empty string")
            data = CommittedMemoryTree.read_file(
                path=path,
                start_line=tool_parameters.get("start_line"),
                end_line=tool_parameters.get("end_line"),
                max_chars=parse_int(tool_parameters.get("max_chars"), default=None),
                include_metadata=parse_bool(tool_parameters.get("include_metadata"), default=True),
            )
            return ToolInvokeResult(name=self.entity.name, data=data)
        except (MemoryTreeError, ValueError) as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))
