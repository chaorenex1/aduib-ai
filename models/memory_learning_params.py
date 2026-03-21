import datetime

from sqlalchemy import Column, DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.base import Base


class MemoryLearningParams(Base):
    """LLM 优化后的每用户学习参数，最新一条为当前生效参数。"""

    __tablename__ = "memory_learning_params"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id = Column(String(255), nullable=False, comment="用户ID")
    params = Column(JSONB, nullable=False, comment="各组件参数，结构见 ParamOptimizer.DEFAULT_PARAMS")
    reasoning = Column(Text, nullable=True, comment="LLM 给出的调参理由")
    created_at = Column(DateTime, default=datetime.datetime.now, nullable=False)

    __table_args__ = (Index("idx_memory_learning_params_user_created", "user_id", "created_at"),)
