import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from models.base import Base


class AgentPlan(Base):
    __tablename__ = "agent_plan"
    __table_args__ = (
        Index("idx_agent_plan_agent_id", "agent_id"),
        Index("idx_agent_plan_status", "status"),
        Index("idx_agent_plan_session_id", "session_id"),
        Index("idx_agent_plan_user_id", "user_id"),
        {"comment": "Agent execution plans for supervisor task orchestration"},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="Plan id")
    agent_id = Column(Integer, nullable=True, comment="Owning agent id")
    session_id = Column(Integer, nullable=True, comment="Associated session id")
    user_id = Column(String(100), nullable=True, comment="Owning user id")
    title = Column(String(500), nullable=False, comment="Plan title")
    body = Column(Text, nullable=False, default="", comment="Markdown planning document body")
    status = Column(
        String(20),
        nullable=False,
        default="active",
        comment="Status: draft/active/completed/cancelled/archived",
    )
    change_log = Column(JSONB, nullable=False, default=list, comment="Audit log of plan changes")
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.now, comment="Creation time")
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
        comment="Last update time",
    )
