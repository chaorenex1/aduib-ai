from typing import Any

from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.entities import ToolInvokeResult
from service.capability_lookup_service import CapabilityLookupError, CapabilityLookupService


class CapabilityLookupTool(BuiltinTool):
    """
    A tool to look up available capabilities.
    """

    async def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> ToolInvokeResult:
        try:
            data = await CapabilityLookupService.lookup(tool_parameters, message_id)
            return ToolInvokeResult(name=self.entity.name, data=data, meta={"message_id": message_id})
        except CapabilityLookupError as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))
