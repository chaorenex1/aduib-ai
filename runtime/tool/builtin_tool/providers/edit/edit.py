from typing import Any

import anyio

from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.common import (
    WorkspaceToolError,
    is_probably_binary,
    relative_to_workdir,
    resolve_workdir_path,
)
from runtime.tool.entities import ToolInvokeResult


class EditTool(BuiltinTool):
    """
    A tool to edit files with string replacement.
    """

    async def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> ToolInvokeResult:
        return await anyio.to_thread.run_sync(self._edit_sync, tool_parameters)

    def _edit_sync(self, tool_parameters: dict[str, Any]) -> ToolInvokeResult:
        file_path = tool_parameters.get("file_path", "")
        old_string = tool_parameters.get("old_string", "")
        new_string = tool_parameters.get("new_string", "")
        replace_all = bool(tool_parameters.get("replace_all", False))
        expected_occurrences = tool_parameters.get("expected_occurrences")
        encoding = tool_parameters.get("encoding") or "utf-8"
        start_line = tool_parameters.get("start_line")
        end_line = tool_parameters.get("end_line")

        try:
            if not isinstance(old_string, str) or old_string == "":
                raise WorkspaceToolError("old_string must be a non-empty string")
            if not isinstance(new_string, str):
                raise WorkspaceToolError("new_string must be a string")

            workdir, resolved = resolve_workdir_path(file_path)
            if not resolved.is_file():
                raise WorkspaceToolError("path is not a file")
            if is_probably_binary(resolved):
                raise WorkspaceToolError("binary files are not supported")

            content = resolved.read_text(encoding=encoding)
            target_text, target_start_line, target_end_line = self._select_target_text(
                content=content,
                start_line=start_line,
                end_line=end_line,
            )
            occurrences = target_text.count(old_string)
            if occurrences == 0:
                raise WorkspaceToolError("old_string not found in file")

            if expected_occurrences is not None:
                expected_occurrences = int(expected_occurrences)
                if occurrences != expected_occurrences:
                    raise WorkspaceToolError(f"expected {expected_occurrences} occurrence(s), found {occurrences}")
            elif not replace_all and occurrences != 1:
                raise WorkspaceToolError(
                    f"old_string occurs {occurrences} times; set replace_all=true or expected_occurrences"
                )

            replacement_count = occurrences if replace_all else 1
            updated_target = target_text.replace(old_string, new_string, replacement_count)
            updated_content = self._merge_updated_content(
                content=content,
                updated_target=updated_target,
                start_line=target_start_line,
                end_line=target_end_line,
            )
            resolved.write_text(updated_content, encoding=encoding)

            return ToolInvokeResult(
                name=self.entity.name,
                data={
                    "file_path": relative_to_workdir(resolved, workdir),
                    "replacements": replacement_count,
                    "line_start": target_start_line,
                    "line_end": target_end_line,
                },
                meta={
                    "workdir": str(workdir),
                    "absolute_path": str(resolved),
                },
            )
        except (OSError, UnicodeDecodeError, ValueError, WorkspaceToolError) as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))

    @staticmethod
    def _select_target_text(
        *,
        content: str,
        start_line: Any,
        end_line: Any,
    ) -> tuple[str, int, int]:
        if start_line is None and end_line is None:
            total_lines = content.count("\n") + 1 if content else 0
            return content, 1 if total_lines else 0, total_lines

        lines = content.splitlines(keepends=True)
        if not lines:
            raise WorkspaceToolError("file is empty")

        start = int(start_line) if start_line is not None else 1
        end = int(end_line) if end_line is not None else len(lines)
        if start < 1:
            raise WorkspaceToolError("start_line must be at least 1")
        if end < 1:
            raise WorkspaceToolError("end_line must be at least 1")
        if end < start:
            raise WorkspaceToolError("end_line must be greater than or equal to start_line")
        if start > len(lines) or end > len(lines):
            raise WorkspaceToolError("line range is out of bounds")

        return "".join(lines[start - 1 : end]), start, end

    @staticmethod
    def _merge_updated_content(
        *,
        content: str,
        updated_target: str,
        start_line: int,
        end_line: int,
    ) -> str:
        if start_line == 0 and end_line == 0:
            return updated_target

        lines = content.splitlines(keepends=True)
        return "".join(lines[: start_line - 1]) + updated_target + "".join(lines[end_line:])
