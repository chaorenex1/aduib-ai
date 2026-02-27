"""注意力评分系统实现。"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AttentionSignalType(StrEnum):
    """注意力信号类型枚举。

    每个信号类型都有一个对应的权重值，用于计算注意力得分。
    """

    # 强正向信号 (用户明确关心)
    EXPLICIT_SAVE = "explicit_save"
    EXPLICIT_IMPORTANT = "explicit_important"
    MANUAL_REFERENCE = "manual_reference"

    # 中正向信号 (隐式关心)
    REPEAT_ACCESS = "repeat_access"
    LONG_ENGAGEMENT = "long_engagement"
    FOLLOW_UP_QUERY = "follow_up_query"
    TASK_SUCCESS = "task_success"

    # 弱正向信号
    VIEW = "view"
    COPY = "copy"

    # 负向信号 (用户不关心)
    SKIP = "skip"
    DISMISS = "dismiss"
    NEGATIVE_FEEDBACK = "negative_feedback"
    CORRECTION = "correction"
    REPORT = "report"

    @property
    def weight(self) -> float:
        """获取信号类型的权重。"""
        return SIGNAL_WEIGHTS[self]


# 信号权重配置字典
SIGNAL_WEIGHTS = {
    # 强正向信号
    AttentionSignalType.EXPLICIT_SAVE: 1.0,
    AttentionSignalType.EXPLICIT_IMPORTANT: 0.9,
    AttentionSignalType.MANUAL_REFERENCE: 0.8,

    # 中正向信号
    AttentionSignalType.REPEAT_ACCESS: 0.5,
    AttentionSignalType.LONG_ENGAGEMENT: 0.4,
    AttentionSignalType.FOLLOW_UP_QUERY: 0.4,
    AttentionSignalType.TASK_SUCCESS: 0.6,

    # 弱正向信号
    AttentionSignalType.VIEW: 0.1,
    AttentionSignalType.COPY: 0.2,

    # 负向信号
    AttentionSignalType.SKIP: -0.3,
    AttentionSignalType.DISMISS: -0.5,
    AttentionSignalType.NEGATIVE_FEEDBACK: -0.8,
    AttentionSignalType.CORRECTION: -0.6,
    AttentionSignalType.REPORT: -1.0,
}

# 强负向信号阈值（权重绝对值）
STRONG_NEGATIVE_THRESHOLD = 0.7


class SignalRecord(BaseModel):
    """注意力信号记录。"""

    signal_type: AttentionSignalType
    memory_id: str
    timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class AttentionScore(BaseModel):
    """注意力评分结果。"""

    memory_id: str
    raw_score: float
    normalized_score: float  # 0-1 归一化分数
    signal_count: int
    last_signal_at: Optional[datetime] = None
    trend: str  # "rising" | "stable" | "declining"


class AttentionScorer:
    """注意力评分器。

    负责记录注意力信号、计算注意力得分和趋势分析。
    """

    RECENCY_HALF_LIFE_DAYS = 7  # 时间衰减半衰期（天）

    def __init__(self) -> None:
        """初始化评分器。"""
        # 内存存储信号记录 (memory_id -> signals)
        self._signals: dict[str, list[SignalRecord]] = {}

    async def record_signal(
        self, memory_id: str, signal_type: AttentionSignalType, payload: dict[str, Any] | None = None
    ) -> None:
        """记录注意力信号。

        Args:
            memory_id: 记忆 ID。
            signal_type: 信号类型。
            payload: 信号载荷数据。
        """
        if payload is None:
            payload = {}

        signal = SignalRecord(
            signal_type=signal_type,
            memory_id=memory_id,
            timestamp=datetime.now(),
            payload=payload,
        )

        if memory_id not in self._signals:
            self._signals[memory_id] = []

        self._signals[memory_id].append(signal)

        logger.debug(
            "记录注意力信号: memory_id=%s, signal_type=%s, payload=%s",
            memory_id, signal_type, payload
        )

    async def compute_score(self, memory_id: str) -> AttentionScore:
        """计算记忆的注意力得分。

        Args:
            memory_id: 记忆 ID。

        Returns:
            注意力评分结果。
        """
        signals = await self.get_signals(memory_id)

        if not signals:
            return AttentionScore(
                memory_id=memory_id,
                raw_score=0.0,
                normalized_score=0.0,
                signal_count=0,
                last_signal_at=None,
                trend="stable",
            )

        now = datetime.now()
        raw_score = 0.0

        # 计算原始分数（带时间衰减）
        for signal in signals:
            # 计算时间衰减因子
            age_days = (now - signal.timestamp).total_seconds() / (24 * 3600)
            recency_factor = 0.5 ** (age_days / self.RECENCY_HALF_LIFE_DAYS)

            # 信号权重
            weight = signal.signal_type.weight

            raw_score += weight * recency_factor

        # 归一化到 0-1
        normalized_score = self._normalize_score(raw_score, len(signals))

        # 计算趋势
        trend = self._compute_trend(signals)

        # 获取最后信号时间
        last_signal_at = max(signal.timestamp for signal in signals) if signals else None

        return AttentionScore(
            memory_id=memory_id,
            raw_score=raw_score,
            normalized_score=normalized_score,
            signal_count=len(signals),
            last_signal_at=last_signal_at,
            trend=trend,
        )

    async def get_signals(self, memory_id: str) -> list[SignalRecord]:
        """获取指定记忆的所有信号记录。

        Args:
            memory_id: 记忆 ID。

        Returns:
            信号记录列表。
        """
        return self._signals.get(memory_id, [])

    async def has_negative_signals(self, memory_id: str) -> bool:
        """检查是否有负向信号。

        Args:
            memory_id: 记忆 ID。

        Returns:
            是否存在负向信号。
        """
        signals = await self.get_signals(memory_id)
        return any(signal.signal_type.weight < 0 for signal in signals)

    async def has_strong_negative_signals(self, memory_id: str) -> bool:
        """检查是否有强负向信号。

        Args:
            memory_id: 记忆 ID。

        Returns:
            是否存在强负向信号。
        """
        signals = await self.get_signals(memory_id)
        return any(
            abs(signal.signal_type.weight) >= STRONG_NEGATIVE_THRESHOLD
            and signal.signal_type.weight < 0
            for signal in signals
        )

    def _normalize_score(self, raw_score: float, signal_count: int) -> float:
        """归一化评分到 0-1 区间。

        Args:
            raw_score: 原始分数。
            signal_count: 信号数量。

        Returns:
            归一化后的分数（0-1）。
        """
        if signal_count == 0:
            return 0.0

        # 基于信号数量的缩放因子
        scale = min(1.0, signal_count / 10)  # 10个信号达到满分潜力

        # 使用 Sigmoid 函数归一化
        sigmoid_value = 1 / (1 + math.exp(-raw_score))

        return scale * sigmoid_value

    def _compute_trend(self, signals: list[SignalRecord]) -> str:
        """计算注意力趋势。

        比较最近7天的信号与之前的信号数量。

        Args:
            signals: 信号记录列表。

        Returns:
            趋势字符串："rising", "stable", 或 "declining"。
        """
        if len(signals) < 2:
            return "stable"

        now = datetime.now()
        cutoff_time = now - timedelta(days=7)

        # 分类信号：最近7天 vs 之前
        recent_count = sum(1 for signal in signals if signal.timestamp >= cutoff_time)
        older_count = len(signals) - recent_count

        if older_count == 0:
            # 所有信号都是最近的
            return "rising"

        # 计算比率来判断趋势
        recent_ratio = recent_count / older_count if older_count > 0 else float("inf")

        if recent_ratio > 1.5:
            return "rising"
        elif recent_ratio < 0.5:
            return "declining"
        else:
            return "stable"