"""记忆升级服务实现。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from runtime.memory.types.base import Memory, MemoryLifecycle
from runtime.memory.lifecycle.attention import AttentionScore, AttentionScorer
from runtime.memory.storage.adapter import StorageAdapter

logger = logging.getLogger(__name__)


class PromotionRule(BaseModel):
    """记忆升级规则。"""

    source_level: MemoryLifecycle
    target_level: MemoryLifecycle
    min_attention: float
    min_access_count: int = 0
    min_validations: int = 0
    no_negative_signals: bool = False
    no_strong_negative: bool = False
    trend_not_declining: bool = False


class PromotionEvent(BaseModel):
    """记忆升级事件。"""

    memory_id: str
    from_level: MemoryLifecycle
    to_level: MemoryLifecycle
    reason: str
    attention_score: float
    promoted_at: datetime


class PromotionResult(BaseModel):
    """批量升级结果。"""

    evaluated: int = 0
    promoted: int = 0
    skipped: int = 0
    events: list[PromotionEvent] = Field(default_factory=list)


# 升级规则配置
PROMOTION_RULES = {
    MemoryLifecycle.TRANSIENT: PromotionRule(
        source_level=MemoryLifecycle.TRANSIENT,
        target_level=MemoryLifecycle.SHORT,
        min_attention=0.4,
        min_access_count=2,
    ),
    MemoryLifecycle.SHORT: PromotionRule(
        source_level=MemoryLifecycle.SHORT,
        target_level=MemoryLifecycle.LONG,
        min_attention=0.7,
        min_validations=3,
        no_strong_negative=True,
    ),
    MemoryLifecycle.LONG: PromotionRule(
        source_level=MemoryLifecycle.LONG,
        target_level=MemoryLifecycle.PERMANENT,
        min_attention=0.9,
        min_validations=5,
        trend_not_declining=True,
        no_negative_signals=True,
    ),
}


class MemoryPromotion:
    """记忆升级服务。

    负责基于注意力评分和验证条件的记忆等级升级。
    """

    def __init__(self, storage: StorageAdapter, scorer: AttentionScorer) -> None:
        """初始化升级服务。

        Args:
            storage: 存储适配器。
            scorer: 注意力评分器。
        """
        self.storage = storage
        self.scorer = scorer

    def get_current_level(self, memory: Memory) -> MemoryLifecycle:
        """获取记忆当前的生命周期等级。

        Args:
            memory: 记忆对象。

        Returns:
            当前生命周期等级。
        """
        # 尝试从 metadata.extra.classification.lifecycle 获取
        classification = memory.metadata.extra.get("classification", {})
        if "lifecycle" in classification:
            return MemoryLifecycle(classification["lifecycle"])

        # 尝试从 metadata.extra.lifecycle 获取
        if "lifecycle" in memory.metadata.extra:
            return MemoryLifecycle(memory.metadata.extra["lifecycle"])

        # 默认为 TRANSIENT
        return MemoryLifecycle.TRANSIENT

    async def evaluate_promotion(self, memory: Memory) -> Optional[MemoryLifecycle]:
        """评估记忆是否应该升级。

        Args:
            memory: 记忆对象。

        Returns:
            目标升级等级，如果不需要升级则返回 None。
        """
        current_level = self.get_current_level(memory)

        # 如果已经是最高等级，不能再升级
        if current_level == MemoryLifecycle.PERMANENT:
            return None

        # 获取升级规则
        if current_level not in PROMOTION_RULES:
            return None

        rule = PROMOTION_RULES[current_level]

        # 获取注意力评分
        score = await self.scorer.compute_score(memory.id)

        # 检查规则条件
        if await self._check_rule(rule, score, memory):
            return rule.target_level

        return None

    async def promote(self, memory: Memory, target_level: MemoryLifecycle) -> PromotionEvent:
        """执行记忆升级。

        Args:
            memory: 记忆对象。
            target_level: 目标等级。

        Returns:
            升级事件。
        """
        from_level = self.get_current_level(memory)

        # 计算升级后的参数
        new_importance = self._calculate_new_importance(target_level)
        new_decay_rate = self._calculate_new_decay_rate(target_level)

        # 更新存储
        updates = {
            "importance": new_importance,
            "decay_rate": new_decay_rate,
        }

        # 更新生命周期信息到 metadata.extra
        current_extra = memory.metadata.extra.copy()
        current_extra["lifecycle"] = target_level
        updates["metadata.extra"] = current_extra

        await self.storage.update(memory.id, updates)

        # 创建升级事件
        score = await self.scorer.compute_score(memory.id)
        event = PromotionEvent(
            memory_id=memory.id,
            from_level=from_level,
            to_level=target_level,
            reason=f"Memory meets promotion criteria for {target_level}",
            attention_score=score.normalized_score,
            promoted_at=datetime.now(),
        )

        logger.info(
            "记忆升级: memory_id=%s, %s -> %s, attention=%.2f",
            memory.id, from_level, target_level, score.normalized_score
        )

        return event

    async def run_promotion_batch(self, memories: list[Memory]) -> PromotionResult:
        """批量评估和执行记忆升级。

        Args:
            memories: 记忆列表。

        Returns:
            批量升级结果。
        """
        result = PromotionResult()

        for memory in memories:
            result.evaluated += 1

            target_level = await self.evaluate_promotion(memory)
            if target_level is None:
                result.skipped += 1
                continue

            # 执行升级
            event = await self.promote(memory, target_level)
            result.events.append(event)
            result.promoted += 1

        logger.info(
            "批量升级完成: evaluated=%d, promoted=%d, skipped=%d",
            result.evaluated, result.promoted, result.skipped
        )

        return result

    async def _check_rule(self, rule: PromotionRule, score: AttentionScore, memory: Memory) -> bool:
        """检查升级规则是否满足。

        Args:
            rule: 升级规则。
            score: 注意力评分。
            memory: 记忆对象。

        Returns:
            是否满足规则条件。
        """
        # 检查最低注意力要求
        if score.normalized_score < rule.min_attention:
            return False

        # 检查访问次数要求
        access_count = memory.metadata.extra.get("access_count", 0)
        if access_count < rule.min_access_count:
            return False

        # 检查验证次数要求
        validation_count = memory.metadata.extra.get("validation_count", 0)
        if validation_count < rule.min_validations:
            return False

        # 检查无强负向信号要求
        if rule.no_strong_negative:
            if await self.scorer.has_strong_negative_signals(memory.id):
                return False

        # 检查无负向信号要求
        if rule.no_negative_signals:
            if await self.scorer.has_negative_signals(memory.id):
                return False

        # 检查趋势不下降要求
        if rule.trend_not_declining:
            if score.trend == "declining":
                return False

        return True

    def _calculate_new_importance(self, target_level: MemoryLifecycle) -> float:
        """计算升级后的重要性值。

        Args:
            target_level: 目标等级。

        Returns:
            新的重要性值。
        """
        importance_mapping = {
            MemoryLifecycle.TRANSIENT: 0.3,
            MemoryLifecycle.SHORT: 0.7,
            MemoryLifecycle.LONG: 0.85,
            MemoryLifecycle.PERMANENT: 0.95,
        }
        return importance_mapping.get(target_level, 0.5)

    def _calculate_new_decay_rate(self, target_level: MemoryLifecycle) -> float:
        """计算升级后的衰减率。

        Args:
            target_level: 目标等级。

        Returns:
            新的衰减率。
        """
        decay_mapping = {
            MemoryLifecycle.TRANSIENT: 0.02,
            MemoryLifecycle.SHORT: 0.005,
            MemoryLifecycle.LONG: 0.001,
            MemoryLifecycle.PERMANENT: 0.0,
        }
        return decay_mapping.get(target_level, 0.01)