from collections.abc import Generator
from typing import Any, Union

from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.entities import ToolInvokeResult


class WebFetchTool(BuiltinTool):
    """
    A tool to fetch and convert URLs to markdown.
    """

    def _invoke(
        self, tool_parameters: dict[str, Any], message_id: str | None = None
    ) -> Union[ToolInvokeResult, Generator[ToolInvokeResult, None, None]]:
        """
        Invoke tool to fetch URL.
        """
        return ToolInvokeResult(
            name=self.entity.name,
            data="",
            meta={},
        )
