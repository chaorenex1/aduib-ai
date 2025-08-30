from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from controllers.common.base import BaseResponse
from controllers.common.error import ServiceError
from controllers.params import MCPServerCreate, MCPServerUpdate
from models import McpServer, get_db
from utils import generate_string

router = APIRouter(tags=['mcp_server'],prefix="/mcp_server")

# Create
@router.post("/servers/")
def create_server(server: MCPServerCreate, db: Session = Depends(get_db)):
    db_server = McpServer(**server.model_dump(exclude_none=True))
    db_server.server_code = generate_string(16)
    db.add(db_server)
    db.commit()
    db.refresh(db_server)
    return BaseResponse.ok(data=db_server)


# Read all
@router.get("/servers/")
def read_servers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    servers = db.query(McpServer).offset(skip).limit(limit).all()
    return BaseResponse.ok(servers)


# Read one
@router.get("/servers/{server_id}")
def read_server(server_id: str, db: Session = Depends(get_db)):
    server = db.query(McpServer).filter(McpServer.id == server_id).first()
    if not server:
        raise ServiceError(message="server not found")
    return BaseResponse.ok(data=server)


# Update
@router.put("/servers/{server_id}")
def update_server(server_id: str, server_update: MCPServerUpdate, db: Session =Depends(get_db)):
    server = db.query(McpServer).filter(McpServer.id == server_id).first()
    if not server:
        raise ServiceError(message="server not found")

    update_data = server_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(server, key, value)

    db.commit()
    db.refresh(server)
    return BaseResponse.ok(data=server)


# Delete
@router.delete("/servers/{server_id}")
def delete_server(server_id: str, db: Session = Depends(get_db)):
    server = db.query(McpServer).filter(McpServer.id == server_id).first()
    if not server:
        raise ServiceError(message="server not found")

    db.delete(server)
    db.commit()
    return BaseResponse.ok(data=server)