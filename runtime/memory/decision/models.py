"""Decision memory data models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class DecisionStatus(StrEnum):
    """决策状态枚举。"""

    PROPOSED = "proposed"
    UNDER_REVIEW = "under_review"
    DECIDED = "decided"
    APPROVED = "approved"
    IMPLEMENTING = "implementing"
    IMPLEMENTED = "implemented"
    SUPERSEDED = "superseded"
    DEPRECATED = "deprecated"
    REVERTED = "reverted"


class DecisionCategory(StrEnum):
    """决策类别枚举。"""

    ARCHITECTURE = "architecture"
    TECHNOLOGY = "technology"
    DESIGN = "design"
    PROCESS = "process"
    REQUIREMENT = "requirement"
    SECURITY = "security"
    PERFORMANCE = "performance"
    COST = "cost"


class DecisionScope(StrEnum):
    """决策影响范围枚举。"""

    GLOBAL = "global"
    PROJECT = "project"
    MODULE = "module"
    COMPONENT = "component"


class DecisionCertainty(StrEnum):
    """决策确定性枚举。"""

    CONFIRMED = "confirmed"
    EVIDENCED = "evidenced"
    EXPLICIT = "explicit"
    INFERRED = "inferred"
    IMPLICIT = "implicit"
    TENTATIVE = "tentative"
    DISCUSSING = "discussing"
    UNCERTAIN = "uncertain"
    DISPUTED = "disputed"
    RETRACTED = "retracted"


class DecisionPriority(StrEnum):
    """决策优先级枚举。"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceType(StrEnum):
    """证据类型枚举。"""

    CODE_COMMIT = "code_commit"
    PULL_REQUEST = "pull_request"
    CONFIG_CHANGE = "config_change"
    DOCUMENT = "document"
    TEST_RESULT = "test_result"
    DEPLOYMENT = "deployment"
    MANUAL_CONFIRM = "manual_confirm"


class TimelineEventType(StrEnum):
    """时间线事件类型枚举。"""

    PROPOSED = "proposed"
    DISCUSSED = "discussed"
    DECIDED = "decided"
    APPROVED = "approved"
    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    CHANGED = "changed"
    SUPERSEDED = "superseded"
    REVERTED = "reverted"


class ConflictType(StrEnum):
    """冲突类型枚举。"""

    DIRECT_CONTRADICTION = "direct_contradiction"
    PARTIAL_OVERLAP = "partial_overlap"
    SUPERSEDES = "supersedes"
    UNRELATED = "unrelated"


class Alternative(BaseModel):
    """决策备选方案模型。"""

    name: str
    description: str
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    rejected_reason: str = ""

    model_config = ConfigDict(from_attributes=True)


class Evidence(BaseModel):
    """决策证据模型。"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: EvidenceType
    description: str
    reference: str
    verified: bool = False
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TimelineEvent(BaseModel):
    """时间线事件模型。"""

    timestamp: datetime
    type: TimelineEventType
    description: str
    actor: Optional[str] = None
    evidence_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class DecisionTimeline(BaseModel):
    """决策时间线模型。"""

    decision_id: str
    title: str
    events: list[TimelineEvent] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class Decision(BaseModel):
    """决策记忆主模型。"""

    # Core fields
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    summary: str
    context: str
    decision: str
    rationale: str

    # Structure fields
    alternatives: list[Alternative] = Field(default_factory=list)
    consequences: list[str] = Field(default_factory=list)

    # Classification fields
    category: DecisionCategory
    scope: DecisionScope = DecisionScope.PROJECT
    priority: DecisionPriority = DecisionPriority.MEDIUM

    # Relationship fields
    project_id: Optional[str] = None
    module_ids: list[str] = Field(default_factory=list)
    related_decisions: list[str] = Field(default_factory=list)
    supersedes: Optional[str] = None

    # Status fields
    status: DecisionStatus = DecisionStatus.PROPOSED
    certainty: DecisionCertainty = DecisionCertainty.UNCERTAIN
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    implemented_at: Optional[datetime] = None

    # Evidence and memory fields
    evidence: list[Evidence] = Field(default_factory=list)
    source_memories: list[str] = Field(default_factory=list)

    # Confidence and validation fields
    confidence: float = 0.0
    user_confirmed: bool = False
    quarantined: bool = False

    # Timestamp fields
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(from_attributes=True)
