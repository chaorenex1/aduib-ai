"""遗忘机制实现。"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field

from runtime.memory.lifecycle.attention import AttentionScorer
from runtime.memory.storage.adapter import StorageAdapter
from runtime.memory.types.base import Memory, MemoryLifecycle

logger = logging.getLogger(__name__)


def get_memory_lifecycle(memory: Memory) -> MemoryLifecycle:
    """从记忆对象中提取生命周期等级。

    Args:
        memory: 记忆对象。

    Returns:
        生命周期等级，默认为TRANSIENT。
    """
    # 检查直接的 lifecycle 字段
    lifecycle_str = memory.metadata.extra.get("lifecycle")
    if lifecycle_str:
        try:
            return MemoryLifecycle(lifecycle_str)
        except ValueError:
            pass

    # 检查 classification.lifecycle 字段
    classification = memory.metadata.extra.get("classification", {})
    if isinstance(classification, dict):
        lifecycle_str = classification.get("lifecycle")
        if lifecycle_str:
            try:
                return MemoryLifecycle(lifecycle_str)
            except ValueError:
                pass

    # 默认为TRANSIENT
    return MemoryLifecycle.TRANSIENT


class ForgettingReason(StrEnum):
    """遗忘原因枚举。"""

    NATURAL_DECAY = "natural_decay"
    LOW_ATTENTION = "low_attention"
    TTL_EXPIRED = "ttl_expired"
    USER_REQUESTED = "user_requested"
    SPACE_PRESSURE = "space_pressure"


class ForgettingCurve:
    """艾宾浩斯遗忘曲线实现。

    基于艾宾浩斯遗忘曲线公式：retention = e^(-t/S)
    其中 t 是时间间隔，S 是记忆强度。
    """

    # 基础强度配置（小时）- 表示记忆的半衰期
    BASE_STRENGTH: dict[MemoryLifecycle, float] = {
        MemoryLifecycle.TRANSIENT: 2,  # 2小时半衰期
        MemoryLifecycle.SHORT: 168,  # 7天
        MemoryLifecycle.LONG: 2160,  # 90天
        MemoryLifecycle.PERMANENT: float("inf"),  # 永不衰减
    }

    # 注意力对强度的最大加成比例
    MAX_ATTENTION_BOOST = 0.5

    def retention_rate(self, memory: Memory, now: datetime, attention_score: Optional[float] = None) -> float:
        """计算记忆保留率 (0-1) 基于艾宾浩斯曲线。

        Args:
            memory: 记忆对象。
            now: 当前时间。
            attention_score: 可选的注意力得分 (0-1)。

        Returns:
            保留率 (0-1)。
        """
        # 计算时间差（小时）
        time_diff = (now - memory.accessed_at).total_seconds() / 3600

        # 计算记忆强度
        strength = self.compute_strength(memory, attention_score)

        # 永久记忆不衰减
        if strength == float("inf"):
            return 1.0

        # 应用艾宾浩斯曲线: retention = e^(-t/S)
        retention = math.exp(-time_diff / strength)
        return max(0.0, min(1.0, retention))

    def compute_strength(self, memory: Memory, attention_score: Optional[float] = None) -> float:
        """计算记忆强度，基于生命周期等级和注意力得分。

        Args:
            memory: 记忆对象。
            attention_score: 可选的注意力得分 (0-1)。

        Returns:
            记忆强度（小时）。
        """
        # 获取生命周期等级
        lifecycle = get_memory_lifecycle(memory)

        # 获取基础强度
        base_strength = self.BASE_STRENGTH.get(lifecycle, self.BASE_STRENGTH[MemoryLifecycle.SHORT])

        # 永久记忆始终返回无穷大
        if base_strength == float("inf"):
            return base_strength

        # 应用注意力加成
        if attention_score is not None:
            attention_boost = attention_score * self.MAX_ATTENTION_BOOST
            return base_strength * (1 + attention_boost)

        return base_strength


class ForgettingResult(BaseModel):
    """遗忘操作结果。"""

    evaluated: int = 0
    forgotten: int = 0
    protected: int = 0
    reasons: dict[str, int] = Field(default_factory=dict)


class Forgetting:
    """遗忘服务。

    负责评估和执行记忆的遗忘操作，基于多种因素：
    - TTL过期
    - 艾宾浩斯遗忘曲线的自然衰减
    - 注意力得分过低且长期无信号
    """

    # 遗忘阈值常量
    RETENTION_THRESHOLD = 0.2  # 保留率低于20%时触发遗忘
    ATTENTION_THRESHOLD = 0.1  # 注意力低于10%时触发遗忘
    ATTENTION_INACTIVE_DAYS = 30  # 注意力信号不活跃天数阈值

    def __init__(self, storage: StorageAdapter, scorer: AttentionScorer):
        """初始化遗忘服务。

        Args:
            storage: 存储适配器。
            scorer: 注意力评分器。
        """
        self.storage = storage
        self.scorer = scorer
        self.curve = ForgettingCurve()

    async def evaluate_forgetting(self, memory: Memory) -> Optional[ForgettingReason]:
        """评估记忆是否应该被遗忘。

        Args:
            memory: 记忆对象。

        Returns:
            遗忘原因，如果不应该遗忘则返回None。
        """
        # 检查保护状态
        if self._is_protected(memory):
            return None

        now = datetime.now()

        # 检查TTL过期
        if memory.ttl is not None and memory.ttl < now:
            return ForgettingReason.TTL_EXPIRED

        # 检查自然衰减（保留率）
        # 先获取注意力得分用于强度计算
        attention_score_obj = await self.scorer.compute_score(memory.id)
        attention_score = attention_score_obj.normalized_score

        retention = self.curve.retention_rate(memory, now, attention_score)
        if retention < self.RETENTION_THRESHOLD:
            return ForgettingReason.NATURAL_DECAY

        # 检查注意力遗忘
        if attention_score < self.ATTENTION_THRESHOLD:
            # 额外检查：是否长期无信号
            if attention_score_obj.last_signal_at is not None:
                days_since_signal = (now - attention_score_obj.last_signal_at).days
                if days_since_signal > self.ATTENTION_INACTIVE_DAYS:
                    return ForgettingReason.LOW_ATTENTION

        return None

    async def forget(self, memory: Memory, reason: ForgettingReason) -> None:
        """执行遗忘操作（软删除 - 归档）。

        Args:
            memory: 记忆对象。
            reason: 遗忘原因。
        """
        now = datetime.now()

        # 准备更新字段
        updates = {
            "metadata.extra.lifecycle": "archived",
            "metadata.extra.archived_at": now.isoformat(),
            "metadata.extra.archive_reason": reason,
        }

        # 更新存储
        await self.storage.update(memory.id, updates)

        logger.info("记忆已归档: memory_id=%s, reason=%s", memory.id, reason)

    async def run_forgetting_batch(self, memories: list[Memory]) -> ForgettingResult:
        """批量执行遗忘评估和操作。

        Args:
            memories: 记忆列表。

        Returns:
            遗忘操作结果。
        """
        result = ForgettingResult()

        for memory in memories:
            result.evaluated += 1

            # 检查保护状态
            if self._is_protected(memory):
                result.protected += 1
                continue

            # 评估是否应该遗忘
            reason = await self.evaluate_forgetting(memory)
            if reason is not None:
                await self.forget(memory, reason)
                result.forgotten += 1

                # 统计原因
                reason_str = str(reason)
                result.reasons[reason_str] = result.reasons.get(reason_str, 0) + 1

        return result

    def _is_protected(self, memory: Memory) -> bool:
        """检查记忆是否受保护（不应被遗忘）。

        Args:
            memory: 记忆对象。

        Returns:
            是否受保护。
        """
        # 检查永久记忆
        lifecycle = get_memory_lifecycle(memory)
        if lifecycle == MemoryLifecycle.PERMANENT:
            return True

        # 检查冻结状态
        if memory.metadata.extra.get("frozen", False):
            return True

        return False


class ForgettingProtection:
    """遗忘保护机制。"""

    def __init__(self, storage: StorageAdapter):
        """初始化保护机制。

        Args:
            storage: 存储适配器。
        """
        self.storage = storage

    async def protect_memory(self, memory_id: str, duration_days: Optional[int] = None) -> None:
        """保护记忆不被遗忘。

        Args:
            memory_id: 记忆ID。
            duration_days: 保护时长（天数），None表示永久保护。
        """
        if duration_days is None:
            # 永久冻结
            updates = {
                "metadata.extra.frozen": True,
            }
        else:
            # 临时保护
            protect_until = datetime.now() + timedelta(days=duration_days)
            updates = {
                "metadata.extra.protected_until": protect_until.isoformat(),
            }

        await self.storage.update(memory_id, updates)

        logger.info("记忆已保护: memory_id=%s, duration_days=%s", memory_id, duration_days)

    async def unprotect_memory(self, memory_id: str) -> None:
        """取消记忆保护。

        Args:
            memory_id: 记忆ID。
        """
        updates = {
            "$unset": {
                "metadata.extra.protected_until": "",
                "metadata.extra.frozen": "",
            }
        }

        await self.storage.update(memory_id, updates)

        logger.info("记忆保护已取消: memory_id=%s", memory_id)

    def is_protected(self, memory: Memory) -> bool:
        """检查记忆是否受到保护。

        Args:
            memory: 记忆对象。

        Returns:
            是否受保护。
        """
        # 检查永久冻结
        if memory.metadata.extra.get("frozen", False):
            return True

        # 检查时间保护
        protected_until_str = memory.metadata.extra.get("protected_until")
        if protected_until_str:
            try:
                protected_until = datetime.fromisoformat(protected_until_str)
                # 移除时区信息进行比较
                if protected_until.tzinfo is not None:
                    protected_until = protected_until.replace(tzinfo=None)
                return datetime.now() < protected_until
            except (ValueError, TypeError):
                pass

        return False
