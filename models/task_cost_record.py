import datetime

from sqlalchemy import DECIMAL, Column, DateTime, Float, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID

from models.base import Base


class TaskCostRecord(Base):
    __tablename__ = "task_cost_record"
    __table_args__ = (
        Index("idx_task_cost_record_user_model", "user_id", "model_id"),
        Index("idx_task_cost_record_task_level", "task_level"),
        Index("idx_task_cost_record_created_at", "created_at"),
        {"comment": "Per-task cost and outcome records for cost-aware routing"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id = Column(String(100), nullable=False)
    agent_id = Column(String(100), nullable=True)
    todo_id = Column(UUID(as_uuid=True), nullable=True)
    task_level = Column(String(10), nullable=True)
    task_type = Column(String(100), nullable=True)
    model_id = Column(String(128), nullable=True)
    provider = Column(String(64), nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_price = Column(DECIMAL(10, 7), nullable=True)
    outcome = Column(String(20), nullable=True)
    quality_score = Column(Float, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=True, default=datetime.datetime.now)
