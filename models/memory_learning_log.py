import datetime

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID

from models.base import Base


class MemoryLearningLog(Base):
    __tablename__ = "memory_learning_log"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id = Column(String(255), nullable=False, comment="用户ID")
    quality_scored = Column(Integer, nullable=True, comment="本轮打分记忆条数")
    insights_created = Column(Integer, nullable=True, comment="本轮生成洞察数")
    merges_performed = Column(Integer, nullable=True, comment="本轮合并主题数")
    memories_pruned = Column(Integer, nullable=True, comment="本轮剪枝记忆数")
    elapsed_seconds = Column(Float, nullable=True, comment="本轮耗时秒数")
    error = Column(String(500), nullable=True, comment="错误信息，无错误则 NULL")
    created_at = Column(DateTime, default=datetime.datetime.now, nullable=False)

    __table_args__ = (Index("idx_memory_learning_log_user_created", "user_id", "created_at"),)
