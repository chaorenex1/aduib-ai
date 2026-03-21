from typing import Any

import anyio

from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.entities import ToolInvokeResult
from service.task_job_service import TaskJobError, TaskJobService


class TaskCannelTool(BuiltinTool):
    """
    A tool to cancel background tasks.
    """

    async def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> ToolInvokeResult:
        task_id = tool_parameters.get("task_id")
        if task_id is None:
            return ToolInvokeResult(name=self.entity.name, success=False, error="task_id is required")
        try:
            data = await anyio.to_thread.run_sync(TaskJobService.cancel, int(task_id))
            return ToolInvokeResult(name=self.entity.name, data=data, meta={"message_id": message_id})
        except (TaskJobError, ValueError) as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))
