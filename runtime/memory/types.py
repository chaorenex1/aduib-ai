from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


def _ensure_aware(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (assume UTC if naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class MemorySource(StrEnum):
    """记忆的来源渠道。"""

    CHAT = "chat"
    QA = "qa"
    AGENT_TASK = "agent_task"
    BROWSE = "browse"
    DOCUMENT = "document"
    CODE = "code"
    ACTION = "action"
    PREFERENCE = "preference"
    FEEDBACK = "feedback"


class MemoryDomain(StrEnum):
    """记忆所属领域。"""

    PREFERENCE = "preference"  # 偏好
    EVENT = "event"  # 事件
    RELATIONSHIP = "relationship"  # 关系
    BEHAVIOR = "behavior"  # 行为
    KNOWLEDGE = "knowledge"  # 知识


class MemoryClassType(StrEnum):
    """高层记忆分类枚举。"""

    PERCEPTUAL = "perceptual"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class Memory(BaseModel):
    """统一的记忆实体模型。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: MemoryClassType
    content: str
    summary_enabled: bool = Field(False, description="Whether to generate summary for the memory")
    knowledge_base: Optional[Any] = Field(default=None, description="关联的知识库信息")

    # Context
    user_id: str = ""
    project_id: str = ""
    agent_id: str = ""

    # Classification (LLM-managed)
    domain: str = ""
    source: str = ""
    topic: str = ""

    # Metadata
    tags: list[str] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    accessed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Lifecycle
    ttl: Optional[int] = None
    access_count: int = 0

    @model_validator(mode="before")
    @classmethod
    def _ensure_aware_datetimes(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        for key in ("created_at", "updated_at", "accessed_at"):
            val = data.get(key)
            if isinstance(val, datetime) and val.tzinfo is None:
                data[key] = val.replace(tzinfo=UTC)
        return data

    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        expiry = self.created_at + timedelta(seconds=self.ttl)
        return _utcnow() > expiry

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="python")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        return cls.model_validate(data)


class MemoryTopicSegment(BaseModel):
    """主题相关内容片段，用于辅助记忆分类与检索。"""

    topic: str = Field(..., description="主题名称")
    topic_content_segment: list[str] = Field(default_factory=lambda: [], description="与主题相关的内容片段列表")

    @classmethod
    def json_schema(cls) -> str:
        """返回 JSON Schema 定义字符串。"""
        return json.dumps(cls.model_json_schema(), ensure_ascii=False, indent=2)

    @classmethod
    def parse_list(cls, json_str: str) -> list[MemoryTopicSegment]:
        """从 JSON 字符串解析 MemoryTopicSegment 列表。"""
        try:
            data = json.loads(json_str)
            if isinstance(data, list):
                return [cls.model_validate(item) for item in data]
            elif isinstance(data, dict):
                return [cls.model_validate(data)]
            else:
                raise ValueError("Invalid JSON format for MemoryTopicSegment")
        except json.JSONDecodeError:
            logger.exception("Failed to decode JSON for MemoryTopicSegment")
            raise


class MemoryTopicSegmentProcessed(MemoryTopicSegment):
    """处理后的主题内容片段，包含额外的向量表示和相关记忆 ID 列表。"""

    pass


class MemoryRetrieveType(StrEnum):
    """记忆检索类型枚举。"""

    RAG = "rag"
    LLM = "llm"


class MemorySignalType(StrEnum):
    """记忆学习信号类型枚举。"""

    MEMORY_EXPOSED = "memory_exposed"
    MEMORY_SELECTED = "memory_selected"
    MEMORY_USED_IN_ANSWER = "memory_used_in_answer"
    MEMORY_USER_CONFIRMED = "memory_user_confirmed"
    MEMORY_USER_CORRECTED = "memory_user_corrected"
    TASK_SUCCEEDED_AFTER_MEMORY = "task_succeeded_after_memory"
    TASK_FAILED_AFTER_MEMORY = "task_failed_after_memory"
    MEMORY_CONFLICT_DETECTED = "memory_conflict_detected"
    MEMORY_DISTILLED = "memory_distilled"
    MEMORY_MERGED = "memory_merged"
    MEMORY_ADOPTION = "memory_adoption"
    MEMORY_ACCESS = "memory_access"


class MemoryRetrieve(BaseModel):
    """记忆检索请求模型。"""

    query: str
    user_id: str
    agent_id: Optional[str] = None
    project_id: Optional[str] = None
    retrieve_type: MemoryRetrieveType = MemoryRetrieveType.RAG
    top_k: int = 5
    score_threshold: float = 0.6
    filters: dict[str, Any] = Field(default_factory=dict)


class MemoryRetrieveResult(BaseModel):
    """记忆检索结果模型。"""

    memory_id: str
    content: str
    score: Optional[float] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Entity(BaseModel):
    """记忆中涉及的实体。"""

    id: str
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class Relation(BaseModel):
    """实体间的关联关系。"""

    source_id: str
    target_id: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)

    model_config = ConfigDict(from_attributes=True)
