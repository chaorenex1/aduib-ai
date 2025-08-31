import logging
from datetime import timedelta
from typing import Any, Union, Generator

from utils import AsyncUtils
from ..base.tool import Tool, ToolInvokeResult
from ..entities import ToolProviderType, ToolEntity

logger=logging.getLogger(__name__)


class McpTool(Tool):
    """MCP Tool class"""
    def __init__(self, server_url: str, entity: ToolEntity):
        super().__init__(entity=entity)
        self.server_url = server_url

    def tool_provider_type(self) -> ToolProviderType:
        return ToolProviderType.MCP

    def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> Union[
        ToolInvokeResult, Generator[ToolInvokeResult, None, None]]:
        """Invoke the tool with the given parameters."""

        if self.entity.is_local():
            from .tool_provider import fast_mcp

            try:
                async def invoke_tool():
                    from mcp.types import TextContent,ImageContent,EmbeddedResource
                    async with await fast_mcp.call_tool(self.entity.name, tool_parameters) as result:
                        if isinstance(result, TextContent):
                            from runtime.mcp.types import TextContent
                            return ToolInvokeResult(name=self.entity.name, data=TextContent.model_validate(result.model_dump(exclude_none=True)))
                        elif isinstance(result, ImageContent):
                            from runtime.mcp.types import ImageContent
                            return ToolInvokeResult(name=self.entity.name, data=ImageContent.model_validate(result.model_dump(exclude_none=True)))
                        elif isinstance(result, EmbeddedResource):
                            from runtime.mcp.types import EmbeddedResource
                            return ToolInvokeResult(name=self.entity.name, data=EmbeddedResource.model_validate(result.model_dump(exclude_none=True)))
                        else:
                            return ToolInvokeResult(name=self.entity.name, data=result.model_dump(exclude_none=True))
                return AsyncUtils.run_async(invoke_tool)
            except Exception as e:
                logger.error(f"Failed to invoke tool: {e}")
                return ToolInvokeResult(name=self.entity.name, error=f"Error: {str(e)}", success=False,meta=tool_parameters)
        else:
            try:
                from runtime.mcp.client.mcp_client import McpClient
                self.entity.configs['credential_type'] = self.entity.credentials.value()
                client = McpClient.build_client(server_url=self.server_url,mcp_config=self.entity.configs)
                async def invoke_tool():
                    from mcp.types import TextContent,ImageContent,EmbeddedResource
                    async with client.get_client_session() as client_session:
                        result=await client_session.call_tool(self.entity.name, tool_parameters, read_timeout_seconds=timedelta(seconds=60))
                        if isinstance(result, TextContent):
                            from runtime.mcp.types import TextContent
                            return ToolInvokeResult(name=self.entity.name, data=TextContent.model_validate(result.model_dump(exclude_none=True)))
                        elif isinstance(result, ImageContent):
                            from runtime.mcp.types import ImageContent
                            return ToolInvokeResult(name=self.entity.name, data=ImageContent.model_validate(result.model_dump(exclude_none=True)))
                        elif isinstance(result, EmbeddedResource):
                            from runtime.mcp.types import EmbeddedResource
                            return ToolInvokeResult(name=self.entity.name, data=EmbeddedResource.model_validate(result.model_dump(exclude_none=True)))
                        else:
                            return ToolInvokeResult(name=self.entity.name, data=result.model_dump(exclude_none=True))
                return AsyncUtils.run_async(invoke_tool)
            except Exception as e:
                logger.error(f"Failed to invoke remote MCP tool: {e}")
                return ToolInvokeResult(name=self.entity.name, error=f"Error: {str(e)}", success=False,meta=tool_parameters)

