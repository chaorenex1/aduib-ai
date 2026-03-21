import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from models.base import Base


class TaskJob(Base):
    __tablename__ = "task_job"
    __table_args__ = (
        Index("idx_task_job_status", "status"),
        Index("idx_task_job_celery_task_id", "celery_task_id"),
        Index("idx_task_job_cron_id", "cron_id"),
        Index("idx_task_job_created_at", "created_at"),
        {"comment": "Persisted background task jobs"},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="Task job id")
    name = Column(String(255), nullable=True, comment="Optional task display name")
    source = Column(String(20), nullable=False, default="manual", comment="manual | cron")
    cron_id = Column(Integer, nullable=True, comment="Source cron job id when created by scheduler")
    message_id = Column(String(200), nullable=True, comment="Originating conversation message id")
    user_id = Column(String(100), nullable=True, comment="Owning user id")
    agent_id = Column(Integer, nullable=True, comment="Owning agent id")
    session_id = Column(Integer, nullable=True, comment="Owning session id")

    execution_type = Column(String(20), nullable=False, comment="command | shell_script | python_script")
    command = Column(Text, nullable=True, comment="Shell command text when execution_type=command")
    script_path = Column(String(255), nullable=True, comment="Relative script path inside app.workdir")

    timeout_seconds = Column(Integer, nullable=True, comment="Execution timeout in seconds")
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending | running | completed | failed | cancelled",
    )
    output_payload = Column(JSONB, nullable=True, comment="Execution output payload")
    error = Column(Text, nullable=True, comment="Execution error")
    celery_task_id = Column(String(120), nullable=True, comment="Backing Celery task id")
    cancellation_requested = Column(Boolean, nullable=False, default=False, comment="Cancellation requested flag")

    created_at = Column(DateTime, nullable=False, default=datetime.datetime.now, comment="Creation time")
    started_at = Column(DateTime, nullable=True, comment="Execution start time")
    finished_at = Column(DateTime, nullable=True, comment="Execution end time")
    cancel_requested_at = Column(DateTime, nullable=True, comment="Cancellation request time")
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
        comment="Last update time",
    )
