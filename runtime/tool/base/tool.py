from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import Any, Union

from runtime.tool.entities import ToolEntity, ToolInvokeResult, ToolProviderType


class Tool(ABC):
    """
    The base class of a tool
    """

    def __init__(self, entity: ToolEntity) -> None:
        self.entity = entity

    @abstractmethod
    def tool_provider_type(self) -> ToolProviderType:
        """
        Get the tool provider type

        :return: the tool provider type
        """
        pass

    def get_tool_schema(self) -> dict[str, Any]:
        """
        Get the tool schema

        :return: the tool schema
        """
        return self.entity.get_schema()

    async def invoke(
        self,
        tool_parameters: dict[str, Any],
        message_id: str | None = None,
    ) -> Generator[ToolInvokeResult, None, None]:
        """
        Invoke the tool with the given parameters.
        :param tool_parameters: the parameters for the tool
        :param message_id: the message id for the tool invocation
        :return: the result of the tool invocation
        """
        result = await self._invoke(tool_parameters=tool_parameters, message_id=message_id)

        if isinstance(result, ToolInvokeResult):

            def generator() -> Generator[ToolInvokeResult, None, None]:
                yield result

            return generator()
        else:
            return result

    @abstractmethod
    async def _invoke(
        self,
        tool_parameters: dict[str, Any],
        message_id: str | None = None,
    ) -> Union[ToolInvokeResult, Generator[ToolInvokeResult, None, None]]:
        """
        Internal method to invoke the tool.
        :param tool_parameters: the parameters for the tool
        :param message_id: the message id for the tool invocation
        :return: the result of the tool invocation
        """
        pass

    def get_tool_schema(self) -> dict[str, Any]:
        """
        Convert the tool to a dictionary.
        :return: the tool as a dictionary
        """
        return {
            "name": self.entity.name,
            "description": self.entity.description,
            "parameters": self.entity.parameters,
        }
