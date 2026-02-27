"""Decision retraction mechanism.

This module provides functionality for retracting decisions that need to be
withdrawn due to various reasons such as user rejection, conflicts, or
invalidated evidence.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field

from .models import Decision, DecisionCertainty, DecisionStatus


class RetractionReason(StrEnum):
    """决策撤回原因枚举。"""

    USER_REJECTED = "user_rejected"
    CONFLICT_RESOLVED = "conflict_resolved"
    EVIDENCE_INVALIDATED = "evidence_invalidated"
    STALE_UNCONFIRMED = "stale_unconfirmed"
    SUPERSEDED = "superseded"
    ERROR = "error"


class RetractionResult(BaseModel):
    """决策撤回结果模型。"""

    success: bool
    decision_id: str
    reason: RetractionReason
    affected_memories: list[str] = Field(default_factory=list)
    retracted_at: datetime = Field(default_factory=datetime.now)
    retracted_by: Optional[str] = None
    notes: str = ""


class DecisionRetraction:
    """决策撤回处理器。"""

    @staticmethod
    def retract(
        decision: Decision,
        reason: RetractionReason,
        retracted_by: str | None = None,
        notes: str = ""
    ) -> tuple[Decision, RetractionResult]:
        """撤回决策。

        Args:
            decision: 要撤回的决策
            reason: 撤回原因
            retracted_by: 撤回人
            notes: 撤回备注

        Returns:
            tuple[Decision, RetractionResult]: 更新的决策和撤回结果
        """
        # 更新决策状态
        decision.certainty = DecisionCertainty.RETRACTED
        decision.quarantined = True
        decision.status = DecisionStatus.REVERTED
        decision.updated_at = datetime.now()

        # 创建撤回结果
        result = RetractionResult(
            success=True,
            decision_id=decision.id,
            reason=reason,
            affected_memories=decision.source_memories.copy(),  # 复制避免引用问题
            retracted_by=retracted_by,
            notes=notes
        )

        return decision, result

    @staticmethod
    def can_retract(decision: Decision) -> bool:
        """检查决策是否可以撤回。

        Args:
            decision: 要检查的决策

        Returns:
            bool: 是否可以撤回
        """
        return decision.certainty != DecisionCertainty.RETRACTED

    @staticmethod
    def bulk_retract(
        decisions: list[Decision],
        reason: RetractionReason,
        retracted_by: str | None = None
    ) -> list[RetractionResult]:
        """批量撤回决策。

        Args:
            decisions: 要撤回的决策列表
            reason: 撤回原因
            retracted_by: 撤回人

        Returns:
            list[RetractionResult]: 撤回结果列表
        """
        results = []

        for decision in decisions:
            if DecisionRetraction.can_retract(decision):
                _, result = DecisionRetraction.retract(decision, reason, retracted_by)
                results.append(result)

        return results