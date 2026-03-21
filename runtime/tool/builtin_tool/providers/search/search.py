import re
from typing import Any

import anyio

from runtime.tool.builtin_tool.providers._workspace import (
    DEFAULT_ENCODING,
    MAX_SEARCH_FILE_BYTES,
    WorkspaceToolError,
    is_probably_binary,
    iter_files,
    relative_to_workdir,
    resolve_workdir_path,
)
from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.entities import ToolInvokeResult


class SearchTool(BuiltinTool):
    """
    A tool to search codebase.
    """

    async def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> ToolInvokeResult:
        return await anyio.to_thread.run_sync(self._search_sync, tool_parameters)

    def _search_sync(self, tool_parameters: dict[str, Any]) -> ToolInvokeResult:
        pattern = tool_parameters.get("pattern", "")
        path_value = tool_parameters.get("path", ".")
        glob_pattern = tool_parameters.get("glob")
        case_sensitive = bool(tool_parameters.get("case_sensitive", False))
        max_results = int(tool_parameters.get("max_results") or 20)

        try:
            if not isinstance(pattern, str) or not pattern:
                raise WorkspaceToolError("pattern must be a non-empty string")
            if max_results < 1:
                raise WorkspaceToolError("max_results must be at least 1")

            workdir, base_path = resolve_workdir_path(path_value)
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)
            results: list[dict[str, Any]] = []

            for candidate in iter_files(base_path, glob_pattern):
                if candidate.stat().st_size > MAX_SEARCH_FILE_BYTES or is_probably_binary(candidate):
                    continue
                try:
                    with candidate.open("r", encoding=DEFAULT_ENCODING, errors="replace") as file_obj:
                        for line_number, line in enumerate(file_obj, start=1):
                            if regex.search(line):
                                results.append(
                                    {
                                        "file_path": relative_to_workdir(candidate, workdir),
                                        "line_number": line_number,
                                        "line": line.rstrip(),
                                    }
                                )
                                if len(results) >= max_results:
                                    return ToolInvokeResult(
                                        name=self.entity.name,
                                        data={
                                            "pattern": pattern,
                                            "path": relative_to_workdir(base_path, workdir),
                                            "results": results,
                                            "truncated": True,
                                        },
                                        meta={"workdir": str(workdir)},
                                    )
                except OSError:
                    continue

            return ToolInvokeResult(
                name=self.entity.name,
                data={
                    "pattern": pattern,
                    "path": relative_to_workdir(base_path, workdir),
                    "results": results,
                    "truncated": False,
                },
                meta={"workdir": str(workdir)},
            )
        except (OSError, re.error, ValueError, WorkspaceToolError) as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))
