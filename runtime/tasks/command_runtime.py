from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from runtime.tasks.types import TaskExecutionResult
from runtime.tool.builtin_tool.providers._workspace import (
    DEFAULT_MAX_OUTPUT_CHARS,
    WorkspaceToolError,
    get_workdir,
    relative_to_workdir,
    resolve_workdir_path,
    truncate_text,
)

EXECUTION_TYPES = {"command", "shell_script", "python_script"}


class CommandTaskError(ValueError):
    """Raised when a command-backed task request is invalid."""


def normalize_execution_payload(
    payload: dict[str, Any],
    *,
    script_prefix: str,
) -> dict[str, Any]:
    execution_hint = payload.get("type")
    if execution_hint is None:
        execution_hint = payload.get("execution_type")
    if execution_hint is not None:
        if not isinstance(execution_hint, str) or execution_hint.lower() not in EXECUTION_TYPES:
            raise CommandTaskError("type must be one of command, shell_script, or python_script")
        execution_hint = execution_hint.lower()

    raw_command = payload.get("command")
    script_path_value = payload.get("script_path")
    if script_path_value is not None and (not isinstance(script_path_value, str) or not script_path_value.strip()):
        raise CommandTaskError("script_path must be a non-empty string when provided")

    if execution_hint is None:
        raise CommandTaskError("type is required")

    if execution_hint == "command":
        if not isinstance(raw_command, str) or not raw_command.strip():
            raise CommandTaskError("command is required when type=command")
        if script_path_value:
            raise CommandTaskError("script_path is only valid for shell_script or python_script")
        return {
            "execution_type": "command",
            "command": raw_command.strip(),
            "script_path": None,
        }

    if execution_hint in {"shell_script", "python_script"}:
        if isinstance(raw_command, str) and raw_command.strip():
            relative_script_path = materialize_script(
                execution_type=execution_hint,
                script_content=raw_command,
                script_path=script_path_value,
                script_prefix=script_prefix,
            )
            return {
                "execution_type": execution_hint,
                "command": None,
                "script_path": relative_script_path,
            }
        if script_path_value:
            return {
                "execution_type": execution_hint,
                "command": None,
                "script_path": _resolve_existing_script_path(script_path_value.strip()),
            }
        raise CommandTaskError(f"command or script_path is required when type={execution_hint}")

    raise CommandTaskError("type must be one of command, shell_script, or python_script")


def materialize_script(
    *,
    execution_type: str,
    script_content: str,
    script_path: str | None,
    script_prefix: str,
) -> str:
    if execution_type not in {"shell_script", "python_script"}:
        raise CommandTaskError(f"script materialization is unsupported for {execution_type}")
    if not isinstance(script_content, str) or not script_content.strip():
        raise CommandTaskError(f"{execution_type} content is required")

    suffix = _default_script_suffix(execution_type)
    if script_path:
        _, resolved = resolve_workdir_path(_ensure_script_suffix(script_path.strip(), suffix), allow_missing=True)
    else:
        workdir = get_workdir()
        relative_path = Path(script_prefix) / "scripts" / f"{uuid.uuid4().hex}{suffix}"
        resolved = (workdir / relative_path).resolve(strict=False)

    workdir = get_workdir()
    if not resolved.is_relative_to(workdir):
        raise CommandTaskError("script_path escapes app.workdir")
    if resolved.exists():
        raise CommandTaskError(f"script_path already exists: {relative_to_workdir(resolved, workdir)}")

    resolved.parent.mkdir(parents=True, exist_ok=True)
    normalized_content = script_content.replace("\r\n", "\n")
    resolved.write_text(normalized_content, encoding="utf-8")
    if execution_type == "shell_script" and os.name != "nt":
        resolved.chmod(0o700)
    return relative_to_workdir(resolved, workdir)


def _resolve_existing_script_path(script_path: str) -> str:
    workdir, resolved = resolve_workdir_path(script_path)
    return relative_to_workdir(resolved, workdir)


def run_execution(
    *,
    execution_type: str,
    command: str | None,
    script_path: str | None,
    timeout_seconds: int | None,
) -> TaskExecutionResult:
    if execution_type not in EXECUTION_TYPES:
        raise CommandTaskError(f"unsupported execution_type: {execution_type}")

    workdir = get_workdir()
    argv = _build_argv(execution_type=execution_type, command=command, script_path=script_path)
    timeout = timeout_seconds or 300

    try:
        completed = subprocess.run(
            argv,
            cwd=workdir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
        )
        stdout, stdout_truncated = truncate_text(completed.stdout or "", DEFAULT_MAX_OUTPUT_CHARS)
        stderr, stderr_truncated = truncate_text(completed.stderr or "", DEFAULT_MAX_OUTPUT_CHARS)
        success = completed.returncode == 0
        return TaskExecutionResult(
            success=success,
            output={
                "execution_type": execution_type,
                "command": command,
                "script_path": script_path,
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
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", errors="replace")
        stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", errors="replace")
        truncated_stdout, stdout_truncated = truncate_text(stdout, DEFAULT_MAX_OUTPUT_CHARS)
        truncated_stderr, stderr_truncated = truncate_text(stderr, DEFAULT_MAX_OUTPUT_CHARS)
        return TaskExecutionResult(
            success=False,
            output={
                "execution_type": execution_type,
                "command": command,
                "script_path": script_path,
                "argv": argv,
                "stdout": truncated_stdout,
                "stderr": truncated_stderr,
                "stdout_truncated": stdout_truncated,
                "stderr_truncated": stderr_truncated,
            },
            error=f"command timed out after {timeout} seconds",
            meta={"workdir": str(workdir)},
        )
    except (OSError, ValueError, WorkspaceToolError) as exc:
        return TaskExecutionResult(
            success=False,
            output={
                "execution_type": execution_type,
                "command": command,
                "script_path": script_path,
                "argv": argv,
            },
            error=str(exc),
            meta={"workdir": str(workdir)},
        )


def _build_argv(*, execution_type: str, command: str | None, script_path: str | None) -> list[str]:
    if execution_type == "command":
        if not isinstance(command, str) or not command.strip():
            raise CommandTaskError("command is required when execution_type=command")
        if os.name == "nt":
            return [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ]
        return ["/bin/sh", "-lc", command]

    if not isinstance(script_path, str) or not script_path.strip():
        raise CommandTaskError(f"script_path is required when execution_type={execution_type}")
    _, resolved = resolve_workdir_path(script_path)
    if execution_type == "shell_script":
        if os.name == "nt":
            return [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(resolved),
            ]
        return ["/bin/sh", str(resolved)]
    if execution_type == "python_script":
        return [sys.executable, str(resolved)]
    raise CommandTaskError(f"unsupported execution_type: {execution_type}")


def _default_script_suffix(execution_type: str) -> str:
    if execution_type == "python_script":
        return ".py"
    if execution_type == "shell_script":
        return ".ps1" if os.name == "nt" else ".sh"
    raise CommandTaskError(f"unsupported script execution_type: {execution_type}")


def _ensure_script_suffix(path_value: str, suffix: str) -> str:
    path = Path(path_value)
    if path.suffix:
        return path.as_posix()
    return (path.parent / f"{path.name}{suffix}").as_posix()
