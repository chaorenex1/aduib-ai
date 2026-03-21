import datetime

from sqlalchemy import Column, DateTime, Float, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.base import Base


class LearningSignal(Base):
    __tablename__ = "learning_signal"
    __table_args__ = (
        Index("idx_learning_signal_user_type_created", "user_id", "signal_type", "created_at"),
        Index("idx_learning_signal_source_id", "source_id"),
        {"comment": "Unified signal event stream for memory quality learning"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id = Column(String(100), nullable=False)
    agent_id = Column(String(100), nullable=True)
    signal_type = Column(String(50), nullable=False)
    source_id = Column(String(100), nullable=True)
    value = Column(Float, nullable=False, server_default=text("0.0"))
    context = Column(JSONB, nullable=True, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime, nullable=True, default=datetime.datetime.now)
