"""AgentMemory 与 UnifiedMemoryManager 的集成桥接器。"""

from __future__ import annotations

from typing import Any, Dict, List

from runtime.memory.manager import UnifiedMemoryManager
from runtime.memory.types.base import Memory, MemoryMetadata, MemoryType


class UnifiedAgentMemory:
    """统一记忆系统的 AgentMemory 适配器。

    将 AgentMemory 接口适配到 UnifiedMemoryManager，实现无缝集成。
    """

    def __init__(
        self,
        manager: UnifiedMemoryManager,
        agent_id: str,
        session_id: str,
        max_turns: int = 20,
    ) -> None:
        """初始化适配器。

        Args:
            manager: 统一记忆管理器实例。
            agent_id: 智能体 ID。
            session_id: 会话 ID。
            max_turns: 最大轮次，超过时触发整合。
        """
        self._manager = manager
        self._agent_id = agent_id
        self._session_id = session_id
        self._max_turns = max_turns

    async def add_interaction(self, user_message: str, assistant_message: str) -> str:
        """添加用户-助手交互记忆。

        Args:
            user_message: 用户消息。
            assistant_message: 助手消息。

        Returns:
            记忆 ID。
        """
        # 构建交互内容
        content = f"User: {user_message}\nAssistant: {assistant_message}"

        # 创建工作记忆
        memory = Memory(
            type=MemoryType.WORKING,
            content=content,
            metadata=MemoryMetadata(
                session_id=self._session_id,
                agent_id=self._agent_id,
                source="agent",
            ),
        )

        # 检查当前工作记忆数量
        working_count = await self.get_working_memory_count()

        # 存储记忆
        memory_id = await self._manager.store(memory)

        # 检查是否需要整合（添加后的数量）
        if working_count + 1 >= self._max_turns:
            await self.consolidate()

        return memory_id

    async def retrieve_context(self, query: str) -> Dict[str, List[Memory]]:
        """检索记忆上下文。

        Args:
            query: 查询字符串。

        Returns:
            包含短期和长期记忆的字典。
        """
        # 获取短期记忆（当前会话的工作记忆）
        session_memories = await self._get_session_memories()
        short_term = [memory for memory in session_memories if memory.type == MemoryType.WORKING]

        # 获取长期记忆（情景和语义记忆）
        long_term = await self._manager.retrieve(
            query=query,
            memory_types=[MemoryType.EPISODIC, MemoryType.SEMANTIC],
        )

        return {
            "short_term": short_term,
            "long_term": long_term,
        }

    async def consolidate(self) -> List[Memory]:
        """整合会话记忆。

        将工作记忆整合为情景记忆。

        Returns:
            整合后产生的新记忆列表。
        """
        return await self._manager.consolidate(self._session_id)

    async def clear_memory(self) -> None:
        """清理会话记忆。"""
        memories = await self._get_session_memories()
        for memory in memories:
            await self._manager.forget(memory.id)

    async def get_working_memory_count(self) -> int:
        """获取工作记忆数量。

        Returns:
            当前会话的工作记忆数量。
        """
        memories = await self._get_session_memories()
        return sum(1 for memory in memories if memory.type == MemoryType.WORKING)

    async def _get_session_memories(self) -> List[Memory]:
        """获取当前会话的所有记忆。

        Returns:
            会话记忆列表。
        """
        return await self._manager.list_by_session(self._session_id)


class AgentMemoryFactory:
    """AgentMemory 工厂类。"""

    @staticmethod
    def create(
        manager: UnifiedMemoryManager,
        agent_id: str,
        session_id: str,
        **kwargs: Any,
    ) -> UnifiedAgentMemory:
        """创建 UnifiedAgentMemory 实例。

        Args:
            manager: 统一记忆管理器。
            agent_id: 智能体 ID。
            session_id: 会话 ID。
            **kwargs: 额外参数，支持 max_turns。

        Returns:
            配置好的 UnifiedAgentMemory 实例。
        """
        max_turns = kwargs.get("max_turns", 20)
        return UnifiedAgentMemory(
            manager=manager,
            agent_id=agent_id,
            session_id=session_id,
            max_turns=max_turns,
        )