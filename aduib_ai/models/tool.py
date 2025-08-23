import datetime

from sqlalchemy import UUID, String, text, JSON, DateTime, Integer, Column

from models import Base


class ToolCallResult(Base):
    __tablename__ = "tool_call_result"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    message_id = Column(String, index=True, comment="message id")
    tool_call_id = Column(String, index=True, comment="tool call id")
    tool_call=Column(JSON, comment="tool calls")
    result=Column(JSON, comment="tool call result", nullable=True, default="{}")
    state: str = Column(String, nullable=False, comment="tool call state", default="success")
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="api key create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="api key update time")
    deleted = Column(Integer, default=0, comment="api key delete flag")



class Tool(Base):
    __tablename__ = "tool_info"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    name = Column(String, unique=True, comment="tool name")
    description = Column(String, comment="tool description")
    parameters = Column(JSON, comment="tool parameters schema")
    configs=Column(JSON, comment="tool configurations")
    icon=Column(String, comment="tool icon")
    provider = Column(String, comment="tool provider type")
    type=Column(String, comment="tool type")
    credentials=Column(String, comment="tool credentials")
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="tool create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="tool update time")
    deleted = Column(Integer, default=0, comment="tool delete flag")