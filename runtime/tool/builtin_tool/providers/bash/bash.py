import shlex
import subprocess
from typing import Any

import anyio

from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.common import (
    WorkspaceToolError,
    get_workdir,
    truncate_text,
)
from runtime.tool.entities import ToolInvokeResult


class BashTool(BuiltinTool):
    """
    A tool to execute shell commands.
    """

    async def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> ToolInvokeResult:
        return await anyio.to_thread.run_sync(self._bash_sync, tool_parameters)

    def _bash_sync(self, tool_parameters: dict[str, Any]) -> ToolInvokeResult:
        command = tool_parameters.get("command", "")
        timeout_seconds = int(tool_parameters.get("timeout_seconds") or self.entity.configs.get("timeout", 30))

        try:
            if not isinstance(command, str) or not command.strip():
                raise WorkspaceToolError("command must be a non-empty string")
            if timeout_seconds < 1:
                raise WorkspaceToolError("timeout_seconds must be at least 1")

            argv = shlex.split(command, posix=True)
            if not argv:
                raise WorkspaceToolError("command must contain an executable")

            workdir = get_workdir()
            completed = subprocess.run(
                argv,
                cwd=workdir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                shell=False,
            )
            stdout, stdout_truncated = truncate_text(completed.stdout or "", 50_000)
            stderr, stderr_truncated = truncate_text(completed.stderr or "", 50_000)
            success = completed.returncode == 0
            return ToolInvokeResult(
                name=self.entity.name,
                success=success,
                data={
                    "command": command,
                    "argv": argv,
                    "exit_code": completed.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "stdout_truncated": stdout_truncated,
                    "stderr_truncated": stderr_truncated,
                },
                error=None if success else f"command exited with code {completed.returncode}",
                meta={"workdir": str(workdir)},
            )
        except FileNotFoundError as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))
        except subprocess.TimeoutExpired as exc:
            stdout = (
                exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", errors="replace")
            )
            stderr = (
                exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", errors="replace")
            )
            truncated_stdout, stdout_truncated = truncate_text(stdout, 50_000)
            truncated_stderr, stderr_truncated = truncate_text(stderr, 50_000)
            return ToolInvokeResult(
                name=self.entity.name,
                success=False,
                error=f"command timed out after {timeout_seconds} seconds",
                data={
                    "command": command,
                    "stdout": truncated_stdout,
                    "stderr": truncated_stderr,
                    "stdout_truncated": stdout_truncated,
                    "stderr_truncated": stderr_truncated,
                },
                meta={"workdir": str(get_workdir())},
            )
        except (OSError, ValueError, WorkspaceToolError) as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))
