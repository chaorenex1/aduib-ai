import os

from runtime.tool.base.tool_provider import ToolController
from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.entities import ToolEntity
from utils import load_single_subclass_from_source, load_yaml_files


class BuiltinToolController(ToolController):
    """
    A controller for managing built-in tools.
    This controller provides methods to access and manage built-in tools.
    """

    tools: list[BuiltinTool] = []

    def __init__(self) -> None:
        super().__init__()
        self.tools = self.load_tools()

    def get_tool(self, tool_name: str) -> BuiltinTool:
        """
        Get a specific built-in tool by its name.
        This method should be implemented to return the tool instance.
        """
        for tool in self.tools:
            if tool.entity.name == tool_name:
                return tool
        return None

    def get_tools(self, filter_names: list[str] = None) -> list[BuiltinTool]:
        """
        Get all built-in tools.
        This method should be implemented to return a list of all built-in tools.
        """
        if filter_names:
            return [tool for tool in self.tools if tool.entity.name in filter_names]
        return self.tools

    def get_tool_schema(self, tool_name: str) -> dict:
        """
        Get the schema of a specific built-in tool.
        This method should be implemented to return the schema of the specified tool.
        """
        for tool in self.tools:
            if tool.entity.name == tool_name:
                return
        raise ValueError(f"Tool {tool_name} not found.")

    def load_tools(self) -> list[BuiltinTool]:
        """
        Load all built-in tools.
        This method should be implemented to return a list of all built-in tools.
        """

        tools_dir = os.path.join(os.path.dirname(__file__), "providers")
        tools_yamls = load_yaml_files(tools_dir)
        tool_entities = []
        tools = []
        if tools_yamls:
            tool_entities = [ToolEntity(**tool) for tool in tools_yamls]
        for tool_entity in tool_entities:
            # get tool class, import the module
            assistant_tool_class: type[BuiltinTool] = load_single_subclass_from_source(
                module_name=f"runtime.tool.builtin_tool.providers.{tool_entity.name}.{tool_entity.name}",
                script_path=os.path.join(
                    os.path.dirname(os.path.realpath(__file__)),
                    # "builtin_tool",
                    "providers",
                    tool_entity.name,
                    f"{tool_entity.name}.py",
                ),
                parent_type=BuiltinTool,
            )
            tools.append(
                assistant_tool_class(
                    entity=tool_entity,
                )
            )
        return tools
