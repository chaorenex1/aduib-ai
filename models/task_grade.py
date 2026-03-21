import datetime

from sqlalchemy import Column, DateTime, Float, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.base import Base


class TaskGradeRecord(Base):
    __tablename__ = "task_grade_record"
    __table_args__ = (
        Index("idx_task_grade_record_task_level", "task_level"),
        {"comment": "Records task complexity grading decisions for model routing"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    prompt = Column(Text, nullable=False, server_default=text("''"))
    prompt_hash = Column(String(150), nullable=False, server_default=text("''"))
    task_level = Column(String, nullable=False, index=True, server_default="'L1'")
    reason = Column(String(300), nullable=False, server_default=text("''"))
    recommended_model = Column(String(128), nullable=False, server_default=text("''"))
    recommended_model_provider = Column(String(64), nullable=False, server_default=text("''"))
    confidence = Column(Float, nullable=False, server_default=text("0.5"))
    temperature = Column(Float, nullable=True, server_default=text("0.5"))
    top_p = Column(Float, nullable=True, server_default=text("0.9"))
    weight = Column(Float, nullable=True, server_default=text("0.5"))
    raw_json = Column(JSONB, nullable=True, server_default=text("'{}'::jsonb"))
    raw_text = Column(Text, nullable=True, server_default=text("''"))
    created_at = Column(DateTime, nullable=True, default=datetime.datetime.now)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
    )
