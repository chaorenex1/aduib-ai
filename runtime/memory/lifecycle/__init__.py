"""记忆生命周期管理模块。"""

from .consolidation import (
    Consolidation,
    ConsolidationTrigger,
    ConsolidationStrategy,
    ConsolidationAction,
    ConsolidationResult,
)

__all__ = [
    "Consolidation",
    "ConsolidationTrigger",
    "ConsolidationStrategy",
    "ConsolidationAction",
    "ConsolidationResult",
]