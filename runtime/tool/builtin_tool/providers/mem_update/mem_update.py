from __future__ import annotations

from typing import Any

import anyio

from component.storage.base_storage import storage_manager
from configs import config
from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.entities import ToolInvokeResult


class MemUpdateTool(BuiltinTool):
    async def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> ToolInvokeResult:
        return await anyio.to_thread.run_sync(self._update_sync, tool_parameters)

    def _update_sync(self, tool_parameters: dict[str, Any]) -> ToolInvokeResult:
        try:
            path = str(tool_parameters.get("path") or "").strip()
            content = str(tool_parameters.get("content") or "")
            if not path:
                raise ValueError("path must be a non-empty string")
            scoped_path = _to_scoped_path(path)
            if not storage_manager.exists(scoped_path):
                raise ValueError(f"memory file not found: {path}")
            storage_manager.write_text_atomic(scoped_path, content)
            return ToolInvokeResult(name=self.entity.name, data={"path": path, "updated": True})
        except Exception as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))


def _to_scoped_path(relative_path: str) -> str:
    return "/".join(part for part in [config.MEMORY_TREE_ROOT_DIR, relative_path] if part)
