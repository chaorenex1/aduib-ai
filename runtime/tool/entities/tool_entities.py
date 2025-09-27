from enum import StrEnum
from typing import Optional, Union

from pydantic import BaseModel

from runtime.mcp.types import TextContent, ImageContent, EmbeddedResource, BlobResourceContents, TextResourceContents


class McpTransportType(StrEnum):
    """
    Enum for MCP transport types.
    """

    STDIO = "stdio"
    SSE = "sse"
    STREAMABLE = "streamable"

    @classmethod
    def value_of(cls, value: str) -> "McpTransportType":
        for mode in cls:
            if mode.value == value:
                return mode
        raise ValueError(f"Invalid McpTransportType value: {value}")

    @classmethod
    def to_original(cls, type: str) -> "McpTransportType":
        if type == "stdio":
            return cls.STDIO
        elif type == "sse":
            return cls.SSE
        elif type == "streamable":
            return cls.STREAMABLE
        else:
            raise ValueError(f"Invalid McpTransportType value: {type}")


class ToolProviderType(StrEnum):
    """
    Enum for tool provider types.
    """

    BUILTIN = "builtin"
    API = "api"
    MCP = "mcp"
    local = "local"

    @classmethod
    def value_of(cls, value: str) -> "ToolProviderType":
        for mode in cls:
            if mode.value == value:
                return mode
        raise ValueError(f"Invalid ToolProviderType value: {value}")

    @classmethod
    def to_original(cls, type: str) -> "ToolProviderType":
        if type == "builtin":
            return cls.BUILTIN
        elif type == "api":
            return cls.API
        elif type == "mcp":
            return cls.MCP
        elif type == "local":
            return cls.local
        else:
            raise ValueError(f"Invalid ToolProviderType value: {type}")


class CredentialType(StrEnum):
    """
    Enum for credential types.
    """

    NONE = "none"
    BASIC = "basic"
    OAUTH2 = "oauth2"
    API_KEY = "api_key"

    @classmethod
    def to_original(cls, credential: str) -> "CredentialType":
        if credential == "none":
            return cls.NONE
        elif credential == "basic":
            return cls.BASIC
        elif credential == "oauth2":
            return cls.OAUTH2
        elif credential == "api_key":
            return cls.API_KEY
        else:
            raise ValueError(f"Invalid CredentialType value: {credential}")


class ToolEntity(BaseModel):
    """
    Base class for tool entities.
    """

    name: str = ""
    description: str = ""
    configs: dict = {}
    parameters: Optional[dict] = None
    icon: str = ""
    provider: str = ""
    type: ToolProviderType = ToolProviderType.BUILTIN
    credentials: CredentialType = CredentialType.NONE

    def is_local(self) -> bool:
        return self.type == ToolProviderType.local


class ToolInvokeResult(BaseModel):
    name: str = ""
    data: Optional[Union[dict, str, list, bytes, TextContent, ImageContent, EmbeddedResource]] = None
    success: bool = True
    error: Optional[str] = None
    meta: Optional[dict] = None


    def to_normal(self) -> str | None:
        if isinstance(self.data, dict):
            import json

            return json.dumps(self.data, ensure_ascii=False)
        elif isinstance(self.data, list):
            import json

            return json.dumps(self.data, ensure_ascii=False)
        elif isinstance(self.data, bytes):
            return self.data.decode("utf-8", errors="ignore")
        elif isinstance(self.data, TextContent):
            return self.data.text
        elif isinstance(self.data, ImageContent):
            return self.data.data
        elif isinstance(self.data, EmbeddedResource):
            if isinstance(self.data.resource,BlobResourceContents):
                return self.data.resource.blob
            elif isinstance(self.data.resource,TextResourceContents):
                return self.data.resource.text
        elif isinstance(self.data, str):
            return self.data
        else:
            return str(self.data) if self.data is not None else ""
