import os
from pathlib import Path

from runtime.tool.base.tool_provider import ToolController
from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.entities import ToolEntity
from utils import load_single_subclass_from_source, load_yaml_file


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
                return tool.entity.model_json_schema()
        raise ValueError(f"Tool {tool_name} not found.")

    def load_tools(self) -> list[BuiltinTool]:
        """
        Load all built-in tools.
        This method should be implemented to return a list of all built-in tools.
        """

        tools_dir = os.path.join(os.path.dirname(__file__), "providers")
        tools = []
        yaml_paths = sorted(path for path in Path(tools_dir).rglob("*.yaml") if not path.name.startswith("__"))
        for yaml_path in yaml_paths:
            tool_config = load_yaml_file(str(yaml_path), ignore_error=True, default_value=None)
            if not isinstance(tool_config, dict) or not tool_config:
                continue
            tool_entity = ToolEntity(**tool_config)
            module_stem = yaml_path.stem
            provider_dir = yaml_path.parent.name
            # get tool class, import the module
            assistant_tool_class: type[BuiltinTool] = load_single_subclass_from_source(
                module_name=f"runtime.tool.builtin_tool.providers.{provider_dir}.{module_stem}",
                script_path=str(yaml_path.with_suffix(".py")),
                parent_type=BuiltinTool,
            )
            tools.append(
                assistant_tool_class(
                    entity=tool_entity,
                )
            )
        return tools
