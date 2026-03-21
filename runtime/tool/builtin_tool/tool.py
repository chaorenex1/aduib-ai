from abc import abstractmethod
from collections.abc import Generator
from typing import Any, Union

from ..base.tool import Tool, ToolInvokeResult
from ..entities import ToolEntity, ToolProviderType


class BuiltinTool(Tool):
    """
    The base class of a builtin tool
    """

    def __init__(self, entity: ToolEntity):
        super().__init__(entity)
        self.entity = entity

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
