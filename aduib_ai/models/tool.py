import datetime

from sqlalchemy import UUID, String, text, DateTime, Integer, Column, ForeignKeyConstraint, Text

from models import Base


class ToolCallResult(Base):
    __tablename__ = "tool_call_result"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    message_id = Column(String, index=True, comment="message id")
    tool_call_id = Column(String, index=True, comment="tool call id")
    tool_id = Column(UUID(as_uuid=True), index=True, comment="tool id")
    tool_call=Column(Text, comment="tool calls")
    result=Column(Text, comment="tool call result", nullable=True, default="{}")
    state: str = Column(String, nullable=False, comment="tool call state", default="success")
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="update time")
    deleted = Column(Integer, default=0, comment="delete flag")
    __table_args__ = (
        ForeignKeyConstraint(["tool_id"], ["tool_info.id"]),
    )



class ToolInfo(Base):
    __tablename__ = "tool_info"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    name = Column(String, unique=True, comment="tool name")
    description = Column(String, comment="tool description")
    parameters = Column(Text, comment="tool parameters schema")
    configs=Column(Text, comment="tool configurations", nullable=True, server_default=text("{}"))
    icon=Column(String, comment="tool icon", nullable=True)
    provider = Column(String, comment="tool provider type")
    type=Column(String, comment="tool type")
    credentials=Column(String, comment="tool credentials", nullable=True, server_default=text("none"))
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="update time")
    deleted = Column(Integer, default=0, comment="delete flag")