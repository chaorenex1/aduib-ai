import datetime

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.base import Base


class FailurePattern(Base):
    __tablename__ = "failure_pattern"
    __table_args__ = (
        Index("idx_failure_pattern_user_type", "user_id", "pattern_type"),
        {"comment": "Aggregated failure evidence and repair strategies"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id = Column(String(100), nullable=False)
    pattern_type = Column(String(100), nullable=False)
    pattern_hash = Column(String(64), nullable=False, unique=True)
    occurrence_count = Column(Integer, nullable=False, server_default=text("0"))
    first_seen_at = Column(DateTime, nullable=True, default=datetime.datetime.now)
    last_seen_at = Column(
        DateTime,
        nullable=True,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
    )
    evidence = Column(JSONB, nullable=True, server_default=text("'[]'::jsonb"))
    repair_strategy = Column(Text, nullable=True)
    effectiveness = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=True, default=datetime.datetime.now)
