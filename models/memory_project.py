import datetime

from sqlalchemy import Column, DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.base import Base


class MemoryProject(Base):
    __tablename__ = "memory_project"
    __table_args__ = (
        Index("idx_memory_project_status", "status"),
        Index("idx_memory_project_user_updated_at", "user_id", "updated_at"),
        Index("uq_memory_project_user_project_id", "user_id", "project_id", unique=True),
        {"comment": "Frontend-facing project metadata for programmer memory scopes"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    project_id = Column(String(191), nullable=False, comment="Stable frontend-facing project id")
    user_id = Column(String(100), nullable=False, comment="Owning user id")
    name = Column(String(120), nullable=False, comment="Project name")
    description = Column(Text, nullable=False, server_default=text("''"), comment="Project description")
    mode = Column(String(32), nullable=False, comment="Project mode: web or desktop")
    status = Column(
        String(32),
        nullable=False,
        server_default=text("'planning'"),
        comment="Project status: planning, active, done",
    )
    branches_json = Column(
        "branches",
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Branch/path bindings for desktop projects",
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.datetime.now,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="Creation time",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="Last update time",
    )
    deleted_at = Column(DateTime, nullable=True, comment="Soft delete timestamp")


class MemoryProjectRecent(Base):
    __tablename__ = "memory_project_recent"
    __table_args__ = (
        Index("uq_memory_project_recent_user_id", "user_id", unique=True),
        {"comment": "Per-user recent project selection"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id = Column(String(100), nullable=False, comment="Owning user id")
    recent_project_id = Column(String(191), nullable=False, comment="Most recently selected project id")
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.datetime.now,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="Creation time",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="Last update time",
    )
