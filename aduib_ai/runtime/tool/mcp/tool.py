from typing import Any, Union, Generator

from ..base.tool import Tool, ToolInvokeResult
from ..entities import ToolProviderType


class McpTool(Tool):
    """MCP Tool class"""

    def tool_provider_type(self) -> ToolProviderType:
        return ToolProviderType.MCP

    def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> Union[
        ToolInvokeResult, Generator[ToolInvokeResult, None, None]]:
        """Invoke the tool with the given parameters."""