from __future__ import annotations

from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


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
