import datetime

from sqlalchemy import Column, DateTime, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB

from models.base import Base


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


class MemoryIndex(Base):
    """Committed file-layer memory index projected into PostgreSQL."""

    __tablename__ = "memory_index"
    __table_args__ = (
        UniqueConstraint("memory_id", name="uq_memory_index_memory_id"),
        UniqueConstraint("file_path", name="uq_memory_index_file_path"),
        Index("idx_memory_index_user_class", "user_id", "memory_class"),
        Index("idx_memory_index_scope_path", "scope_path"),
        Index("idx_memory_index_directory_path", "directory_path"),
        Index("idx_memory_index_project_id", "project_id"),
        Index("idx_memory_index_memory_updated_at", "memory_updated_at"),
        {"comment": "Derived metadata index for committed formal memory files"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="DB row id")
    memory_id = Column(String(120), nullable=False, comment="Stable memory id from file frontmatter")
    memory_class = Column(String(32), nullable=False, comment="First-level memory class")
    kind = Column(String(32), nullable=False, comment="Concrete file kind")

    user_id = Column(String(100), nullable=False, comment="Owning user id")
    agent_id = Column(String(100), nullable=True, comment="Owning agent id when applicable")
    project_id = Column(String(255), nullable=True, comment="Owning project id when applicable")

    scope_type = Column(String(32), nullable=False, comment="user | agent")
    scope_path = Column(String(1024), nullable=False, comment="Metadata refresh scope path")
    directory_path = Column(String(1024), nullable=False, comment="Parent committed directory path")
    file_path = Column(String(1024), nullable=False, comment="Committed memory file path")

    title = Column(String(255), nullable=False, comment="Human-readable title")
    topic = Column(String(255), nullable=True, comment="Primary semantic topic when available")
    source_type = Column(String(32), nullable=True, comment="manual | session | derived | imported")
    visibility = Column(String(32), nullable=True, comment="public-safe | internal")
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


class MemoryDirectoryIndex(Base):
    """Directory-level navigation metadata derived from the committed tree."""

    __tablename__ = "memory_directory_index"
    __table_args__ = (
        UniqueConstraint("directory_path", name="uq_memory_directory_index_directory_path"),
        Index("idx_memory_directory_index_scope_path", "scope_path"),
        Index("idx_memory_directory_index_parent_path", "parent_directory_path"),
        Index("idx_memory_directory_index_user_kind", "user_id", "directory_kind"),
        {"comment": "Derived navigation metadata for committed memory directories"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="DB row id")

    user_id = Column(String(100), nullable=False, comment="Owning user id")
    agent_id = Column(String(100), nullable=True, comment="Owning agent id when applicable")
    project_id = Column(String(255), nullable=True, comment="Owning project id when applicable")

    scope_type = Column(String(32), nullable=False, comment="user | agent")
    scope_path = Column(String(1024), nullable=False, comment="Metadata refresh scope path")
    directory_path = Column(String(1024), nullable=False, comment="Committed directory path")
    parent_directory_path = Column(String(1024), nullable=True, comment="Parent committed directory path")

    memory_class = Column(String(32), nullable=True, comment="First-level memory class for this branch")
    directory_kind = Column(String(64), nullable=False, comment="Concrete directory kind such as event or ops/runbooks")
    title = Column(String(255), nullable=False, comment="Directory display title")

    overview_path = Column(String(1024), nullable=True, comment="Committed overview.md path when present")
    summary_path = Column(String(1024), nullable=True, comment="Committed summary.md path when present")
    memory_entry_count = Column(Integer, nullable=False, server_default=text("0"), comment="Formal memory file count")
    child_directory_count = Column(Integer, nullable=False, server_default=text("0"), comment="Child directory count")
    latest_memory_updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Latest memory_updated_at among entries in this directory",
    )
    projection_payload = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Projected directory-level navigation summary",
    )

    refreshed_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, comment="Refresh time")
    refreshed_by_task_id = Column(String(64), nullable=True, comment="Last memory_write_task.task_id")


class MemoryTimelineIndex(Base):
    """Time-oriented view over committed memories that carry timeline semantics."""

    __tablename__ = "memory_timeline_index"
    __table_args__ = (
        UniqueConstraint("memory_id", "timeline_kind", name="uq_memory_timeline_index_memory_kind"),
        Index("idx_memory_timeline_index_user_sort_at", "user_id", "sort_at"),
        Index("idx_memory_timeline_index_project_sort_at", "project_id", "sort_at"),
        Index("idx_memory_timeline_index_file_path", "file_path"),
        {"comment": "Derived timeline metadata for committed time-bearing memories"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="DB row id")
    memory_id = Column(String(120), nullable=False, comment="Stable memory id from file frontmatter")

    user_id = Column(String(100), nullable=False, comment="Owning user id")
    agent_id = Column(String(100), nullable=True, comment="Owning agent id when applicable")
    project_id = Column(String(255), nullable=True, comment="Owning project id when applicable")

    memory_class = Column(String(32), nullable=False, comment="First-level memory class")
    kind = Column(String(32), nullable=False, comment="Concrete file kind")
    timeline_kind = Column(String(32), nullable=False, comment="event | task | verification | review | ops")
    file_path = Column(String(1024), nullable=False, comment="Committed memory file path")

    title = Column(String(255), nullable=False, comment="Timeline entry title")
    sort_at = Column(DateTime(timezone=True), nullable=False, comment="Primary sort timestamp for timeline ordering")
    happened_at = Column(DateTime(timezone=True), nullable=True, comment="Explicit domain time from the memory content")
    result_status = Column(String(64), nullable=True, comment="Outcome/result summary when available")
    projection_payload = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Timeline-specific metadata such as severity, environment, reviewer, or operator",
    )

    indexed_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, comment="Refresh time")
    refreshed_by_task_id = Column(String(64), nullable=True, comment="Last memory_write_task.task_id")


class MemoryDedupeIndex(Base):
    """Dedupe-oriented metadata projected from committed memories."""

    __tablename__ = "memory_dedupe_index"
    __table_args__ = (
        UniqueConstraint("memory_id", name="uq_memory_dedupe_index_memory_id"),
        Index("idx_memory_dedupe_index_scope_path", "dedupe_scope_path"),
        Index("idx_memory_dedupe_index_content_hash", "content_sha256"),
        Index("idx_memory_dedupe_index_semantic_key", "semantic_key"),
        {"comment": "Derived dedupe metadata for committed memory files"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="DB row id")
    memory_id = Column(String(120), nullable=False, comment="Stable memory id from file frontmatter")

    user_id = Column(String(100), nullable=False, comment="Owning user id")
    agent_id = Column(String(100), nullable=True, comment="Owning agent id when applicable")
    project_id = Column(String(255), nullable=True, comment="Owning project id when applicable")

    memory_class = Column(String(32), nullable=False, comment="First-level memory class")
    kind = Column(String(32), nullable=False, comment="Concrete file kind")
    file_path = Column(String(1024), nullable=False, comment="Committed memory file path")
    dedupe_scope_path = Column(String(1024), nullable=False, comment="Scope path used during dedupe refresh")

    title_norm = Column(String(255), nullable=True, comment="Normalized title/topic/name for exact heuristics")
    semantic_key = Column(String(255), nullable=True, comment="Normalized semantic key for cheap candidate lookup")
    content_sha256 = Column(String(64), nullable=False, comment="Hash of committed content for exact-match dedupe")
    fingerprint_version = Column(String(32), nullable=False, server_default=text("'v1'"), comment="Fingerprint version")
    fingerprint_payload = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Derived dedupe fingerprint attributes from committed file view",
    )

    indexed_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, comment="Refresh time")
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
    agent_id = Column(String(100), nullable=True, comment="Owning agent id when applicable")
    project_id = Column(String(255), nullable=True, comment="Owning project id when applicable")

    memory_class = Column(String(32), nullable=False, comment="First-level memory class")
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
