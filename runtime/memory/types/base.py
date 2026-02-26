from __future__ import annotations

import math
from datetime import datetime
from enum import StrEnum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class MemoryType(StrEnum):
    """记忆类型枚举。"""

    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


class MemoryScope(StrEnum):
    """记忆作用域枚举。"""

    PERSONAL = "personal"
    WORK = "work"
    PROJECT = "project"
    MODULE = "module"


class EntityType(StrEnum):
    """实体类型枚举。"""

    USER = "user"
    CONCEPT = "concept"
    EVENT = "event"
    FACT = "fact"
    PREFERENCE = "preference"



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

    WORK = "work"
    LEARNING = "learning"
    RESEARCH = "research"
    LIFE = "life"
    HEALTH = "health"
    FINANCE = "finance"
    HOBBY = "hobby"
    ENTERTAINMENT = "entertainment"
    GENERAL = "general"


class MemoryLifecycle(StrEnum):
    """记忆生命周期分级。"""

    TRANSIENT = "transient"
    SHORT = "short"
    LONG = "long"
    PERMANENT = "permanent"


class ImportanceLevel(StrEnum):
    """重要性等级。"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FrequencyLevel(StrEnum):
    """出现频率等级。"""

    DAILY = "daily"
    WEEKLY = "weekly"
    OCCASIONAL = "occasional"
    RARE = "rare"


class TimeSensitivity(StrEnum):
    """时间敏感度等级。"""

    VOLATILE = "volatile"
    EVOLVING = "evolving"
    STABLE = "stable"
    PERMANENT = "permanent"


class Entity(BaseModel):
    """记忆中涉及的实体。"""

    id: str
    name: str
    type: EntityType
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


class MemoryMetadata(BaseModel):
    """记忆的上下文元数据。"""

    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    user_id: Optional[str] = None
    scope: MemoryScope = MemoryScope.PERSONAL
    source: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class Memory(BaseModel):
    """统一的记忆实体模型。"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: MemoryType
    content: str
    embedding: Optional[list[float]] = None
    metadata: MemoryMetadata = Field(default_factory=MemoryMetadata)
    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    accessed_at: datetime = Field(default_factory=datetime.now)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    decay_rate: float = Field(default=0.01, ge=0.0, le=1.0)
    ttl: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    def is_expired(self) -> bool:
        """判断记忆是否过期。"""

        if self.ttl is None:
            return False
        return datetime.now() > self.ttl

    def calculate_current_importance(self) -> float:
        """依据上次访问时间对重要性进行指数衰减。"""

        elapsed_seconds = (datetime.now() - self.accessed_at).total_seconds()
        decay_factor = math.exp(-self.decay_rate * elapsed_seconds)
        current = self.importance * decay_factor
        return max(0.0, min(1.0, current))

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""

        return self.model_dump(mode="python")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Memory":
        """从字典反序列化构建记忆。"""

        return cls.model_validate(data)


class SourceMetadata(BaseModel):
    """记录记忆来源的元信息。"""

    source: MemorySource
    source_id: str
    source_uri: Optional[str] = None
    created_by: str = "user"
    session_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(from_attributes=True)


class DomainHierarchy(BaseModel):
    """描述记忆所属的领域层级。"""

    domain: MemoryDomain = MemoryDomain.GENERAL
    project: Optional[str] = None
    module: Optional[str] = None
    topic: Optional[str] = None
    task_type: Optional[str] = None
    tags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class QAClassification(BaseModel):
    """问答类记忆的结构化分类信息。"""

    project: Optional[str] = None
    module: Optional[str] = None
    topic: Optional[str] = None
    task_type: Optional[str] = None
    tech_stack: list[str] = Field(default_factory=list)
    importance: ImportanceLevel = ImportanceLevel.MEDIUM
    frequency: FrequencyLevel = FrequencyLevel.OCCASIONAL
    time_sensitivity: TimeSensitivity = TimeSensitivity.STABLE

    model_config = ConfigDict(from_attributes=True)


class MemoryClassification(BaseModel):
    """统一的记忆分类描述。"""

    source: MemorySource
    domain: MemoryDomain
    scope: MemoryScope
    lifecycle: MemoryLifecycle
    source_metadata: Optional[SourceMetadata] = None
    domain_hierarchy: Optional[DomainHierarchy] = None
    qa_classification: Optional[QAClassification] = None
    tags: list[str] = Field(default_factory=list)
    inferred_topics: list[str] = Field(default_factory=list)
    inferred_entities: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
