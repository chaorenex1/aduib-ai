from abc import ABC, abstractmethod

from .tool import Tool


class ToolController(ABC):

    @abstractmethod
    def get_tool(self, tool_name: str) -> Tool:
        """
        Get a tool by its name.
        :param tool_name: The name of the tool.
        :return: An instance of the tool.
        """
        pass

    @abstractmethod
    def get_tools(self) -> list[Tool]:
        """
        Get tool list
        :return: A list of the tool
        """

    @abstractmethod
    def get_tool_schema(self, tool_name: str) -> dict:
        """
        Get the schema of a tool by its name.
        :param tool_name: The name of the tool.
        :return: A dictionary representing the tool's schema.
        """
        pass