import datetime

from sqlalchemy import UUID, Boolean, Column, DateTime, Integer, String, text

from models.base import Base


class McpUser(Base):
    __tablename__ = "mcp_user"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    name = Column(String(128), nullable=False, index=True)
    type = Column(String(128), nullable=False, index=True)
    is_is_anonymous = Column(Boolean, nullable=False, server_default=text("true"))
    external_user_id = Column(UUID, nullable=True, index=True)
    session_id = Column(String(256), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="update time")
    deleted = Column(Integer, default=0, comment="delete flag")
