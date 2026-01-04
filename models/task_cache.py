import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, Boolean, Index

from models import Base


class TaskCache(Base):
    """
    Task cache table for storing task execution results from Orchestrator clients.
    Supports caching and history tracking for AI task executions.
    """
    __tablename__ = "task_cache"
    __table_args__ = (
        Index('idx_request_hash_mode_backend', 'request_hash', 'mode', 'backend', unique=True),
        Index('idx_created_at', 'created_at'),
        Index('idx_mode', 'mode'),
        Index('idx_backend', 'backend'),
        {
            "comment": "Task cache and history table for Orchestrator integration",
        }
    )

    id = Column(Integer, primary_key=True, index=True, comment="Task cache id")
    request = Column(Text, nullable=False, comment="Original request content")
    request_hash = Column(String(64), nullable=False, comment="SHA256 hash of request:mode:backend")
    mode = Column(String(32), nullable=False, comment="Execution mode: command/agent/prompt/skill/backend")
    backend = Column(String(32), nullable=False, comment="Backend type: claude/gemini/codex")
    success = Column(Boolean, nullable=False, default=True, comment="Whether execution succeeded")
    output = Column(Text, nullable=False, comment="Task output content")
    error = Column(Text, nullable=True, comment="Error message if failed")
    run_id = Column(String(64), nullable=True, comment="Memex-CLI run ID")
    duration_seconds = Column(Float, nullable=True, comment="Execution duration in seconds")
    hit_count = Column(Integer, nullable=False, default=0, comment="Cache hit count")
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.now, comment="Task creation time")
    updated_at = Column(DateTime, nullable=False, default=datetime.datetime.now, onupdate=datetime.datetime.now, comment="Last update time")
