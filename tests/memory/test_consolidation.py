import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

from runtime.memory.lifecycle.consolidation import (
    Consolidation,
    ConsolidationTrigger,
    ConsolidationStrategy,
    ConsolidationAction,
    ConsolidationResult
)
from runtime.memory.types.base import Memory, MemoryType, MemoryMetadata, MemoryLifecycle


class TestConsolidationTriggers:
    """测试整合触发条件。"""

    def test_consolidation_trigger_enum_exists(self):
        """测试ConsolidationTrigger枚举定义。"""
        assert ConsolidationTrigger.SESSION_END == "session_end"
        assert ConsolidationTrigger.PERIODIC_DAILY == "periodic_daily"
        assert ConsolidationTrigger.PERIODIC_WEEKLY == "periodic_weekly"
        assert ConsolidationTrigger.THRESHOLD == "threshold"
        assert ConsolidationTrigger.MANUAL == "manual"


class TestConsolidationStrategy:
    """测试整合策略枚举。"""

    def test_consolidation_strategy_enum_exists(self):
        """测试ConsolidationStrategy枚举定义。"""
        assert ConsolidationStrategy.SUMMARIZE == "summarize"
        assert ConsolidationStrategy.MERGE == "merge"
        assert ConsolidationStrategy.PROMOTE == "promote"
        assert ConsolidationStrategy.EXTRACT_KNOWLEDGE == "extract_knowledge"


class TestConsolidation:
    """测试记忆整合核心功能。"""

    @pytest.fixture
    def mock_storage(self):
        """模拟存储适配器。"""
        mock = AsyncMock()
        return mock

    @pytest.fixture
    def consolidation(self, mock_storage):
        """创建整合实例。"""
        return Consolidation(storage=mock_storage)

    @pytest.mark.asyncio
    async def test_consolidate_session_with_working_memories(self, consolidation, mock_storage):
        """测试整合包含工作记忆的会话。"""
        # 准备测试数据
        session_id = "test-session-123"
        working_memories = [
            Memory(
                id="mem1",
                type=MemoryType.WORKING,
                content="用户询问了Python基础语法",
                importance=0.7,
                metadata=MemoryMetadata(session_id=session_id)
            ),
            Memory(
                id="mem2",
                type=MemoryType.WORKING,
                content="解释了变量和函数定义",
                importance=0.8,
                metadata=MemoryMetadata(session_id=session_id)
            )
        ]

        # 模拟存储返回
        mock_storage.list_by_session.return_value = working_memories
        mock_storage.save.return_value = "consolidated-mem-id"

        # 执行整合
        result = await consolidation.consolidate_session(session_id)

        # 验证结果
        assert isinstance(result, list)
        assert len(result) > 0
        consolidated_memory = result[0]
        assert consolidated_memory.type == MemoryType.EPISODIC
        assert consolidated_memory.metadata.session_id == session_id

        # 验证存储调用
        mock_storage.list_by_session.assert_called_once_with(session_id)
        mock_storage.save.assert_called()

    @pytest.mark.asyncio
    async def test_consolidate_session_with_empty_session(self, consolidation, mock_storage):
        """测试整合空会话。"""
        session_id = "empty-session"
        mock_storage.list_by_session.return_value = []

        result = await consolidation.consolidate_session(session_id)

        assert result == []
        mock_storage.list_by_session.assert_called_once_with(session_id)
        mock_storage.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_consolidate_by_timerange(self, consolidation, mock_storage):
        """测试按时间范围整合记忆。"""
        start_time = datetime.now() - timedelta(hours=24)
        end_time = datetime.now()
        memory_type = MemoryType.WORKING

        # 模拟按时间范围查询记忆的方法
        mock_storage.list_by_timerange = AsyncMock()
        mock_storage.list_by_timerange.return_value = [
            Memory(
                id="time-mem-1",
                type=MemoryType.WORKING,
                content="时间范围内的记忆1",
                importance=0.7,
                metadata=MemoryMetadata(),
                created_at=datetime.now() - timedelta(hours=12)
            ),
            Memory(
                id="time-mem-2",
                type=MemoryType.WORKING,
                content="时间范围内的记忆2",
                importance=0.8,
                metadata=MemoryMetadata(),
                created_at=datetime.now() - timedelta(hours=6)
            )
        ]
        mock_storage.save.return_value = "timerange-consolidated"

        result = await consolidation.consolidate_by_timerange(start_time, end_time, memory_type)

        assert isinstance(result, list)
        if result:  # 如果有实际的整合结果
            assert len(result) > 0
            mock_storage.list_by_timerange.assert_called_once_with(start_time, end_time, memory_type)
            mock_storage.save.assert_called()

    @pytest.mark.asyncio
    async def test_run_periodic_consolidation(self, consolidation):
        """测试周期性整合执行。"""
        trigger = ConsolidationTrigger.PERIODIC_DAILY

        result = await consolidation.run_periodic_consolidation(trigger)

        assert isinstance(result, ConsolidationResult)
        assert result.memories_evaluated >= 0
        assert result.memories_promoted >= 0
        assert result.memories_merged >= 0
        assert result.memories_archived >= 0
        assert isinstance(result.new_memories_created, list)

    @pytest.mark.asyncio
    async def test_evaluate_consolidation_for_high_importance_memory(self, consolidation):
        """测试评估高重要性记忆的整合条件。"""
        memory = Memory(
            id="high-importance-mem",
            type=MemoryType.WORKING,
            content="非常重要的用户偏好设置",
            importance=0.9,
            metadata=MemoryMetadata()
        )

        action = await consolidation.evaluate_consolidation(memory)

        assert action is not None
        assert isinstance(action, ConsolidationAction)

    @pytest.mark.asyncio
    async def test_evaluate_consolidation_for_low_importance_memory(self, consolidation):
        """测试评估低重要性记忆的整合条件。"""
        memory = Memory(
            id="low-importance-mem",
            type=MemoryType.WORKING,
            content="临时性的问候语",
            importance=0.1,
            metadata=MemoryMetadata()
        )

        action = await consolidation.evaluate_consolidation(memory)

        # 低重要性记忆可能不需要整合
        assert action is None or isinstance(action, ConsolidationAction)


class TestConsolidationResult:
    """测试整合结果数据结构。"""

    def test_consolidation_result_creation(self):
        """测试ConsolidationResult创建。"""
        result = ConsolidationResult(
            memories_evaluated=10,
            memories_promoted=3,
            memories_merged=2,
            memories_archived=1,
            new_memories_created=["mem-1", "mem-2"]
        )

        assert result.memories_evaluated == 10
        assert result.memories_promoted == 3
        assert result.memories_merged == 2
        assert result.memories_archived == 1
        assert result.new_memories_created == ["mem-1", "mem-2"]


class TestConsolidationAction:
    """测试整合动作数据结构。"""

    def test_consolidation_action_creation(self):
        """测试ConsolidationAction创建。"""
        action = ConsolidationAction(
            strategy=ConsolidationStrategy.PROMOTE,
            target_lifecycle=MemoryLifecycle.SHORT,
            reason="高重要性且频繁访问"
        )

        assert action.strategy == ConsolidationStrategy.PROMOTE
        assert action.target_lifecycle == MemoryLifecycle.SHORT
        assert action.reason == "高重要性且频繁访问"
        assert action.confidence == 0.5  # 默认值

    def test_consolidation_action_with_confidence(self):
        """测试带置信度的ConsolidationAction创建。"""
        action = ConsolidationAction(
            strategy=ConsolidationStrategy.MERGE,
            target_lifecycle=MemoryLifecycle.LONG,
            reason="相似内容合并",
            confidence=0.85
        )

        assert action.confidence == 0.85


class TestConsolidationIntegration:
    """整合功能的集成测试。"""

    @pytest.fixture
    def mock_storage(self):
        """模拟存储适配器。"""
        mock = AsyncMock()
        return mock

    @pytest.fixture
    def consolidation(self, mock_storage):
        """创建整合实例。"""
        return Consolidation(storage=mock_storage)

    @pytest.mark.asyncio
    async def test_consolidate_mixed_memory_types(self, consolidation, mock_storage):
        """测试包含不同记忆类型的会话整合。"""
        session_id = "mixed-session-456"
        memories = [
            Memory(
                id="working1",
                type=MemoryType.WORKING,
                content="用户问题1",
                importance=0.7,
                metadata=MemoryMetadata(session_id=session_id, tags=["python", "基础"])
            ),
            Memory(
                id="episodic1",
                type=MemoryType.EPISODIC,
                content="之前的对话",
                importance=0.5,
                metadata=MemoryMetadata(session_id=session_id)
            ),
            Memory(
                id="working2",
                type=MemoryType.WORKING,
                content="用户问题2",
                importance=0.8,
                metadata=MemoryMetadata(session_id=session_id, tags=["进阶"])
            )
        ]

        mock_storage.list_by_session.return_value = memories
        mock_storage.save.return_value = "consolidated-mixed-id"

        result = await consolidation.consolidate_session(session_id)

        assert len(result) == 1
        consolidated = result[0]
        assert consolidated.type == MemoryType.EPISODIC
        # 应该只整合WORKING类型的记忆
        assert "用户问题1" in consolidated.content
        assert "用户问题2" in consolidated.content
        assert "之前的对话" not in consolidated.content
        # 标签应该被合并
        assert "python" in consolidated.metadata.tags
        assert "基础" in consolidated.metadata.tags
        assert "进阶" in consolidated.metadata.tags

    @pytest.mark.asyncio
    async def test_consolidate_session_importance_calculation(self, consolidation, mock_storage):
        """测试会话整合的重要性计算。"""
        session_id = "importance-test"
        memories = [
            Memory(
                id="low", type=MemoryType.WORKING, content="低重要性", importance=0.2,
                metadata=MemoryMetadata(session_id=session_id)
            ),
            Memory(
                id="high", type=MemoryType.WORKING, content="高重要性", importance=0.9,
                metadata=MemoryMetadata(session_id=session_id)
            ),
        ]

        mock_storage.list_by_session.return_value = memories
        mock_storage.save.return_value = "importance-consolidated"

        result = await consolidation.consolidate_session(session_id)

        assert len(result) == 1
        consolidated = result[0]
        # 整合后的重要性应该倾向于更重要的记忆
        assert consolidated.importance > 0.5
        assert consolidated.importance <= 1.0

    @pytest.mark.asyncio
    async def test_evaluate_consolidation_edge_cases(self, consolidation):
        """测试整合评估的边界情况。"""
        # 测试恰好在阈值的记忆
        memory_threshold = Memory(
            id="threshold",
            type=MemoryType.WORKING,
            content="阈值记忆",
            importance=0.8,  # 恰好等于高重要性阈值
            metadata=MemoryMetadata()
        )

        action = await consolidation.evaluate_consolidation(memory_threshold)
        assert action is not None
        assert action.strategy == ConsolidationStrategy.PROMOTE
        assert action.target_lifecycle == MemoryLifecycle.SHORT

        # 测试中等重要性记忆
        memory_medium = Memory(
            id="medium",
            type=MemoryType.WORKING,
            content="中等记忆",
            importance=0.6,
            metadata=MemoryMetadata()
        )

        action_medium = await consolidation.evaluate_consolidation(memory_medium)
        assert action_medium is not None
        assert action_medium.strategy == ConsolidationStrategy.SUMMARIZE