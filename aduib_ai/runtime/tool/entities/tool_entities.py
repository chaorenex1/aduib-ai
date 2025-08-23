from enum import StrEnum
from typing import Optional, Union

from pydantic import BaseModel


class ToolProviderType(StrEnum):
    """
    Enum for tool provider types.
    """
    BUILTIN = "builtin"
    API = "api"
    MCP = "mcp"

    @classmethod
    def value_of(cls, value: str) -> "ToolProviderType":
        for mode in cls:
            if mode.value == value:
                return mode
        raise ValueError(f"Invalid ToolProviderType value: {value}")


class CredentialType(StrEnum):
    """
    Enum for credential types.
    """
    NONE = "none"
    BASIC = "basic"
    OAUTH2 = "oauth2"
    API_KEY= "api_key"



class ToolEntity(BaseModel):
    """
    Base class for tool entities.
    """
    name: str= ""
    description: str = ""
    configs: dict = {}
    parameters: Optional[dict] = None
    icon: str = ""
    provider: str = ""
    type: ToolProviderType = ToolProviderType.BUILTIN
    credentials: CredentialType = CredentialType.NONE



class ToolInvokeResult(BaseModel):
    name: str = ""
    data: Optional[Union[dict, str, list,bytes]] = None
    success: bool = True
    error: Optional[str] = None
    meta: Optional[dict] = None
