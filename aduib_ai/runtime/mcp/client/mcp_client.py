import logging
import os
import secrets
from datetime import timedelta
from typing import Any, AsyncGenerator
from urllib.parse import parse_qs, urlparse

import requests
from httpx import BasicAuth
from mcp import ClientSession, StdioServerParameters
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.shared.auth import OAuthClientMetadata, OAuthToken, OAuthClientInformationFull
from pydantic import AnyHttpUrl

from component.cache.redis_cache import redis_client
from configs import config
from runtime.tool.entities.tool_entities import CredentialType, McpTransportType

logger=logging.getLogger(__name__)


class RedisTokenStorage(TokenStorage):
    """A token storage implementation using Redis."""

    def __init__(self):
        self.redis_client = redis_client

    async def get_tokens(self) -> OAuthToken | None:
        """Get stored tokens."""
        token_data = self.redis_client.get("mcp_oauth_tokens")
        if token_data:
            return OAuthToken.model_validate_json(token_data)
        return None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        """Store tokens."""
        if tokens.expires_in:
            self.redis_client.setex("mcp_oauth_tokens",timedelta(seconds=tokens.expires_in), tokens.model_dump_json(exclude_none=True))
        else:
            self.redis_client.set("mcp_oauth_tokens", tokens.model_dump_json(exclude_none=True))

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        """Get stored client information."""
        client_info_data = self.redis_client.get("mcp_oauth_client_info")
        if client_info_data:
            return OAuthClientInformationFull.model_validate_json(client_info_data)
        return None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        """Store client information."""
        self.redis_client.set("mcp_oauth_client_info", client_info.model_dump_json(exclude_none=True))

class McpClient:
    """A implementation of an MCP client."""
    def __init__(self, server_url:str,mcp_config:dict[str,Any]):
        self.oauth_auth:Any =None
        self.server_url = server_url
        if server_url.endswith("/"):
            self.server_url = server_url[:-1]
        self.mcp_config = mcp_config
        if self.mcp_config is not None:
            self.authed = mcp_config.get("authed", False)
            self.client_type = McpTransportType.to_original(mcp_config.get("client_type", "streamable"))  # 'streamable' or 'non-streamable'
            self.user_agent = mcp_config.get("user_agent", config.DEFAULT_USER_AGENT)

        if self.authed:
            self._setup_auth_info(mcp_config)
        else:
            self.credential_type = CredentialType.NONE


    def get_client_header(self) -> dict[str,str]:
        """Get the headers for the MCP client."""
        headers = {
            "User-Agent": self.user_agent
        }
        match self.credential_type:
            case CredentialType.BASIC:
                pass
            case CredentialType.API_KEY:
                if self.auth_info["in"] == "header":
                    headers[self.auth_info["name"]] = self.auth_info["api_key"]
                elif self.auth_info["in"] == "query":
                    # For query parameters, we would typically append to the URL, but here we just log a warning
                    logger.warning("API key in query parameters should be added to the URL, not headers.")
            case CredentialType.OAUTH2:
                pass
            case CredentialType.NONE:
                pass
            case _:
                raise ValueError(f"Unsupported credential type: {self.credential_type}")
        return headers

    @classmethod
    def build_client(cls,server_url:str,mcp_config:dict[str,Any]) -> "McpClient":
        """Factory method to create an McpClient instance."""
        return cls(server_url, mcp_config)

    async def get_client_session(self)-> AsyncGenerator[ClientSession, None]:
        """Get an asynchronous context manager for the MCP client session."""
        if self.client_type == McpTransportType.STREAMABLE:
            from mcp.client.streamable_http import streamablehttp_client
            async with streamablehttp_client(self.server_url+"/mcp", headers=self.get_client_header(),
                                             auth=self.oauth_auth) as (read, write, _):
                async with ClientSession(read, write) as session:
                    yield session  # <-- 保证外部能用，退出时自动清理

        elif self.client_type == McpTransportType.SSE:
            from mcp.client.sse import sse_client
            async with sse_client(self.server_url+"/sse", headers=self.get_client_header(), auth=self.oauth_auth) as (read,write,_):
                async with ClientSession(read, write) as session:
                    yield session

        elif self.client_type == McpTransportType.STDIO:
            from mcp.client.stdio import stdio_client
            server_params = StdioServerParameters(
                command="uv",
                args=["run", "server", self.server_url, "stdio"],
                env={"UV_INDEX": os.environ.get("UV_INDEX", "")},
            )
            async with stdio_client(server_params) as (read, write, _):
                async with ClientSession(read, write) as session:
                    yield session

        else:
            raise ValueError(f"Unsupported MCP client type: {self.client_type}")

    def _setup_auth_info(self, mcp_config):
        """Setup authentication information based on the credential type."""
        self.credential_type = CredentialType.to_original(mcp_config.get("credential_type", "none"))
        match self.credential_type:
            case CredentialType.NONE:
                self.auth_info = None
            case CredentialType.BASIC:
                self.auth_info = {
                    "username": mcp_config.get("username", ""),
                    "password": mcp_config.get("password", "")
                }
                self.oauth_auth = BasicAuth(self.auth_info["username"], self.auth_info["password"])
            case CredentialType.OAUTH2:
                self.auth_info = {
                    "client_id": mcp_config.get("client_id", ""),
                    "client_secret": mcp_config.get("client_secret", ""),
                    "client_name": mcp_config.get("client_name", "MCP Client"),
                    "authorization_url": mcp_config.get("authorization_url", ""),
                    "redirect_uri": mcp_config.get("redirect_uri", ""),
                    "state": mcp_config.get("state", secrets.token_urlsafe(16)),
                    "scopes": mcp_config.get("scopes", ["user"]),
                }

                self.oauth_auth = OAuthClientProvider(
                    server_url=self.auth_info["authorization_url"],
                    client_metadata=OAuthClientMetadata(
                        client_name=self.auth_info["client_id"],
                        redirect_uris=[AnyHttpUrl(self.auth_info["redirect_uri"])],
                        grant_types=["authorization_code", "refresh_token"],
                        response_types=["code"],
                        scope=self.auth_info.get("scopes", ["user"]),
                    ),
                    storage=RedisTokenStorage(),
                    redirect_handler=self.handle_redirect,
                    callback_handler=self.handle_callback,
                )
            case CredentialType.API_KEY:
                self.auth_info = {
                    "api_key": mcp_config.get("api_key", ""),
                    "in": mcp_config.get("in", "header"),  # 'header' or 'query'
                    "name": mcp_config.get("name", "X-API-KEY"),  # Header or query parameter name
                }
            case _:
                raise ValueError(f"Unsupported credential type: {self.credential_type}")

    async def handle_redirect(self,auth_url: str) -> None:
        logger.debug(auth_url)
        redirect_url= requests.get(url=auth_url, headers={"User-Agent": self.user_agent}).text
        logger.debug(f"Redirect URL: {redirect_url}")
        redis_client.setex("mcp_oauth_redirect_url",timedelta(seconds=10), redirect_url)


    async def handle_callback(self) -> tuple[str, str | None]:
        logger.debug("Waiting for authorization...")
        callback_url = redis_client.get("mcp_oauth_redirect_url")
        params = parse_qs(urlparse(callback_url).query)
        return params["code"][0], params.get("state", [None])[0]