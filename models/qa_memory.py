import datetime
from enum import Enum
from typing import Any

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models import Base
from runtime.rag.rag_type import RagType


class QaMemoryStatus(str, Enum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    STALE = "stale"
    DEPRECATED = "deprecated"
    FROZEN = "frozen"


class QaMemoryLevel(str, Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class QaMemoryRecord(Base):
    __tablename__ = "qa_memory_record"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    project_id = Column(String(64), nullable=False, index=True, comment="Project or workspace identifier")
    knowledge_base_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_base.id"), nullable=False)
    rag_type = Column(String(32), nullable=False, default=RagType.QA.value)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    tags = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    meta = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status = Column(String(32), nullable=False, default=QaMemoryStatus.CANDIDATE.value)
    level = Column(String(16), nullable=False, default=QaMemoryLevel.L0.value)
    confidence = Column(Float, nullable=False, server_default=text("0.5"))
    trust_score = Column(Float, nullable=False, server_default=text("0.5"))
    success_count = Column(Integer, nullable=False, default=0)
    failure_count = Column(Integer, nullable=False, default=0)
    usage_count = Column(Integer, nullable=False, default=0)
    strong_signal_count = Column(Integer, nullable=False, default=0)
    ttl_expire_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    last_validated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.datetime.now(),
        onupdate=datetime.datetime.now(),
    )
    source = Column(String(128), nullable=True)
    author = Column(String(128), nullable=True)


class QaMemoryEvent(Base):
    __tablename__ = "qa_memory_event"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    qa_id = Column(UUID(as_uuid=True), ForeignKey("qa_memory_record.id"), index=True, nullable=False)
    project_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(32), nullable=False)
    payload: Column[Any] = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.now())



class TaskGradeRecord(Base):
    __tablename__ = "task_grade_record"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    prompt = Column(Text, nullable=False, server_default=text("''"))
    prompt_hash = Column(String(32), nullable=False, server_default=text("''"))
    task_level = Column(String, nullable=False, index=True,server_default="'L1'")
    reason = Column(String(300), nullable=False,server_default=text("''"))
    recommended_model = Column(String(128), nullable=False,server_default=text("''"))
    recommended_model_provider = Column(String(64), nullable=False,server_default=text("''"))
    confidence = Column(Float, nullable=False, server_default=text("0.5"))
    temperature = Column(Float, nullable=True, server_default=text("0.5"))
    top_p = Column(Float, nullable=True, server_default=text("0.9"))
    weight = Column(Float, nullable=True, server_default=text("0.5"))
    raw_json = Column(JSONB, nullable=True, server_default=text("'{}'::jsonb"))
    raw_text = Column(Text, nullable=True, server_default=text("''"))
    created_at = Column(DateTime, nullable=True, default=datetime.datetime.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.datetime.now(),
        onupdate=datetime.datetime.now(),
    )
