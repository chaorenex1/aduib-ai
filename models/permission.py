import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from models.base import Base


class Permission(Base):
    __tablename__ = "permissions"
    __table_args__ = (
        Index("idx_permission_agent_id", "agent_id"),
        Index("idx_permission_scope", "scope"),
        {"comment": "Agent-level tool permission grants and denials"},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="Row id")
    agent_id = Column(Integer, nullable=False, comment="Agent this permission applies to")

    # Comma-separated scope identifier, e.g. 'agent:42', 'role:admin', 'global'
    scope = Column(
        String(100),
        nullable=False,
        default="agent",
        comment="Permission scope: agent | role:<name> | global",
    )

    # Allowlist and denylist stored as JSON arrays of tool name strings
    allowed_tool_names = Column(
        JSONB,
        nullable=False,
        default=list,
        comment="Tool names the agent is explicitly allowed to invoke: []",
    )
    denied_tool_names = Column(
        JSONB,
        nullable=False,
        default=list,
        comment="Tool names the agent is explicitly denied from invoking: []",
    )

    # Optional free-text note explaining why this permission was granted/denied
    reason = Column(Text, nullable=True, comment="Human-readable rationale for this permission entry")

    granted_by = Column(String(200), nullable=True, comment="User or system that granted this permission")

    created_at = Column(DateTime, nullable=False, default=datetime.datetime.now, comment="Record creation time")
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
        comment="Last update time",
    )
