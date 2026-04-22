import datetime

from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.base import Base


class MemoryConversation(Base):
    __tablename__ = "memory_conversation"
    __table_args__ = (
        Index("idx_memory_conversation_status", "status"),
        Index("idx_memory_conversation_user_updated_at", "user_id", "updated_at"),
        Index("idx_memory_conversation_project_updated_at", "project_id", "updated_at"),
        Index("idx_memory_conversation_last_message_at", "last_message_at"),
        Index("uq_memory_conversation_user_conversation_id", "user_id", "conversation_id", unique=True),
        Index(
            "uq_memory_conversation_user_source_session",
            "user_id",
            "external_source",
            "external_session_id",
            unique=True,
        ),
        {"comment": "Programmer memory conversation metadata with external jsonl message storage"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    conversation_id = Column(String(191), nullable=False, comment="Canonical conversation id")
    external_source = Column(String(64), nullable=False, comment="External conversation source")
    external_session_id = Column(String(191), nullable=False, comment="External source session id")
    user_id = Column(String(100), nullable=False, comment="Owning user id")
    agent_id = Column(String(100), nullable=True, comment="Owning agent id")
    project_id = Column(String(255), nullable=True, comment="Project id")

    title = Column(String(500), nullable=True, comment="Conversation title")
    metadata_json = Column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Conversation-level metadata",
    )

    message_store_type = Column(
        String(32),
        nullable=False,
        server_default=text("'jsonl'"),
        comment="Message storage type",
    )
    message_store_uri = Column(String(1024), nullable=False, comment="Authoritative jsonl locator")
    message_store_path = Column(String(1024), nullable=True, comment="Optional filesystem-compatible display path")

    message_count = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Count of message rows in the jsonl object",
    )
    modalities = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Union of message content part types",
    )
    content_sha256 = Column(String(64), nullable=True, comment="Hash of current jsonl content")
    size_bytes = Column(BigInteger, nullable=True, comment="Size of current jsonl object in bytes")

    version = Column(
        Integer,
        nullable=False,
        server_default=text("1"),
        comment="Monotonic conversation version",
    )
    status = Column(
        String(32),
        nullable=False,
        server_default=text("'active'"),
        comment="Conversation resource status",
    )

    first_message_at = Column(DateTime, nullable=True, comment="Timestamp of first message")
    last_message_at = Column(DateTime, nullable=True, comment="Timestamp of latest message")
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
