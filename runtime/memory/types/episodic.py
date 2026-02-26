"""Episodic memory implementation for event timelines and user interaction history."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from runtime.memory.storage.adapter import StorageAdapter
from runtime.memory.types.base import Memory, MemoryMetadata, MemoryType

logger = logging.getLogger(__name__)


class EpisodicMemory:
    """Episodic memory processor that supports event timelines and user interaction history."""

    def __init__(self, storage_adapter: StorageAdapter) -> None:
        """初始化 episodic memory 处理器。

        Args:
            storage_adapter: 存储适配器实例，用于持久化记忆
        """
        self.storage = storage_adapter

    async def add_episode(
        self,
        content: str,
        session_id: str,
        user_id: Optional[str] = None,
        event_type: str = "interaction",
        duration: Optional[float] = None,
        importance: float = 0.5,
        sequence_number: Optional[int] = None
    ) -> str:
        """添加一个新的情景记忆事件。

        Args:
            content: 事件内容描述
            session_id: 会话 ID
            user_id: 用户 ID
            event_type: 事件类型（如 'chat', 'question', 'action' 等）
            duration: 事件持续时间（秒）
            importance: 重要性评分 (0.0-1.0)
            sequence_number: 序列号，如果未提供则自动生成

        Returns:
            str: 创建的记忆 ID
        """
        # 如果没有提供序列号，则获取该会话的下一个序列号
        if sequence_number is None:
            sequence_number = await self._get_next_sequence_number(session_id)

        # 构建 episode 元数据
        metadata = MemoryMetadata(
            session_id=session_id,
            user_id=user_id,
            extra={
                "event_type": event_type,
                "sequence_number": sequence_number
            }
        )

        # 添加持续时间信息（如果提供）
        if duration is not None:
            metadata.extra["duration"] = duration

        # 创建记忆对象
        memory = Memory(
            type=MemoryType.EPISODIC,
            content=content,
            metadata=metadata,
            importance=importance
        )

        # 保存到存储
        memory_id = await self.storage.save(memory)
        logger.debug(
            "Added episodic memory: session=%s, type=%s, sequence=%s",
            session_id, event_type, sequence_number
        )

        return memory_id

    async def get_episode(self, episode_id: str) -> Optional[Memory]:
        """获取单个情景记忆。

        Args:
            episode_id: 记忆 ID

        Returns:
            Optional[Memory]: 记忆对象，如果不存在则返回 None
        """
        return await self.storage.get(episode_id)

    async def get_timeline(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> list[Memory]:
        """获取按时间排序的事件时间线。

        Args:
            session_id: 会话 ID
            user_id: 用户 ID，如果提供则只返回该用户的事件
            start_time: 开始时间，如果提供则只返回此时间之后的事件
            end_time: 结束时间，如果提供则只返回此时间之前的事件

        Returns:
            list[Memory]: 按时间排序的记忆列表
        """
        # 从存储获取该会话的所有 episodic 记忆
        memories = await self.storage.list_by_session(session_id)

        # 过滤条件
        filtered_memories = []
        for memory in memories:
            # 确保是 episodic 类型
            if memory.type != MemoryType.EPISODIC:
                continue

            # 用户过滤
            if user_id is not None and memory.metadata.user_id != user_id:
                continue

            # 时间范围过滤
            if start_time is not None and memory.created_at < start_time:
                continue

            if end_time is not None and memory.created_at > end_time:
                continue

            filtered_memories.append(memory)

        # 按创建时间排序
        filtered_memories.sort(key=lambda m: m.created_at)

        return filtered_memories

    async def generate_session_summary(self, session_id: str) -> str:
        """生成会话摘要，将多个事件汇总成摘要文本。

        Args:
            session_id: 会话 ID

        Returns:
            str: 会话摘要文本
        """
        timeline = await self.get_timeline(session_id)

        if not timeline:
            return "该会话暂无记录的事件。"

        # 统计信息
        event_count = len(timeline)
        event_types = set()
        important_events = []
        all_content = []

        for memory in timeline:
            # 收集事件类型
            event_type = memory.metadata.extra.get("event_type", "unknown")
            event_types.add(event_type)

            # 收集所有内容用于关键词提取
            all_content.append(memory.content)

            # 收集重要事件
            if memory.importance > 0.7:
                important_events.append(memory.content[:100] + "..." if len(memory.content) > 100 else memory.content)

        # 生成摘要
        summary_parts = [
            f"会话包含{event_count}个事件",
            f"涉及事件类型: {', '.join(sorted(event_types))}"
        ]

        # 添加内容摘要（包含关键内容）
        content_summary = " ".join(all_content)[:200]
        if len(" ".join(all_content)) > 200:
            content_summary += "..."
        summary_parts.append(f"主要内容: {content_summary}")

        if important_events:
            summary_parts.append(f"重要事件: {'; '.join(important_events[:3])}")

        # 时间范围
        if timeline:
            duration = timeline[-1].created_at - timeline[0].created_at
            summary_parts.append(f"持续时间: {duration}")

        return "。".join(summary_parts) + "。"

    async def _get_next_sequence_number(self, session_id: str) -> int:
        """获取该会话的下一个序列号。

        Args:
            session_id: 会话 ID

        Returns:
            int: 下一个序列号
        """
        memories = await self.storage.list_by_session(session_id)

        # 过滤出 episodic 记忆并找到最大序列号
        max_sequence = 0
        for memory in memories:
            if memory.type == MemoryType.EPISODIC:
                sequence = memory.metadata.extra.get("sequence_number", 0)
                if isinstance(sequence, int):
                    max_sequence = max(max_sequence, sequence)

        return max_sequence + 1