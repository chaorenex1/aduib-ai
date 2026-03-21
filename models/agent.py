import datetime

from sqlalchemy import TEXT, Column, DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB

from models.base import Base


class Agent(Base):
    __tablename__ = "agent"
    id = Column(Integer, primary_key=True, index=True, comment="id")
    name = Column(String(255), nullable=False, index=True, comment="Agent name")
    description = Column(String(255), nullable=True, comment="Agent description", server_default=text("''"))
    model_id = Column(String(255), nullable=False, comment="Model ID", server_default=text("''"))
    prompt_template = Column(TEXT, nullable=False, comment="Prompt template", server_default=text("''"))
    tools = Column(JSONB, nullable=True, comment="Tools", server_default=text("'[]'"))
    agent_parameters = Column(JSONB, nullable=True, comment="Agent parameters", server_default=text("'{}'"))
    enabled_memory = Column(Integer, server_default=text("0"), comment="Enable memory,user agent disabled by default")
    builtin = Column(Integer, server_default=text("0"), comment="Built-in agent flag (1=builtin)")
    output_schema = Column(JSONB, nullable=True, comment="Output schema", server_default=text("'{}'"))
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="update time")
    deleted = Column(Integer, default=0, comment="delete flag")
    user_id = Column(String(100), nullable=True, comment="User ID")


class AgentSession(Base):
    __tablename__ = "agent_session"
    id = Column(Integer, primary_key=True, index=True, comment="id")
    agent_id = Column(Integer, index=True, comment="Agent ID")
    user_id = Column(String(100), index=True, comment="User ID")
    name = Column(String(255), nullable=True, index=True, comment="Session name")
    description = Column(String(255), nullable=True, comment="Session description", server_default=text("''"))
    status = Column(String(64), nullable=False, index=True, comment="Session status", default="active")
    context = Column(TEXT, nullable=True, comment="Session context", server_default=text("''"))
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="update time")
    deleted = Column(Integer, default=0, comment="delete flag")
