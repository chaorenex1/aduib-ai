from typing import Any

import anyio

from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.entities import ToolInvokeResult
from service.plan_service import PlanService, PlanStateError


class TodoListTool(BuiltinTool):
    """
    A tool to list all todos.
    """

    async def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> ToolInvokeResult:
        try:
            data = await anyio.to_thread.run_sync(PlanService.list_todos, tool_parameters, message_id)
            return ToolInvokeResult(name=self.entity.name, data=data, meta={"message_id": message_id})
        except PlanStateError as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))
