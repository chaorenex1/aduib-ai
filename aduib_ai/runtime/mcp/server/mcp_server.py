import json
import logging
import uuid
from typing import cast

from sqlalchemy import select, func

from configs import config
from models import McpServer
from models.engine import get_db
from models.user import EndUser
from runtime.mcp import types
from runtime.mcp.types import METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL_ERROR
from runtime.mcp.utils import create_mcp_error_response
from runtime.tool.mcp.tool_provider import McpToolController
from utils import jsonable_encoder

logger = logging.getLogger(__name__)


class MCPServerStreamableHTTPRequestHandler:
    def __init__(
        self, request: types.ClientRequest | types.ClientNotification,mcp_server: McpServer,
    ):
        self.request = request
        self.mcp_server= mcp_server
        self.end_user = self.retrieve_end_user()
        self.mcp_tool_controller=McpToolController(server_url=self.mcp_server.server_url)

    @property
    def request_type(self):
        return type(self.request.root)

    @property
    def parameter_schema(self,parameters: dict | None = None, required: list | None = None):
        return {
                "type": "object",
                "properties": parameters,
                "required": required,
            }

    @property
    def capabilities(self):
        return types.ServerCapabilities(
            tools=types.ToolsCapability(listChanged=False),
        )

    def response(self, response: types.Result | str):
        if isinstance(response, str):
            sse_content = f"event: ping\ndata: {response}\n\n".encode()
            yield sse_content
            return
        json_response = types.JSONRPCResponse(
            jsonrpc="2.0",
            id=(self.request.root.model_extra or {}).get("id", 1),
            result=response.model_dump(by_alias=True, mode="json", exclude_none=True),
        )
        json_data = json.dumps(jsonable_encoder(json_response))

        sse_content = f"event: message\ndata: {json_data}\n\n".encode()

        yield sse_content

    def error_response(self, code: int, message: str, data=None):
        request_id = (self.request.root.model_extra or {}).get("id", 1) or 1
        return create_mcp_error_response(request_id, code, message, data)

    def handle(self):
        handle_map = {
            types.InitializeRequest: self.initialize,
            types.ListToolsRequest: self.list_tools,
            types.CallToolRequest: self.invoke_tool,
            types.InitializedNotification: self.handle_notification,
            types.PingRequest: self.handle_ping,
        }
        try:
            if self.request_type in handle_map:
                return self.response(handle_map[self.request_type]())
            else:
                return self.error_response(METHOD_NOT_FOUND, f"Method not found: {self.request_type}")
        except ValueError as e:
            logger.exception("Invalid params")
            return self.error_response(INVALID_PARAMS, str(e))
        except Exception as e:
            logger.exception("Internal server error")
            return self.error_response(INTERNAL_ERROR, f"Internal server error: {str(e)}")

    def handle_notification(self):
        return "ping"

    def handle_ping(self):
        return types.EmptyResult()

    def initialize(self):
        request = cast(types.InitializeRequest, self.request.root)
        client_info = request.params.clientInfo
        client_name = f"{client_info.name}@{client_info.version}"
        if not self.end_user:
            with get_db() as session:
                end_user = EndUser(
                    type="mcp",
                    name=client_name,
                    session_id=self.generate_session_id(),
                    external_user_id=self.mcp_server.id,
                )
                session.add(end_user)
                session.commit()
        return types.InitializeResult(
            protocolVersion=types.LATEST_PROTOCOL_VERSION,
            capabilities=self.capabilities,
            serverInfo=types.Implementation(name="AduibAI", version=config.APP_VERSION),
            instructions=self.mcp_server.description,
        )

    def list_tools(self):
        if not self.end_user:
            raise ValueError("User not found")
        tools = self.mcp_tool_controller.get_tools()
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name=tool.entity.name,
                    description=tool.entity.description,
                    inputSchema=tool.entity.parameters,
                ) for tool in tools
            ],
        )

    def invoke_tool(self):
        if not self.end_user:
            raise ValueError("User not found")
        request = cast(types.CallToolRequest, self.request.root)
        params = request.params
        tool_invoke_result=self.mcp_tool_controller.get_tool(params.name).invoke(tool_parameters=params.arguments,message_id="")
        for result in tool_invoke_result:
            if result.success:
                return types.CallToolResult(content=[result.data],_meta=result.meta)
            else:
                return types.ErrorData(message=result.error,code=-32603)

    def retrieve_end_user(self):
        with get_db() as session:
            return (
                session.query(EndUser)
                .where(EndUser.external_user_id == self.mcp_server.id, EndUser.type == "mcp")
                .first()
            )

    def generate_session_id(self):
        """
        Generate a unique session ID.
        """
        while True:
            with get_db() as session:
                session_id = str(uuid.uuid4())
                existing_count = session.scalar(
                    select(func.count()).select_from(EndUser).where(EndUser.session_id == session_id)
                )
                if existing_count == 0:
                    return session_id