import logging
from collections.abc import Generator
from datetime import timedelta
from typing import Any, Union

import mcp.types as mcp_types

import runtime.mcp.types as runtime_mcp_types

from ..base.tool import Tool, ToolInvokeResult
from ..entities import ToolEntity, ToolProviderType

logger = logging.getLogger(__name__)


class McpTool(Tool):
    """MCP Tool class"""

    def __init__(self, server_url: str, entity: ToolEntity):
        super().__init__(entity=entity)
        self.server_url = server_url

    def tool_provider_type(self) -> ToolProviderType:
        return ToolProviderType.MCP

    async def _invoke(
        self, tool_parameters: dict[str, Any], message_id: str | None = None
    ) -> Union[ToolInvokeResult, Generator[ToolInvokeResult, None, None]]:
        """Invoke the tool with the given parameters."""
        if self.entity.is_local():
            from .tool_provider import fast_mcp

            try:
                result = await fast_mcp.call_tool(self.entity.name, tool_parameters)
                return ToolInvokeResult(
                    name=self.entity.name, data=self.convert_content(result.content), meta=result.meta
                )
            except Exception as e:
                logger.exception("Failed to invoke tool: {e}")
                return ToolInvokeResult(
                    name=self.entity.name, error=f"Error: {str(e)}", success=False, meta=tool_parameters
                )
        else:
            try:
                from runtime.mcp.client.mcp_client import McpClient

                self.entity.configs["credential_type"] = self.entity.credentials
                client = McpClient.build_client(server_url=self.server_url, mcp_config=self.entity.configs)

                tool_result = None
                async for client_session in client.get_client_session():
                    await client_session.initialize()
                    tool_result = await client_session.call_tool(
                        self.entity.name, tool_parameters, read_timeout_seconds=timedelta(seconds=60)
                    )
                return ToolInvokeResult(
                    name=self.entity.name, data=self.convert_content(tool_result.content), meta=tool_result.meta
                )

            except Exception as e:
                logger.exception("Failed to invoke remote MCP tool: {e}")
                return ToolInvokeResult(
                    name=self.entity.name, error=f"Error: {str(e)}", success=False, meta=tool_parameters
                )

    def convert_content(
        self, content: list[mcp_types.TextContent | mcp_types.ImageContent | mcp_types.EmbeddedResource]
    ) -> list[runtime_mcp_types.TextContent | runtime_mcp_types.ImageContent | runtime_mcp_types.EmbeddedResource]:
        """Convert MCP content to runtime MCP content."""
        converted_content = []
        for item in content:
            if isinstance(item, mcp_types.TextContent):
                converted_content.append(runtime_mcp_types.TextContent(text=item.text, type=item.type))
            elif isinstance(item, mcp_types.ImageContent):
                converted_content.append(
                    runtime_mcp_types.ImageContent(data=item.data, mimeType=item.mimeType, type=item.type)
                )
            elif isinstance(item, mcp_types.EmbeddedResource):
                converted_content.append(
                    runtime_mcp_types.EmbeddedResource(
                        type=item.type,
                        resource=runtime_mcp_types.TextResourceContents(text=item.resource.text)
                        if isinstance(item.resource, mcp_types.TextResourceContents)
                        else runtime_mcp_types.BlobResourceContents(
                            blob=item.resource.blob, mimeType=item.resource.mimeType, uri=item.resource.uri
                        ),
                    )
                )
        return converted_content
