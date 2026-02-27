"""测试 AgentMemory 集成桥接器。"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from runtime.memory.integration.agent_bridge import AgentMemoryFactory, UnifiedAgentMemory
from runtime.memory.manager import UnifiedMemoryManager
from runtime.memory.types.base import Memory, MemoryMetadata, MemoryType


class TestUnifiedAgentMemory:
    """测试 UnifiedAgentMemory 类。"""

    @pytest.fixture
    def mock_manager(self) -> AsyncMock:
        """模拟 UnifiedMemoryManager。"""
        return AsyncMock(spec=UnifiedMemoryManager)

    @pytest.fixture
    def agent_memory(self, mock_manager: AsyncMock) -> UnifiedAgentMemory:
        """创建 UnifiedAgentMemory 实例。"""
        return UnifiedAgentMemory(
            manager=mock_manager,
            agent_id="test_agent",
            session_id="test_session",
            max_turns=5,
        )

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_initialization(self, mock_manager: AsyncMock) -> None:
        """测试初始化。"""
        memory = UnifiedAgentMemory(mock_manager, "agent_1", "session_1", max_turns=10)

        assert memory._manager is mock_manager
        assert memory._agent_id == "agent_1"
        assert memory._session_id == "session_1"
        assert memory._max_turns == 10

    @pytest.mark.asyncio
    async def test_add_interaction_stores_working_memory(
        self, agent_memory: UnifiedAgentMemory, mock_manager: AsyncMock
    ) -> None:
        """测试添加交互存储为工作记忆。"""
        mock_manager.store.return_value = "memory_123"

        memory_id = await agent_memory.add_interaction(
            user_message="Hello",
            assistant_message="Hi there!"
        )

        assert memory_id == "memory_123"
        mock_manager.store.assert_called_once()

        # 检查存储的记忆参数
        call_args = mock_manager.store.call_args[0][0]
        assert isinstance(call_args, Memory)
        assert call_args.type == MemoryType.WORKING
        assert call_args.content == "User: Hello\nAssistant: Hi there!"
        assert call_args.metadata.session_id == "test_session"
        assert call_args.metadata.agent_id == "test_agent"
        assert call_args.metadata.source == "agent"

    @pytest.mark.asyncio
    async def test_retrieve_context_returns_short_and_long_term(
        self, agent_memory: UnifiedAgentMemory, mock_manager: AsyncMock
    ) -> None:
        """测试检索上下文返回短期和长期记忆。"""
        # 模拟 list_by_session 返回工作记忆
        working_memories = [
            Memory(
                type=MemoryType.WORKING,
                content="Working memory",
                metadata=MemoryMetadata(session_id="test_session")
            )
        ]
        mock_manager.list_by_session.return_value = working_memories

        # 模拟 retrieve 返回情景和语义记忆
        long_term_memories = [
            Memory(
                type=MemoryType.EPISODIC,
                content="Episodic memory",
                metadata=MemoryMetadata()
            ),
            Memory(
                type=MemoryType.SEMANTIC,
                content="Semantic memory",
                metadata=MemoryMetadata()
            )
        ]
        mock_manager.retrieve.return_value = long_term_memories

        context = await agent_memory.retrieve_context("test query")

        assert "short_term" in context
        assert "long_term" in context
        assert context["short_term"] == working_memories
        assert context["long_term"] == long_term_memories

        # 验证调用参数
        mock_manager.list_by_session.assert_called_once_with("test_session")
        mock_manager.retrieve.assert_called_once_with(
            query="test query",
            memory_types=[MemoryType.EPISODIC, MemoryType.SEMANTIC]
        )

    @pytest.mark.asyncio
    async def test_consolidate_delegates_to_manager(
        self, agent_memory: UnifiedAgentMemory, mock_manager: AsyncMock
    ) -> None:
        """测试整合记忆委托给管理器。"""
        consolidated_memories = [
            Memory(
                type=MemoryType.EPISODIC,
                content="Consolidated memory",
                metadata=MemoryMetadata()
            )
        ]
        mock_manager.consolidate.return_value = consolidated_memories

        result = await agent_memory.consolidate()

        assert result == consolidated_memories
        mock_manager.consolidate.assert_called_once_with("test_session")

    @pytest.mark.asyncio
    async def test_clear_memory_forgets_session_memories(
        self, agent_memory: UnifiedAgentMemory, mock_manager: AsyncMock
    ) -> None:
        """测试清理记忆删除会话记忆。"""
        memories = [
            Memory(id="mem_1", type=MemoryType.WORKING, content="Memory 1", metadata=MemoryMetadata()),
            Memory(id="mem_2", type=MemoryType.EPISODIC, content="Memory 2", metadata=MemoryMetadata()),
        ]
        mock_manager.list_by_session.return_value = memories
        mock_manager.forget.return_value = True

        await agent_memory.clear_memory()

        mock_manager.list_by_session.assert_called_once_with("test_session")
        assert mock_manager.forget.call_count == 2
        mock_manager.forget.assert_any_call("mem_1")
        mock_manager.forget.assert_any_call("mem_2")

    @pytest.mark.asyncio
    async def test_get_working_memory_count(
        self, agent_memory: UnifiedAgentMemory, mock_manager: AsyncMock
    ) -> None:
        """测试获取工作记忆数量。"""
        memories = [
            Memory(type=MemoryType.WORKING, content="Working 1", metadata=MemoryMetadata()),
            Memory(type=MemoryType.WORKING, content="Working 2", metadata=MemoryMetadata()),
            Memory(type=MemoryType.EPISODIC, content="Episodic", metadata=MemoryMetadata()),
        ]
        mock_manager.list_by_session.return_value = memories

        count = await agent_memory.get_working_memory_count()

        assert count == 2
        mock_manager.list_by_session.assert_called_once_with("test_session")

    @pytest.mark.asyncio
    async def test_auto_consolidation_when_max_turns_reached(
        self, mock_manager: AsyncMock
    ) -> None:
        """测试达到最大轮次时自动整合。"""
        agent_memory = UnifiedAgentMemory(mock_manager, "agent", "session", max_turns=2)

        # 模拟已有1个工作记忆
        mock_manager.list_by_session.return_value = [
            Memory(type=MemoryType.WORKING, content="Existing", metadata=MemoryMetadata())
        ]
        mock_manager.store.return_value = "new_memory"
        mock_manager.consolidate.return_value = []

        # 添加第2个交互，应该触发整合
        await agent_memory.add_interaction("User", "Assistant")

        # 验证调用了整合
        mock_manager.consolidate.assert_called_once_with("session")


class TestAgentMemoryFactory:
    """测试 AgentMemoryFactory 类。"""

    def test_create_agent_memory(self) -> None:
        """测试创建 UnifiedAgentMemory 实例。"""
        mock_manager = MagicMock(spec=UnifiedMemoryManager)

        agent_memory = AgentMemoryFactory.create(
            manager=mock_manager,
            agent_id="test_agent",
            session_id="test_session",
            max_turns=15
        )

        assert isinstance(agent_memory, UnifiedAgentMemory)
        assert agent_memory._manager is mock_manager
        assert agent_memory._agent_id == "test_agent"
        assert agent_memory._session_id == "test_session"
        assert agent_memory._max_turns == 15

    def test_create_with_default_max_turns(self) -> None:
        """测试使用默认最大轮次创建。"""
        mock_manager = MagicMock(spec=UnifiedMemoryManager)

        agent_memory = AgentMemoryFactory.create(
            manager=mock_manager,
            agent_id="test_agent",
            session_id="test_session"
        )

        assert agent_memory._max_turns == 20  # 默认值