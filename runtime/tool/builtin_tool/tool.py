from abc import abstractmethod
from typing import Any, Union, Generator

from ..base.tool import Tool, ToolInvokeResult
from ..entities import ToolProviderType


class BuiltinTool(Tool):
    """
    The base class of a builtin tool
    """

    def tool_provider_type(self) -> ToolProviderType:
        """
        Get the tool provider type.

        :return: The tool provider type, which is always ToolProviderType.BUILTIN for builtin tools.
        """
        return ToolProviderType.BUILTIN

    @abstractmethod
    def _invoke(
        self, tool_parameters: dict[str, Any], message_id: str | None = None
    ) -> Union[ToolInvokeResult, Generator[ToolInvokeResult, None, None]]:
        """
        Invoke the tool with the given parameters.
        """
