import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text

from models.base import Base


class CronJob(Base):
    __tablename__ = "cron_job"
    __table_args__ = (
        Index("idx_cron_job_enabled", "enabled"),
        Index("idx_cron_job_next_run_at", "next_run_at"),
        Index("idx_cron_job_updated_at", "updated_at"),
        {"comment": "Persisted scheduled task definitions"},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="Cron job id")
    name = Column(String(255), nullable=False, comment="Cron display name")
    message_id = Column(String(200), nullable=True, comment="Originating conversation message id")
    user_id = Column(String(100), nullable=True, comment="Owning user id")
    agent_id = Column(Integer, nullable=True, comment="Owning agent id")
    session_id = Column(Integer, nullable=True, comment="Owning session id")

    schedule = Column(String(120), nullable=False, comment="Cron expression")
    timezone = Column(String(64), nullable=False, default="UTC", comment="Cron timezone")
    enabled = Column(Boolean, nullable=False, default=True, comment="Whether the schedule is active")

    execution_type = Column(String(20), nullable=False, comment="command | shell_script | python_script")
    command = Column(Text, nullable=True, comment="Shell command text when execution_type=command")
    script_path = Column(String(255), nullable=True, comment="Relative script path inside app.workdir")
    timeout_seconds = Column(Integer, nullable=True, comment="Execution timeout in seconds")

    last_task_id = Column(Integer, nullable=True, comment="Last created task job id")
    last_run_at = Column(DateTime, nullable=True, comment="Last trigger time")
    next_run_at = Column(DateTime, nullable=True, comment="Next trigger time")

    created_at = Column(DateTime, nullable=False, default=datetime.datetime.now, comment="Creation time")
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
        comment="Last update time",
    )
