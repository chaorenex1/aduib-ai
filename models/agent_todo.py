import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from models.base import Base


class AgentTodo(Base):
    __tablename__ = "agent_todo"
    __table_args__ = (
        Index("idx_agent_todo_agent_id", "agent_id"),
        Index("idx_agent_todo_status", "status"),
        Index("idx_agent_todo_session_id", "session_id"),
        Index("idx_agent_todo_user_id", "user_id"),
        {"comment": "Agent todo items for supervisor task tracking"},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="Todo item id")
    agent_id = Column(Integer, nullable=True, comment="Owning agent id")
    session_id = Column(Integer, nullable=True, comment="Associated session id")
    user_id = Column(String(100), nullable=True, comment="Owning user id")
    title = Column(String(500), nullable=False, comment="Short imperative task title")
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        comment="Status: pending/in_progress/completed/failed/blocked",
    )
    completion_condition = Column(Text, nullable=True, comment="Concrete completion condition for this todo")
    blocked_reason = Column(Text, nullable=True, comment="Reason this todo is blocked")
    failure_reason = Column(Text, nullable=True, comment="Failure reason short string")
    failure_evidence = Column(
        JSONB,
        nullable=True,
        comment="Legacy structured failure evidence kept for offline failure analysis",
    )
    depends_on = Column(
        JSONB,
        nullable=False,
        default=list,
        comment="List of todo IDs that must be completed before this todo can start",
    )
    evidence = Column(
        JSONB,
        nullable=True,
        comment="Structured verification evidence for completion or state transitions",
    )
    change_log = Column(
        JSONB,
        nullable=False,
        default=list,
        comment="Audit log of todo changes, including status transitions and reasons",
    )
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.now, comment="Creation time")
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
        comment="Last update time",
    )
