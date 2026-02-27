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
from .forgetting import (
    ForgettingReason,
    ForgettingCurve,
    Forgetting,
    ForgettingProtection,
    ForgettingResult,
)
from .scheduler import (
    ScheduleType,
    TaskType,
    ScheduledTask,
    TaskExecutionResult,
    MemoryLifecycleScheduler,
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
    "ForgettingReason",
    "ForgettingCurve",
    "Forgetting",
    "ForgettingProtection",
    "ForgettingResult",
    "ScheduleType",
    "TaskType",
    "ScheduledTask",
    "TaskExecutionResult",
    "MemoryLifecycleScheduler",
]