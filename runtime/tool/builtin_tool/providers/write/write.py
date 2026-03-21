from typing import Any

import anyio

from runtime.tool.builtin_tool.providers._workspace import (
    DEFAULT_ENCODING,
    WorkspaceToolError,
    is_probably_binary,
    relative_to_workdir,
    resolve_workdir_path,
)
from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.entities import ToolInvokeResult


class WriteTool(BuiltinTool):
    """
    A tool to write content to files.
    """

    async def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> ToolInvokeResult:
        return await anyio.to_thread.run_sync(self._write_sync, tool_parameters)

    def _write_sync(self, tool_parameters: dict[str, Any]) -> ToolInvokeResult:
        file_path = tool_parameters.get("file_path", "")
        content = tool_parameters.get("content", "")
        mode = tool_parameters.get("mode")
        append = bool(tool_parameters.get("append", False))
        create_dirs = bool(tool_parameters.get("create_dirs", True))
        encoding = tool_parameters.get("encoding") or DEFAULT_ENCODING
        line = tool_parameters.get("line")
        start_line = tool_parameters.get("start_line")
        end_line = tool_parameters.get("end_line")

        try:
            if not isinstance(content, str):
                raise WorkspaceToolError("content must be a string")
            normalized_mode = self._normalize_mode(mode=mode, append=append)
            workdir, resolved = resolve_workdir_path(file_path, allow_missing=True)
            if resolved.exists() and resolved.is_dir():
                raise WorkspaceToolError("path is a directory")
            if create_dirs or normalized_mode == "overwrite":
                resolved.parent.mkdir(parents=True, exist_ok=True)
            elif not resolved.parent.exists():
                raise WorkspaceToolError("parent directory does not exist")

            if normalized_mode in {"overwrite", "append"}:
                written = self._write_full_file(
                    resolved=resolved,
                    content=content,
                    encoding=encoding,
                    mode=normalized_mode,
                )
                data = {
                    "file_path": relative_to_workdir(resolved, workdir),
                    "bytes_written": len(content.encode(encoding)),
                    "characters_written": written,
                    "mode": normalized_mode,
                }
            else:
                data = self._write_lines(
                    resolved=resolved,
                    workdir=workdir,
                    content=content,
                    encoding=encoding,
                    mode=normalized_mode,
                    line=line,
                    start_line=start_line,
                    end_line=end_line,
                )

            return ToolInvokeResult(
                name=self.entity.name,
                data=data,
                meta={
                    "workdir": str(workdir),
                    "absolute_path": str(resolved),
                },
            )
        except (OSError, UnicodeEncodeError, WorkspaceToolError) as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))

    @staticmethod
    def _normalize_mode(mode: Any, append: bool) -> str:
        normalized_mode = str(mode or "").strip().lower()
        if not normalized_mode:
            return "append" if append else "overwrite"
        allowed_modes = {"overwrite", "append", "replace_lines", "insert_before", "insert_after"}
        if normalized_mode not in allowed_modes:
            raise WorkspaceToolError(f"unsupported mode: {normalized_mode}")
        return normalized_mode

    @staticmethod
    def _write_full_file(resolved, content: str, encoding: str, mode: str) -> int:
        open_mode = "a" if mode == "append" else "w"
        with resolved.open(open_mode, encoding=encoding) as file_obj:
            return file_obj.write(content)

    def _write_lines(
        self,
        *,
        resolved,
        workdir,
        content: str,
        encoding: str,
        mode: str,
        line: Any,
        start_line: Any,
        end_line: Any,
    ) -> dict[str, Any]:
        if not resolved.exists():
            raise WorkspaceToolError("line-based write requires an existing file")
        if not resolved.is_file():
            raise WorkspaceToolError("path is not a file")
        if is_probably_binary(resolved):
            raise WorkspaceToolError("binary files are not supported")

        original_content = resolved.read_text(encoding=encoding)
        lines = original_content.splitlines(keepends=True)
        new_lines = content.splitlines(keepends=True)

        if mode == "replace_lines":
            start = self._require_line_number(start_line, "start_line")
            end = self._require_line_number(end_line, "end_line")
            if end < start:
                raise WorkspaceToolError("end_line must be greater than or equal to start_line")
            self._validate_line_range(lines, start, end)
            updated_lines = lines[: start - 1] + new_lines + lines[end:]
            affected = {"line_start": start, "line_end": end}
        else:
            target_line = self._require_line_number(line, "line")
            self._validate_single_line(lines, target_line)
            insert_index = target_line - 1 if mode == "insert_before" else target_line
            updated_lines = lines[:insert_index] + new_lines + lines[insert_index:]
            affected = {"line": target_line}

        resolved.write_text("".join(updated_lines), encoding=encoding)
        return {
            "file_path": relative_to_workdir(resolved, workdir),
            "mode": mode,
            "inserted_characters": len(content),
            **affected,
        }

    @staticmethod
    def _require_line_number(value: Any, field_name: str) -> int:
        if value is None:
            raise WorkspaceToolError(f"{field_name} is required for this mode")
        line_number = int(value)
        if line_number < 1:
            raise WorkspaceToolError(f"{field_name} must be at least 1")
        return line_number

    @staticmethod
    def _validate_line_range(lines: list[str], start_line: int, end_line: int) -> None:
        if not lines:
            raise WorkspaceToolError("file is empty")
        if start_line > len(lines) or end_line > len(lines):
            raise WorkspaceToolError("line range is out of bounds")

    @staticmethod
    def _validate_single_line(lines: list[str], line_number: int) -> None:
        if not lines:
            raise WorkspaceToolError("file is empty")
        if line_number > len(lines):
            raise WorkspaceToolError("line is out of bounds")
