import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from models.base import Base
from runtime.memory.types import Memory, MemoryClassType


class MemoryBase(Base):
    """Base class for memory-related tables."""

    __tablename__ = "memory_base"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id = Column(String(100), nullable=True, comment="用户ID")
    mem_kb_id = Column(String(100), nullable=True, comment="关联的知识库ID")
    domain = Column(String(50), nullable=False, server_default=text("''"), comment="记忆领域")
    type = Column(String(32), nullable=False)
    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, nullable=False)
    deleted = Column(Integer, default=0, comment="delete flag")


class MemoryRecord(Base):
    """Persistent memory record mapped from runtime.memory.types.Memory."""

    __tablename__ = "memory_record"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id = Column(String(100), nullable=True, comment="代理ID")
    type = Column(String(32), nullable=False)
    memory_base_id = Column(
        UUID(as_uuid=True), ForeignKey("memory_base.id"), nullable=False, comment="关联的 MemoryBase ID"
    )

    # Classification
    domain = Column(String(50), nullable=False, server_default=text("''"))
    source = Column(String(50), nullable=True)
    topic = Column(String, nullable=True, server_default=text("''"))
    kb_doc_id = Column(
        UUID(as_uuid=True), ForeignKey("knowledge_document.id"), nullable=True, comment="关联的知识文档ID"
    )

    tags = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))

    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, nullable=False)
    accessed_at = Column(DateTime, default=datetime.datetime.now, nullable=False)

    quality_score = Column(Float, nullable=True, comment="质量分数 0-1，由学习引擎定期更新")
    access_count = Column(Integer, default=0, comment="被检索次数，检索时自增")

    # Lifecycle
    deleted = Column(Integer, default=0, comment="delete flag")

    # Relationships
    memory_base = relationship("MemoryBase")
    kb_doc = relationship("KnowledgeDocument")

    __table_args__ = (
        Index("idx_memory_type", "type"),
        Index("idx_memory_domain", "domain"),
        Index("idx_memory_topic", "topic"),
        Index("idx_memory_created_at", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id) if self.id else None,
            "type": self.type,
            "domain": self.domain,
            "source": self.source,
            "topic": self.topic,
            "tags": self.tags or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "accessed_at": self.accessed_at.isoformat() if self.accessed_at else None,
            "quality_score": self.quality_score,
            "access_count": self.access_count or 0,
        }

    def to_memory(self) -> "Memory":
        return Memory(
            id=str(self.id),
            type=MemoryClassType(self.type),
            domain=self.domain or "",
            source=self.source or "",
            topic=self.topic or "",
            tags=self.tags or [],
            created_at=self.created_at,
            updated_at=self.updated_at,
            accessed_at=self.accessed_at,
        )

    @classmethod
    def from_memory(cls, memory: "Memory") -> "MemoryRecord":
        return cls(
            id=memory.id,
            type=memory.type.value if isinstance(memory.type, MemoryClassType) else str(memory.type),
            domain=memory.domain or "event",
            source=memory.source or None,
            topic=memory.topic,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
            accessed_at=memory.accessed_at,
        )
