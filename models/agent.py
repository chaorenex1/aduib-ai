import datetime

from sqlalchemy import Column, DateTime, Integer, String, text, UUID, TEXT
from sqlalchemy.dialects.postgresql import JSONB

from models import Base


class Agent(Base):
    __tablename__ = "agent"
    id = Column(Integer, primary_key=True, index=True, comment="id")
    name = Column(String(255), nullable=False,index=True, comment="Agent name")
    description = Column(String(255), nullable=True, comment="Agent description", server_default=text("''"))
    model_id = Column(String(255), nullable=False, comment="Model ID")
    prompt_template = Column(TEXT, nullable=False, comment="Prompt template", server_default=text("''"))
    tools = Column(JSONB, nullable=True, comment="Tools", server_default=text("'[]'"))
    agent_parameters = Column(JSONB, nullable=True, comment="Agent parameters", server_default=text("'{}'"))
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="update time")
    deleted = Column(Integer, default=0, comment="delete flag")



class AgentSession(Base):
    __tablename__ = "agent_session"
    id = Column(Integer, primary_key=True, index=True, comment="id")
    agent_id = Column(Integer, index=True, comment="Agent ID")
    name = Column(String(255), nullable=False, index=True, comment="Session name")
    description = Column(String(255), nullable=True, comment="Session description", server_default=text("''"))
    status = Column(String(64), nullable=False, index=True, comment="Session status", default="active")
    context = Column(TEXT, nullable=True, comment="Session context", server_default=text("''"))
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="update time")
    deleted = Column(Integer, default=0, comment="delete flag")