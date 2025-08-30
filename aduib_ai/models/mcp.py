import datetime

from sqlalchemy import Column, String, Enum, Integer, DateTime, UUID, text, Text

from models import Base


class McpServer(Base):
    __tablename__ = "mcp_server"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    server_code = Column(String(64), unique=True, nullable=False)
    name = Column(String(128), nullable=False,index=True)
    description = Column(String, nullable=True)
    status = Column(Enum("active", "inactive", name="mcp_server_status"), default="active", nullable=False)
    parameters = Column(Text, comment="tool parameters")
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="update time")
    deleted = Column(Integer, default=0, comment="delete flag")