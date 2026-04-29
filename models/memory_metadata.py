import datetime

from sqlalchemy import Column, DateTime, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB

from models.base import Base


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


class MemoryIndex(Base):
    """Committed navigation and memory file index projected into PostgreSQL."""

    __tablename__ = "memory_index"
    __table_args__ = (
        UniqueConstraint("memory_id", name="uq_memory_index_memory_id"),
        UniqueConstraint("file_path", name="uq_memory_index_file_path"),
        Index("idx_memory_index_user_type", "user_id", "memory_type"),
        Index("idx_memory_index_user_level", "user_id", "memory_level"),
        Index("idx_memory_index_directory_path", "directory_path"),
        Index("idx_memory_index_project_id", "project_id"),
        Index("idx_memory_index_memory_updated_at", "memory_updated_at"),
        {"comment": "Derived metadata index for committed memory and navigation files"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="DB row id")
    memory_id = Column(String(120), nullable=False, comment="Stable memory id from file frontmatter or path hash")
    memory_type = Column(String(32), nullable=False, comment="Memory schema name or project index family")
    memory_level = Column(String(8), nullable=False, comment="l0 | l1 | l2")

    user_id = Column(String(100), nullable=False, comment="Owning user id")
    project_id = Column(String(255), nullable=True, comment="Owning project id when applicable")

    scope_type = Column(String(32), nullable=False, comment="user | agent")
    directory_path = Column(String(1024), nullable=False, comment="Parent committed directory path")
    file_path = Column(String(1024), nullable=False, comment="Committed file path")
    filename = Column(String(255), nullable=False, comment="Committed file name")

    status = Column(String(32), nullable=True, comment="active | archived | draft")
    tags = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), comment="Projected tags array")
    file_sha256 = Column(String(64), nullable=False, comment="Hash of committed file content")
    content_bytes = Column(Integer, nullable=False, server_default=text("0"), comment="Committed file size in bytes")
    projection_payload = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Projected machine-readable attributes from committed file metadata",
    )

    memory_created_at = Column(DateTime(timezone=True), nullable=True, comment="Frontmatter created_at from file")
    memory_updated_at = Column(DateTime(timezone=True), nullable=True, comment="Frontmatter updated_at from file")
    indexed_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, comment="Projection refresh time")
    refreshed_by_task_id = Column(String(64), nullable=True, comment="Last memory_write_task.task_id")


class MemoryRetrievalHint(Base):
    """Retrieval-oriented hints derived from committed memories, not the source of truth."""

    __tablename__ = "memory_retrieval_hint"
    __table_args__ = (
        UniqueConstraint("memory_id", name="uq_memory_retrieval_hint_memory_id"),
        Index("idx_memory_retrieval_hint_user_topic", "user_id", "primary_topic"),
        Index("idx_memory_retrieval_hint_kind", "kind"),
        Index("idx_memory_retrieval_hint_file_path", "file_path"),
        {"comment": "Derived retrieval hint metadata projected from committed memories"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="DB row id")
    memory_id = Column(String(120), nullable=False, comment="Stable memory id from file frontmatter")

    user_id = Column(String(100), nullable=False, comment="Owning user id")
    project_id = Column(String(255), nullable=True, comment="Owning project id when applicable")

    kind = Column(String(32), nullable=False, comment="Concrete file kind")
    file_path = Column(String(1024), nullable=False, comment="Committed memory file path")

    title = Column(String(255), nullable=False, comment="Human-readable title")
    primary_topic = Column(String(255), nullable=True, comment="Primary retrieval topic")
    body_summary = Column(Text, nullable=True, comment="Short retrieval-safe summary")

    tags = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), comment="Projected tags")
    aliases = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), comment="Projected aliases")
    entity_refs = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), comment="Projected entity refs")
    keywords = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), comment="Projected retrieval keywords")
    query_hints = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), comment="Suggested query phrases")

    importance_score = Column(Numeric(5, 4), nullable=True, comment="Optional projector-derived importance score")
    freshness_at = Column(DateTime(timezone=True), nullable=True, comment="Timestamp used for freshness weighting")
    indexed_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, comment="Refresh time")
    refreshed_by_task_id = Column(String(64), nullable=True, comment="Last memory_write_task.task_id")
