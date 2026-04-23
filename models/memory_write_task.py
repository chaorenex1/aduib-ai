import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from models.base import Base


class MemoryWriteTask(Base):
    __tablename__ = "memory_write_task"
    __table_args__ = (
        Index("idx_memory_write_task_created_at", "created_at"),
        Index("idx_memory_write_task_idempotency", "idempotency_key"),
        Index("idx_memory_write_task_phase", "phase"),
        Index("idx_memory_write_task_status", "status"),
        Index("idx_memory_write_task_task_id", "task_id", unique=True),
        {"comment": "Queue-first async memory write task lifecycle and journal metadata"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="DB row id")
    task_id = Column(String(64), nullable=False, comment="Public task id")
    trigger_type = Column(String(32), nullable=False, comment="memory_api | session_commit")
    user_id = Column(String(100), nullable=True, comment="Owning user id")
    agent_id = Column(String(100), nullable=True, comment="Owning agent id")
    project_id = Column(String(255), nullable=True, comment="Project id")
    trace_id = Column(String(64), nullable=False, comment="Trace id")
    idempotency_key = Column(String(128), nullable=False, comment="Idempotency key")

    source_ref = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Stable source reference for background extraction",
    )
    archive_ref = Column(JSONB, nullable=True, comment="Archived source details used by worker")
    queue_payload = Column(JSONB, nullable=True, comment="Metadata-only queue envelope")
    result_ref = Column(JSONB, nullable=True, comment="Result metadata from compatibility projector")

    status = Column(
        String(32),
        nullable=True,
        comment="Terminal task outcome: success | failed",
    )
    phase = Column(
        String(64),
        nullable=False,
        default="accepted",
        server_default=text("'accepted'"),
        comment="Current processing phase",
    )

    last_publish_error = Column(Text, nullable=True, comment="Last publish error")
    publish_failed_at = Column(DateTime, nullable=True, comment="Publish failure timestamp")
    failure_code = Column(String(64), nullable=True, comment="Failure code")
    failure_message = Column(Text, nullable=True, comment="Failure message")
    last_error = Column(Text, nullable=True, comment="Last error seen by task")
    rollback_metadata = Column(JSONB, nullable=True, comment="Rollback and recovery metadata payload")
    journal_ref = Column(String(255), nullable=True, comment="Commit journal location")
    operator_notes = Column(Text, nullable=True, comment="Operator notes")
    queued_at = Column(DateTime, nullable=True, comment="Queue ack timestamp")
    started_at = Column(DateTime, nullable=True, comment="Worker started timestamp")
    completed_at = Column(DateTime, nullable=True, comment="Terminal completion timestamp")
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
