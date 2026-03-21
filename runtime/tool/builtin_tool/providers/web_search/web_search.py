from collections.abc import Generator
from typing import Any, Union

from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.entities import ToolInvokeResult


class WebSearchTool(BuiltinTool):
    """
    A tool to search the web.
    """

    def _invoke(
        self, tool_parameters: dict[str, Any], message_id: str | None = None
    ) -> Union[ToolInvokeResult, Generator[ToolInvokeResult, None, None]]:
        """
        Invoke tool to search web.
        """
        return ToolInvokeResult(
            name=self.entity.name,
            data="",
            meta={},
        )
