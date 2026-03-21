from __future__ import annotations

from runtime.tasks.command_runtime import run_execution
from runtime.tasks.types import TaskExecutionResult


class TaskDispatcher:
    def __init__(self) -> None:
        pass

    async def dispatch(self, task_job) -> TaskExecutionResult:
        execution_type = (task_job.execution_type or "").lower()
        if execution_type == "command":
            return await self._dispatch_command(task_job)
        if execution_type == "shell_script":
            return await self._dispatch_shell_script(task_job)
        if execution_type == "python_script":
            return await self._dispatch_python_script(task_job)
        raise ValueError(f"unsupported execution_type: {task_job.execution_type}")

    async def _dispatch_command(self, task_job) -> TaskExecutionResult:
        return run_execution(
            execution_type="command",
            command=task_job.command,
            script_path=task_job.script_path,
            timeout_seconds=task_job.timeout_seconds,
        )

    async def _dispatch_shell_script(self, task_job) -> TaskExecutionResult:
        return run_execution(
            execution_type="shell_script",
            command=task_job.command,
            script_path=task_job.script_path,
            timeout_seconds=task_job.timeout_seconds,
        )

    async def _dispatch_python_script(self, task_job) -> TaskExecutionResult:
        return run_execution(
            execution_type="python_script",
            command=task_job.command,
            script_path=task_job.script_path,
            timeout_seconds=task_job.timeout_seconds,
        )
