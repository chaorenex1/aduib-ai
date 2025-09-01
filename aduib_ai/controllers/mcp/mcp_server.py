import json
from typing import Optional

from fastapi import APIRouter

from controllers.common.base import BaseResponse
from controllers.common.error import ServiceError
from controllers.params import MCPServerCreate, MCPServerUpdate
from models import McpServer, get_db
from runtime.mcp.client.mcp_client import McpClient
from utils import generate_string

router = APIRouter(tags=['mcp_server'],prefix="/mcp_server")

# Create
@router.post("/servers/")
def create_server(server: MCPServerCreate):
    with get_db() as db:
        db_server = McpServer(**server.model_dump(exclude_none=True))
        db_server.server_code = generate_string(16)
        db.add(db_server)
        db.commit()
        db.refresh(db_server)
        return BaseResponse.ok(data=db_server)


# Read all
@router.get("/servers/")
def read_servers(skip: int = 0, limit: int = 100):
    with get_db() as db:
        servers = db.query(McpServer).offset(skip).limit(limit).all()
        return BaseResponse.ok(servers)


# Read one
@router.get("/servers/{server_id}")
def read_server(server_id: str):
    with get_db() as db:
        server = db.query(McpServer).filter(McpServer.id == server_id).first()
        if not server:
            raise ServiceError(message="server not found")
        return BaseResponse.ok(data=server)


# Update
@router.put("/servers/{server_id}")
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
        return BaseResponse.ok(data=server)


# Delete
@router.delete("/servers/{server_id}")
def delete_server(server_id: str):
    with get_db() as db:
        server = db.query(McpServer).filter(McpServer.id == server_id).first()
        if not server:
            raise ServiceError(message="server not found")

        db.delete(server)
        db.commit()
        return BaseResponse.ok(data=server)


@router.get("/init_tools/{server_code}")
async def init_tools(server_code: str):
    with get_db() as db:
        mcp_server:Optional[McpServer] = db.query(McpServer).filter(McpServer.server_code == server_code).first()
        if not mcp_server:
            raise ServiceError(message="server not found")

        mcp_config = json.loads(mcp_server.configs)
        mcp_config['credential_type'] = mcp_server.credentials
        mcp_client = McpClient.build_client(mcp_server.server_url, mcp_config)
        try:
            async with mcp_client.get_client_session() as client_session:
                tools_response  = await client_session.list_tools()
                if tools_response is None:
                    raise ServiceError(message="failed to fetch tools from mcp server")

                from runtime.tool.mcp.tool_provider import ToolProviderType, CredentialType

                from models import ToolInfo

                tools_infos:list[ToolInfo] = []
                for tool in tools_response.tools :
                    print(tool)
                    tool_info = ToolInfo(
                        name=tool.name,
                        description=tool.description,
                        parameters=json.dumps(tool.inputSchema),
                        type=ToolProviderType.MCP,
                        provider=mcp_server.name,
                        credentials=mcp_server.credentials,
                        configs=mcp_server.configs,
                    )
                    existing_tool = db.query(ToolInfo).filter(ToolInfo.name == tool.name, ToolInfo.provider == mcp_server.name).first()
                    if existing_tool:
                        tool_info.id = existing_tool.tool_id

                    tools_infos.append(tool_info)
                db.bulk_save_objects(tools_infos)
                db.commit()
            return BaseResponse.ok(data=mcp_server)
        except Exception as e:
            return BaseResponse.error(error_code=500,error_msg=f"failed to fetch tools from mcp server: {e}")
