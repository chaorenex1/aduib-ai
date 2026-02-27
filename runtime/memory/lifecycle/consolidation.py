"""记忆整合机制实现。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field

from runtime.memory.storage.adapter import StorageAdapter
from runtime.memory.types.base import Memory, MemoryType, MemoryLifecycle, MemoryMetadata, MemorySource

logger = logging.getLogger(__name__)


class ConsolidationTrigger(StrEnum):
    """整合触发条件枚举。"""

    SESSION_END = "session_end"
    PERIODIC_DAILY = "periodic_daily"
    PERIODIC_WEEKLY = "periodic_weekly"
    THRESHOLD = "threshold"
    MANUAL = "manual"


class ConsolidationStrategy(StrEnum):
    """整合策略枚举。"""

    SUMMARIZE = "summarize"
    MERGE = "merge"
    PROMOTE = "promote"
    EXTRACT_KNOWLEDGE = "extract_knowledge"


class ConsolidationAction(BaseModel):
    """整合动作数据结构。"""

    strategy: ConsolidationStrategy
    target_lifecycle: MemoryLifecycle
    reason: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ConsolidationResult(BaseModel):
    """整合结果数据结构。"""

    memories_evaluated: int = 0
    memories_promoted: int = 0
    memories_merged: int = 0
    memories_archived: int = 0
    new_memories_created: list[str] = Field(default_factory=list)


class Consolidation:
    """记忆整合服务。"""

    def __init__(self, storage: StorageAdapter) -> None:
        """初始化整合服务。

        Args:
            storage: 存储适配器实例。
        """
        self._storage = storage

    async def consolidate_session(self, session_id: str) -> list[Memory]:
        """整合会话记忆。

        将会话中的工作记忆整合为情景记忆。

        Args:
            session_id: 会话 ID。

        Returns:
            整合后产生的新记忆列表。
        """
        logger.info(f"开始整合会话记忆: {session_id}")

        # 获取会话中的所有记忆
        memories = await self._storage.list_by_session(session_id)
        working_memories = [memory for memory in memories if memory.type == MemoryType.WORKING]

        if not working_memories:
            logger.info(f"会话 {session_id} 中没有工作记忆，跳过整合")
            return []

        # 生成摘要
        summary = self._build_summary(working_memories)

        # 构建整合后的记忆
        consolidated_metadata = MemoryMetadata(
            session_id=session_id,
            source=MemorySource.CHAT.value,
            tags=self._extract_tags(working_memories),
        )

        consolidated_memory = Memory(
            type=MemoryType.EPISODIC,
            content=summary,
            importance=self._calculate_consolidated_importance(working_memories),
            metadata=consolidated_metadata,
        )

        # 保存整合后的记忆
        memory_id = await self._storage.save(consolidated_memory)
        consolidated_memory.id = memory_id

        logger.info(f"会话 {session_id} 整合完成，生成记忆 {memory_id}")
        return [consolidated_memory]

    async def consolidate_by_timerange(
        self, start: datetime, end: datetime, memory_type: MemoryType
    ) -> list[Memory]:
        """按时间范围整合记忆。

        Args:
            start: 开始时间。
            end: 结束时间。
            memory_type: 记忆类型。

        Returns:
            整合后产生的新记忆列表。
        """
        logger.info(f"按时间范围整合记忆: {start} - {end}, 类型: {memory_type}")

        # 尝试使用存储适配器的时间范围查询方法
        memories = []
        if hasattr(self._storage, 'list_by_timerange'):
            memories = await self._storage.list_by_timerange(start, end, memory_type)
        else:
            logger.warning("存储适配器不支持按时间范围查询，跳过整合")
            return []

        if not memories:
            logger.info(f"时间范围 {start} - {end} 内没有 {memory_type} 类型的记忆")
            return []

        # 按会话分组整合
        session_groups = {}
        for memory in memories:
            session_id = memory.metadata.session_id or "unknown"
            if session_id not in session_groups:
                session_groups[session_id] = []
            session_groups[session_id].append(memory)

        consolidated_memories = []
        for session_id, session_memories in session_groups.items():
            if len(session_memories) >= 2:  # 只有多个记忆才值得整合
                summary = self._build_summary(session_memories)
                consolidated_metadata = MemoryMetadata(
                    session_id=session_id if session_id != "unknown" else None,
                    source=MemorySource.CHAT.value,
                    tags=self._extract_tags(session_memories),
                )

                consolidated_memory = Memory(
                    type=MemoryType.EPISODIC,
                    content=f"时间段整合记忆 ({start.strftime('%Y-%m-%d %H:%M')} - {end.strftime('%Y-%m-%d %H:%M')}):\n{summary}",
                    importance=self._calculate_consolidated_importance(session_memories),
                    metadata=consolidated_metadata,
                )

                memory_id = await self._storage.save(consolidated_memory)
                consolidated_memory.id = memory_id
                consolidated_memories.append(consolidated_memory)

        logger.info(f"时间范围整合完成，生成 {len(consolidated_memories)} 个整合记忆")
        return consolidated_memories

    async def run_periodic_consolidation(self, trigger: ConsolidationTrigger) -> ConsolidationResult:
        """运行周期性整合。

        Args:
            trigger: 触发器类型。

        Returns:
            整合结果。
        """
        logger.info(f"执行周期性整合: {trigger}")

        result = ConsolidationResult()

        # 根据不同触发器设置时间范围
        now = datetime.now()
        if trigger == ConsolidationTrigger.PERIODIC_DAILY:
            start_time = now - timedelta(days=1)
            target_memories = await self._get_memories_for_consolidation(start_time, now, MemoryType.WORKING)
        elif trigger == ConsolidationTrigger.PERIODIC_WEEKLY:
            start_time = now - timedelta(days=7)
            target_memories = await self._get_memories_for_consolidation(start_time, now, MemoryType.WORKING)
        else:
            logger.info(f"触发器 {trigger} 暂不支持周期性整合")
            return result

        if not target_memories:
            logger.info(f"没有需要整合的记忆")
            return result

        result.memories_evaluated = len(target_memories)

        # 评估每个记忆是否需要整合
        consolidation_candidates = []
        for memory in target_memories:
            action = await self.evaluate_consolidation(memory)
            if action:
                consolidation_candidates.append((memory, action))

        # 执行整合
        for memory, action in consolidation_candidates:
            if action.strategy == ConsolidationStrategy.PROMOTE:
                # 提升记忆等级
                await self._promote_memory(memory, action.target_lifecycle)
                result.memories_promoted += 1
            elif action.strategy == ConsolidationStrategy.SUMMARIZE:
                # 创建摘要记忆
                summarized = await self._create_summary_memory([memory])
                if summarized:
                    result.new_memories_created.append(summarized.id)

        logger.info(f"周期性整合完成: {result}")
        return result

    async def evaluate_consolidation(self, memory: Memory) -> Optional[ConsolidationAction]:
        """评估记忆是否需要整合。

        Args:
            memory: 待评估的记忆。

        Returns:
            整合动作，如果不需要整合则返回 None。
        """
        # 简单的重要性评估
        if memory.importance >= 0.8:
            return ConsolidationAction(
                strategy=ConsolidationStrategy.PROMOTE,
                target_lifecycle=MemoryLifecycle.SHORT,
                reason="高重要性且频繁访问",
                confidence=0.9,
            )

        if memory.importance >= 0.5:
            return ConsolidationAction(
                strategy=ConsolidationStrategy.SUMMARIZE,
                target_lifecycle=MemoryLifecycle.SHORT,
                reason="中等重要性，建议摘要保存",
                confidence=0.6,
            )

        # 低重要性记忆不需要整合
        return None

    def _build_summary(self, memories: list[Memory]) -> str:
        """构建记忆摘要。

        Args:
            memories: 记忆列表。

        Returns:
            摘要内容。
        """
        if not memories:
            return ""

        # 简单的摘要生成：按重要性排序，取前几个
        sorted_memories = sorted(memories, key=lambda m: m.importance, reverse=True)
        lines = []
        for memory in sorted_memories[:5]:  # 最多取前5个重要记忆
            content = memory.content.strip()
            if content:
                lines.append(f"- {content}")

        return f"会话摘要（{len(memories)}个记忆）：\n" + "\n".join(lines)

    def _extract_tags(self, memories: list[Memory]) -> list[str]:
        """从记忆列表中提取标签。

        Args:
            memories: 记忆列表。

        Returns:
            去重后的标签列表。
        """
        tags = []
        for memory in memories:
            tags.extend(memory.metadata.tags)

        # 去重并保持顺序
        unique_tags = []
        for tag in tags:
            if tag and tag not in unique_tags:
                unique_tags.append(tag)

        return unique_tags

    def _calculate_consolidated_importance(self, memories: list[Memory]) -> float:
        """计算整合后的重要性分数。

        Args:
            memories: 记忆列表。

        Returns:
            整合后的重要性分数。
        """
        if not memories:
            return 0.0

        # 使用加权平均，高重要性记忆权重更大
        total_weight = 0.0
        weighted_sum = 0.0

        for memory in memories:
            weight = memory.importance + 0.1  # 避免零权重
            weighted_sum += memory.importance * weight
            total_weight += weight

        return min(1.0, weighted_sum / total_weight) if total_weight > 0 else 0.5

    async def _get_memories_for_consolidation(
        self, start: datetime, end: datetime, memory_type: MemoryType
    ) -> list[Memory]:
        """获取指定时间范围内需要整合的记忆。

        Args:
            start: 开始时间。
            end: 结束时间。
            memory_type: 记忆类型。

        Returns:
            符合条件的记忆列表。
        """
        # 如果存储适配器支持时间范围查询
        if hasattr(self._storage, 'list_by_timerange'):
            return await self._storage.list_by_timerange(start, end, memory_type)

        # 备选方案：通过其他方法获取记忆并过滤
        # 这里暂时返回空列表，实际实现中可以遍历所有会话的记忆进行过滤
        logger.warning("存储适配器不支持时间范围查询，无法获取目标记忆")
        return []

    async def _promote_memory(self, memory: Memory, target_lifecycle: MemoryLifecycle) -> bool:
        """提升记忆的生命周期等级。

        Args:
            memory: 要提升的记忆。
            target_lifecycle: 目标生命周期。

        Returns:
            是否提升成功。
        """
        # 更新记忆的生命周期相关字段
        updates = {
            "importance": min(1.0, memory.importance + 0.1),  # 提升重要性
            "decay_rate": max(0.001, memory.decay_rate * 0.5),  # 降低衰减率
        }

        # 如果记忆有分类信息，更新生命周期
        if "classification" in memory.metadata.extra:
            updates["metadata.extra.classification.lifecycle"] = target_lifecycle.value

        updated_memory = await self._storage.update(memory.id, updates)
        return updated_memory is not None

    async def _create_summary_memory(self, memories: list[Memory]) -> Optional[Memory]:
        """创建摘要记忆。

        Args:
            memories: 原始记忆列表。

        Returns:
            摘要记忆，如果创建失败则返回 None。
        """
        if not memories:
            return None

        summary_content = self._build_summary(memories)
        summary_metadata = MemoryMetadata(
            source=MemorySource.CHAT.value,
            tags=self._extract_tags(memories) + ["summary"],
        )

        summary_memory = Memory(
            type=MemoryType.SEMANTIC,  # 摘要通常是语义记忆
            content=f"自动生成摘要:\n{summary_content}",
            importance=self._calculate_consolidated_importance(memories),
            metadata=summary_metadata,
        )

        memory_id = await self._storage.save(summary_memory)
        summary_memory.id = memory_id
        return summary_memory