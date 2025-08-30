from enum import StrEnum

from controllers.mcp.streamable_http import MCPServerStreamableHTTPRequestHandler
from fastapi import APIRouter
from pydantic import ValidationError
from starlette.requests import Request

from libs.deps import CurrentApiKeyDep
from models import McpServer
from models.engine import get_db
from runtime.mcp import types
from runtime.mcp.types import ClientRequest, ClientNotification
from runtime.mcp.utils import create_mcp_error_response, compact_generate_response

router = APIRouter(tags=['mcp'],prefix="/mcp")

class McpServerStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@router.api_route(path="/{server_code}", methods=["POST", "GET"])
async def mcp_chat_completions(server_code: str, request: Request, current_key:CurrentApiKeyDep):
    mcp_server: McpServer = None
    with get_db() as session:
        mcp_server = session.query(McpServer).filter(McpServer.server_code == server_code).first()

    json = await request.json()
    request_id = json.get("id", 1)
    if not mcp_server:
        return create_mcp_error_response(request_id,types.INVALID_REQUEST, "Server Not Found")

    if mcp_server.status != McpServerStatus.ACTIVE:
        return create_mcp_error_response(request_id,types.INVALID_REQUEST, "Server is not active")

    try:
        request: ClientRequest | ClientNotification = ClientRequest.model_validate(json)
    except ValidationError as e:
        try:
            notification = ClientNotification.model_validate(json)
            request = notification
        except ValidationError as e:
            return compact_generate_response(
                create_mcp_error_response(request_id, types.INVALID_PARAMS, f"Invalid MCP request: {str(e)}")
            )

    mcp_server_handler = MCPServerStreamableHTTPRequestHandler(request,mcp_server)
    response = mcp_server_handler.handle()
    return compact_generate_response(response)
