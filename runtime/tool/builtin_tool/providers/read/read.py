from typing import Any

import anyio

from runtime.tool.builtin_tool.providers._workspace import (
    DEFAULT_ENCODING,
    DEFAULT_MAX_READ_CHARS,
    WorkspaceToolError,
    is_probably_binary,
    relative_to_workdir,
    resolve_workdir_path,
    truncate_text,
)
from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.entities import ToolInvokeResult


class ReadTool(BuiltinTool):
    """
    A tool to read file contents.
    """

    async def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> ToolInvokeResult:
        return await anyio.to_thread.run_sync(self._read_sync, tool_parameters)

    def _read_sync(self, tool_parameters: dict[str, Any]) -> ToolInvokeResult:
        file_path = tool_parameters.get("file_path", "")
        encoding = tool_parameters.get("encoding") or DEFAULT_ENCODING
        max_chars = int(tool_parameters.get("max_chars") or DEFAULT_MAX_READ_CHARS)
        start_line = tool_parameters.get("start_line")
        end_line = tool_parameters.get("end_line")

        try:
            workdir, resolved = resolve_workdir_path(file_path)
            if not resolved.is_file():
                raise WorkspaceToolError("path is not a file")
            if is_probably_binary(resolved):
                raise WorkspaceToolError("binary files are not supported")
            if start_line is not None and int(start_line) < 1:
                raise WorkspaceToolError("start_line must be at least 1")
            if end_line is not None and int(end_line) < 1:
                raise WorkspaceToolError("end_line must be at least 1")
            if start_line is not None and end_line is not None and int(end_line) < int(start_line):
                raise WorkspaceToolError("end_line must be greater than or equal to start_line")

            content = resolved.read_text(encoding=encoding)
            selected_content, line_start, line_end = self._slice_content(
                content=content,
                start_line=int(start_line) if start_line is not None else None,
                end_line=int(end_line) if end_line is not None else None,
            )
            truncated_content, truncated = truncate_text(selected_content, max_chars)
            return ToolInvokeResult(
                name=self.entity.name,
                data={
                    "file_path": relative_to_workdir(resolved, workdir),
                    "content": truncated_content,
                    "encoding": encoding,
                    "line_start": line_start,
                    "line_end": line_end,
                    "truncated": truncated,
                },
                meta={
                    "workdir": str(workdir),
                    "absolute_path": str(resolved),
                },
            )
        except (OSError, UnicodeDecodeError, ValueError, WorkspaceToolError) as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))

    @staticmethod
    def _slice_content(content: str, start_line: int | None, end_line: int | None) -> tuple[str, int, int]:
        if start_line is None and end_line is None:
            total_lines = content.count("\n") + 1 if content else 0
            return content, 1 if total_lines else 0, total_lines

        lines = content.splitlines(keepends=True)
        start_index = (start_line - 1) if start_line is not None else 0
        end_index = end_line if end_line is not None else len(lines)
        selected = "".join(lines[start_index:end_index])
        actual_start = start_line if start_line is not None else 1
        actual_end = min(end_index, len(lines))
        return selected, actual_start, actual_end
