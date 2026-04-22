import json
from typing import Optional

from fastapi import APIRouter

from controllers.common.base import ApiHttpException, api_endpoint
from controllers.common.error import ServiceError
from controllers.params import MCPServerCreate, MCPServerUpdate
from models import McpServer, get_db
from runtime.mcp.client.mcp_client import McpClient
from utils import generate_string

router = APIRouter(tags=["mcp_server"], prefix="/mcp_server")


# Create
@router.post("/servers/")
@api_endpoint()
def create_server(server: MCPServerCreate):
    with get_db() as db:
        db_server = McpServer(**server.model_dump(exclude_none=True))
        db_server.server_code = generate_string(16)
        db.add(db_server)
        db.commit()
        db.refresh(db_server)
        return db_server


# Read all
@router.get("/servers/")
@api_endpoint()
def read_servers(skip: int = 0, limit: int = 100):
    with get_db() as db:
        servers = db.query(McpServer).offset(skip).limit(limit).all()
        return servers


# Read one
@router.get("/servers/{server_id}")
@api_endpoint()
def read_server(server_id: str):
    with get_db() as db:
        server = db.query(McpServer).filter(McpServer.id == server_id).first()
        if not server:
            raise ServiceError(message="server not found")
        return server


# Update
@router.put("/servers/{server_id}")
@api_endpoint()
def update_server(server_id: str, server_update: MCPServerUpdate):
    with get_db() as db:
        server = db.query(McpServer).filter(McpServer.id == server_id).first()
        if not server:
            raise ServiceError(message="server not found")

        update_data = server_update.model_dump(exclude_none=True)
        for key, value in update_data.items():
            setattr(server, key, value)

        db.commit()
        db.refresh(server)
        return server


# Delete
@router.delete("/servers/{server_id}")
@api_endpoint()
def delete_server(server_id: str):
    with get_db() as db:
        server = db.query(McpServer).filter(McpServer.id == server_id).first()
        if not server:
            raise ServiceError(message="server not found")

        db.delete(server)
        db.commit()
        return {"deleted": True, "server_id": server_id}


@router.get("/init_tools/{server_code}")
@api_endpoint()
async def init_tools(server_code: str):
    with get_db() as db:
        mcp_server: Optional[McpServer] = db.query(McpServer).filter(McpServer.server_code == server_code).first()
        if not mcp_server:
            raise ServiceError(message="server not found")

        mcp_config = json.loads(mcp_server.configs)
        mcp_config["credential_type"] = mcp_server.credentials
        mcp_client = McpClient.build_client(mcp_server.server_url, mcp_config)
        try:
            async with mcp_client.get_client_session() as client_session:
                tools_response = await client_session.list_tools()
                if tools_response is None:
                    raise ServiceError(message="failed to fetch tools from mcp server")

                from models import ToolInfo
                from runtime.tool.mcp.tool_provider import ToolProviderType

                tools_infos: list[ToolInfo] = []
                for tool in tools_response.tools:
                    print(tool)
                    tool_info = ToolInfo(
                        name=tool.name,
                        description=tool.description,
                        parameters=json.dumps(tool.inputSchema),
                        type=ToolProviderType.MCP,
                        provider=mcp_server.name,
                        credentials=mcp_server.credentials,
                        configs=mcp_server.configs,
                        mcp_server_url=mcp_server.server_url,
                    )
                    existing_tool = (
                        db.query(ToolInfo)
                        .filter(ToolInfo.name == tool.name, ToolInfo.provider == mcp_server.name)
                        .first()
                    )
                    if existing_tool:
                        tool_info.id = existing_tool.tool_id

                    tools_infos.append(tool_info)
                db.bulk_save_objects(tools_infos)
                db.commit()
            return mcp_server
        except Exception as e:
            raise ApiHttpException(
                status_code=500,
                code="mcp_tool_init_failed",
                message=f"failed to fetch tools from mcp server: {e}",
            )


@router.post("/init_servers/")
@api_endpoint()
async def init_servers(server: MCPServerCreate):
    with get_db() as db:
        existing_server = db.query(McpServer).filter(McpServer.server_url == server.server_url).first()
        if existing_server:
            raise ServiceError(message="server already exists")

        db_server = McpServer(**server.model_dump(exclude_none=True))
        db_server.server_code = generate_string(16)
        db.add(db_server)
        db.commit()
        db.refresh(db_server)

        mcp_config = json.loads(server.configs)
        mcp_config["credential_type"] = db_server.credentials
        mcp_client = McpClient.build_client(db_server.server_url, mcp_config)
        try:
            async with mcp_client.get_client_session() as client_session:
                tools_response = await client_session.list_tools()
                if tools_response is None:
                    raise ServiceError(message="failed to fetch tools from mcp server")

                from models import ToolInfo
                from runtime.tool.mcp.tool_provider import ToolProviderType

                tools_infos: list[ToolInfo] = []
                for tool in tools_response.tools:
                    print(tool)
                    tool_info = ToolInfo(
                        name=tool.name,
                        description=tool.description,
                        parameters=json.dumps(tool.inputSchema),
                        type=ToolProviderType.MCP,
                        provider=db_server.name,
                        credentials=db_server.credentials,
                        configs=db_server.configs,
                        mcp_server_url=db_server.server_url,
                    )
                    existing_tool = (
                        db.query(ToolInfo)
                        .filter(ToolInfo.name == tool.name, ToolInfo.provider == db_server.name)
                        .first()
                    )
                    if existing_tool:
                        tool_info.id = existing_tool.tool_id

                    tools_infos.append(tool_info)
                db.bulk_save_objects(tools_infos)
                db.commit()
            return db_server
        except Exception as e:
            db.delete(db_server)
            db.commit()
            raise ApiHttpException(
                status_code=500,
                code="mcp_server_init_failed",
                message=f"failed to fetch tools from mcp server: {e}",
            )
