"""记忆生命周期管理模块。"""

from .consolidation import (
    Consolidation,
    ConsolidationTrigger,
    ConsolidationStrategy,
    ConsolidationAction,
    ConsolidationResult,
)
from .attention import (
    AttentionSignalType,
    SignalRecord,
    AttentionScore,
    AttentionScorer,
    SIGNAL_WEIGHTS,
)
from .promotion import (
    PromotionRule,
    PromotionEvent,
    PromotionResult,
    MemoryPromotion,
    PROMOTION_RULES,
)

__all__ = [
    "Consolidation",
    "ConsolidationTrigger",
    "ConsolidationStrategy",
    "ConsolidationAction",
    "ConsolidationResult",
    "AttentionSignalType",
    "SignalRecord",
    "AttentionScore",
    "AttentionScorer",
    "SIGNAL_WEIGHTS",
    "PromotionRule",
    "PromotionEvent",
    "PromotionResult",
    "MemoryPromotion",
    "PROMOTION_RULES",
]