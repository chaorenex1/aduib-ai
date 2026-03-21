import json

from models import ToolInfo, get_db
from runtime.tool.base.tool import Tool
from runtime.tool.base.tool_provider import ToolController
from runtime.tool.entities import ToolEntity, ToolProviderType
from runtime.tool.entities.tool_entities import CredentialType
from runtime.tool.mcp.fast_mcp_instance import fast_mcp
from runtime.tool.mcp.tool import McpTool


class McpToolController(ToolController):
    """
    A controller for managing MCP tools.
    """

    local_tools: list[McpTool] = []
    remote_tools: list[McpTool] = []
    tools: list[McpTool] = []

    def __init__(self):
        self.remote_tools = self.local_db_tools()
        self.tools = self.local_tools + self.remote_tools

    def get_tool(self, tool_name: str) -> Tool | None:
        """Retrieves a tool by its name."""
        for tool in self.tools:
            if tool.entity.name == tool_name:
                return tool
        return None

    def get_tools(self, filter_names=None) -> list[Tool]:
        """Retrieves all available tools."""
        if filter_names is None:
            filter_names = []
        if filter_names:
            return [tool for tool in self.tools if tool.entity.name in filter_names]
        return self.tools

    def local_db_tools(self):
        """Loads remote MCP tools from configured MCP servers."""
        mcp_tools: list[McpTool] = []
        with get_db() as session:
            remote_tools = session.query(ToolInfo).filter(ToolInfo.type == ToolProviderType.MCP.value).all()
            if remote_tools:
                for tool_info in remote_tools:
                    mcp_tool = McpTool(
                        entity=ToolEntity(
                            name=tool_info.name,
                            description=tool_info.description,
                            parameters=json.loads(tool_info.parameters),
                            configs=json.loads(tool_info.configs),
                            type=ToolProviderType.to_original(tool_info.type)
                            if tool_info.type
                            else ToolProviderType.MCP,
                            provider=tool_info.provider,
                            credentials=CredentialType.to_original(tool_info.credentials)
                            if tool_info.credentials
                            else CredentialType.NONE,
                        ),
                        server_url=tool_info.mcp_server_url,
                    )
                    mcp_tools.append(mcp_tool)

        return mcp_tools
