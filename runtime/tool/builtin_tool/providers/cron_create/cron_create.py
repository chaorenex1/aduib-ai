from typing import Any

import anyio

from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.entities import ToolInvokeResult
from service.cron_job_service import CronJobError, CronJobService


class CronCreateTool(BuiltinTool):
    """
    A tool to create scheduled tasks.
    """

    async def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> ToolInvokeResult:
        try:
            data = await anyio.to_thread.run_sync(CronJobService.create, tool_parameters, message_id)
            return ToolInvokeResult(name=self.entity.name, data=data, meta={"message_id": message_id})
        except CronJobError as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))
