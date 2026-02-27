"""遗忘机制测试。"""

from __future__ import annotations

import math
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from runtime.memory.types.base import Memory, MemoryType, MemoryLifecycle, MemoryMetadata
from runtime.memory.lifecycle.forgetting import (
    ForgettingReason,
    ForgettingCurve,
    Forgetting,
    ForgettingProtection,
    ForgettingResult,
)
from runtime.memory.lifecycle.attention import AttentionScore, AttentionScorer


@pytest.fixture
def mock_storage():
    """模拟存储适配器。"""
    storage = MagicMock()
    storage.update = AsyncMock()
    return storage


@pytest.fixture
def mock_scorer():
    """模拟注意力评分器。"""
    scorer = MagicMock(spec=AttentionScorer)
    scorer.compute_score = AsyncMock()
    return scorer


@pytest.fixture
def sample_memory():
    """创建示例记忆。"""
    return Memory(
        id="test-memory-1",
        type=MemoryType.SEMANTIC,
        content="Test memory content",
        metadata=MemoryMetadata(
            extra={
                "lifecycle": "short",
                "classification": {"lifecycle": "short"}
            }
        ),
        importance=0.5,
        decay_rate=0.01,
        accessed_at=datetime.now() - timedelta(hours=24),
    )


class TestForgettingReason:
    """测试遗忘原因枚举。"""

    def test_forgetting_reason_values(self):
        """测试遗忘原因的值。"""
        assert ForgettingReason.NATURAL_DECAY == "natural_decay"
        assert ForgettingReason.LOW_ATTENTION == "low_attention"
        assert ForgettingReason.TTL_EXPIRED == "ttl_expired"
        assert ForgettingReason.USER_REQUESTED == "user_requested"
        assert ForgettingReason.SPACE_PRESSURE == "space_pressure"


class TestForgettingCurve:
    """测试遗忘曲线。"""

    def test_base_strength_values(self):
        """测试基础强度值。"""
        curve = ForgettingCurve()

        # 测试不同生命周期的基础强度
        assert curve.BASE_STRENGTH[MemoryLifecycle.TRANSIENT] == 2  # 2小时
        assert curve.BASE_STRENGTH[MemoryLifecycle.SHORT] == 168  # 7天
        assert curve.BASE_STRENGTH[MemoryLifecycle.LONG] == 2160  # 90天
        assert curve.BASE_STRENGTH[MemoryLifecycle.PERMANENT] == float('inf')

    def test_compute_strength_without_attention(self):
        """测试计算强度 - 不包含注意力加成。"""
        curve = ForgettingCurve()
        memory = Memory(
            id="test",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=MemoryMetadata(extra={"lifecycle": "short"}),
            importance=0.5,
        )

        strength = curve.compute_strength(memory)
        assert strength == 168  # 基础强度，无注意力加成

    def test_compute_strength_with_attention_boost(self):
        """测试计算强度 - 包含注意力加成。"""
        curve = ForgettingCurve()

        # 设置记忆级别为 SHORT，基础强度168
        memory = Memory(
            id="test",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=MemoryMetadata(extra={"lifecycle": "short"}),
            importance=0.5,
        )

        # 模拟高注意力 (0.8)
        strength = curve.compute_strength(memory, attention_score=0.8)
        # 基础 168 * (1 + 0.8 * 0.5) = 168 * 1.4 = 235.2
        assert strength == 168 * 1.4

    def test_compute_strength_permanent_always_infinite(self):
        """测试永久记忆强度始终为无穷大。"""
        curve = ForgettingCurve()
        memory = Memory(
            id="test",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=MemoryMetadata(extra={"lifecycle": "permanent"}),
            importance=0.5,
        )

        strength = curve.compute_strength(memory, attention_score=1.0)
        assert strength == float('inf')

    def test_retention_rate_exponential_decay(self):
        """测试保持率的指数衰减。"""
        curve = ForgettingCurve()
        now = datetime.now()

        # 创建SHORT级别记忆，24小时前最后访问
        memory = Memory(
            id="test",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=MemoryMetadata(extra={"lifecycle": "short"}),
            accessed_at=now - timedelta(hours=24),
            importance=0.5,
        )

        retention = curve.retention_rate(memory, now)

        # 计算预期值：exp(-24/168) ≈ 0.867
        expected = math.exp(-24 / 168)
        assert abs(retention - expected) < 0.001

    def test_retention_rate_permanent_never_decays(self):
        """测试永久记忆的保持率永远为1。"""
        curve = ForgettingCurve()
        now = datetime.now()

        memory = Memory(
            id="test",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=MemoryMetadata(extra={"lifecycle": "permanent"}),
            accessed_at=now - timedelta(days=365),  # 1年前
            importance=0.5,
        )

        retention = curve.retention_rate(memory, now)
        assert retention == 1.0

    def test_retention_rate_with_attention_boost(self):
        """测试注意力加成对保持率的影响。"""
        curve = ForgettingCurve()
        now = datetime.now()

        memory = Memory(
            id="test",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=MemoryMetadata(extra={"lifecycle": "short"}),
            accessed_at=now - timedelta(hours=24),
            importance=0.5,
        )

        # 无注意力加成
        retention_no_boost = curve.retention_rate(memory, now)

        # 有注意力加成
        retention_with_boost = curve.retention_rate(memory, now, attention_score=0.8)

        # 有注意力加成的保持率应该更高
        assert retention_with_boost > retention_no_boost


class TestForgetting:
    """测试遗忘服务。"""

    def test_threshold_values(self):
        """测试阈值常量。"""
        forgetting = Forgetting(MagicMock(), MagicMock())
        assert forgetting.RETENTION_THRESHOLD == 0.2
        assert forgetting.ATTENTION_THRESHOLD == 0.1
        assert forgetting.ATTENTION_INACTIVE_DAYS == 30

    @pytest.mark.asyncio
    async def test_evaluate_forgetting_ttl_expired(self, mock_storage, mock_scorer):
        """测试TTL过期的遗忘评估。"""
        forgetting = Forgetting(mock_storage, mock_scorer)

        # TTL已过期的记忆
        memory = Memory(
            id="test",
            type=MemoryType.SEMANTIC,
            content="test",
            ttl=datetime.now() - timedelta(hours=1),  # 1小时前过期
            importance=0.8,
        )

        reason = await forgetting.evaluate_forgetting(memory)
        assert reason == ForgettingReason.TTL_EXPIRED

    @pytest.mark.asyncio
    async def test_evaluate_forgetting_low_retention(self, mock_storage, mock_scorer):
        """测试低保持率的遗忘评估。"""
        # 配置mock评分器返回中等注意力分数
        mock_scorer.compute_score.return_value = AttentionScore(
            memory_id="test",
            raw_score=1.0,
            normalized_score=0.5,  # 中等注意力，不会触发注意力遗忘
            signal_count=3,
            last_signal_at=datetime.now() - timedelta(days=5),
            trend="stable",
        )

        forgetting = Forgetting(mock_storage, mock_scorer)

        # 很久前访问的TRANSIENT记忆（保持率低）
        memory = Memory(
            id="test",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=MemoryMetadata(extra={"lifecycle": "transient"}),
            accessed_at=datetime.now() - timedelta(hours=24),  # 24小时前，对于2小时半衰期的TRANSIENT来说很久
            importance=0.5,
        )

        reason = await forgetting.evaluate_forgetting(memory)
        assert reason == ForgettingReason.NATURAL_DECAY

    @pytest.mark.asyncio
    async def test_evaluate_forgetting_low_attention_inactive(self, mock_storage, mock_scorer):
        """测试低注意力且长期无信号的遗忘评估。"""
        forgetting = Forgetting(mock_storage, mock_scorer)

        # 配置低注意力分数且长期无信号
        mock_scorer.compute_score.return_value = AttentionScore(
            memory_id="test",
            raw_score=0.05,
            normalized_score=0.05,  # 低于0.1阈值
            signal_count=1,
            last_signal_at=datetime.now() - timedelta(days=35),  # 35天前
            trend="declining",
        )

        memory = Memory(
            id="test",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=MemoryMetadata(extra={"lifecycle": "short"}),
            importance=0.5,
        )

        reason = await forgetting.evaluate_forgetting(memory)
        assert reason == ForgettingReason.LOW_ATTENTION

    @pytest.mark.asyncio
    async def test_evaluate_forgetting_permanent_protected(self, mock_storage, mock_scorer):
        """测试永久记忆不会被遗忘。"""
        forgetting = Forgetting(mock_storage, mock_scorer)

        memory = Memory(
            id="test",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=MemoryMetadata(extra={"lifecycle": "permanent"}),
            ttl=datetime.now() - timedelta(hours=1),  # 即使TTL过期
            importance=0.1,
        )

        reason = await forgetting.evaluate_forgetting(memory)
        assert reason is None

    @pytest.mark.asyncio
    async def test_evaluate_forgetting_frozen_protected(self, mock_storage, mock_scorer):
        """测试冻结记忆不会被遗忘。"""
        forgetting = Forgetting(mock_storage, mock_scorer)

        memory = Memory(
            id="test",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=MemoryMetadata(extra={"frozen": True}),
            ttl=datetime.now() - timedelta(hours=1),  # 即使TTL过期
            importance=0.1,
        )

        reason = await forgetting.evaluate_forgetting(memory)
        assert reason is None

    @pytest.mark.asyncio
    async def test_evaluate_forgetting_healthy_memory(self, mock_storage, mock_scorer):
        """测试健康记忆不会被遗忘。"""
        forgetting = Forgetting(mock_storage, mock_scorer)

        # 配置良好的注意力分数
        mock_scorer.compute_score.return_value = AttentionScore(
            memory_id="test",
            raw_score=1.5,
            normalized_score=0.7,  # 高于阈值
            signal_count=5,
            last_signal_at=datetime.now() - timedelta(days=5),  # 最近有信号
            trend="stable",
        )

        memory = Memory(
            id="test",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=MemoryMetadata(extra={"lifecycle": "short"}),
            accessed_at=datetime.now() - timedelta(hours=1),  # 最近访问
            importance=0.8,
        )

        reason = await forgetting.evaluate_forgetting(memory)
        assert reason is None

    @pytest.mark.asyncio
    async def test_forget_archives_memory(self, mock_storage, mock_scorer, sample_memory):
        """测试遗忘过程正确归档记忆。"""
        forgetting = Forgetting(mock_storage, mock_scorer)

        await forgetting.forget(sample_memory, ForgettingReason.NATURAL_DECAY)

        # 检查存储更新调用
        mock_storage.update.assert_called_once()
        call_args = mock_storage.update.call_args

        # 验证更新参数
        memory_id = call_args[0][0]
        updates = call_args[0][1]

        assert memory_id == sample_memory.id
        assert "metadata.extra.lifecycle" in updates
        assert updates["metadata.extra.lifecycle"] == "archived"
        assert "metadata.extra.archived_at" in updates
        assert "metadata.extra.archive_reason" in updates
        assert updates["metadata.extra.archive_reason"] == ForgettingReason.NATURAL_DECAY

    @pytest.mark.asyncio
    async def test_run_forgetting_batch(self, mock_storage, mock_scorer):
        """测试批量遗忘处理。"""
        # 配置mock评分器返回不同的注意力分数
        def mock_compute_score(memory_id: str):
            return AttentionScore(
                memory_id=memory_id,
                raw_score=1.0,
                normalized_score=0.5,  # 中等注意力，不会触发注意力遗忘
                signal_count=3,
                last_signal_at=datetime.now() - timedelta(days=5),
                trend="stable",
            )

        mock_scorer.compute_score.side_effect = mock_compute_score
        forgetting = Forgetting(mock_storage, mock_scorer)

        # 创建测试记忆
        memories = [
            Memory(
                id="memory1",
                type=MemoryType.SEMANTIC,
                content="test1",
                ttl=datetime.now() - timedelta(hours=1),  # 过期
                importance=0.5,
            ),
            Memory(
                id="memory2",
                type=MemoryType.SEMANTIC,
                content="test2",
                metadata=MemoryMetadata(extra={"lifecycle": "permanent"}),  # 受保护
                ttl=datetime.now() - timedelta(hours=1),
                importance=0.5,
            ),
            Memory(
                id="memory3",
                type=MemoryType.SEMANTIC,
                content="test3",
                metadata=MemoryMetadata(extra={"lifecycle": "transient"}),
                accessed_at=datetime.now() - timedelta(hours=24),  # 低保持率
                importance=0.5,
            ),
        ]

        result = await forgetting.run_forgetting_batch(memories)

        # 验证结果
        assert result.evaluated == 3
        assert result.forgotten == 2  # memory1 (TTL), memory3 (衰减)
        assert result.protected == 1  # memory2 (永久)
        assert result.reasons[ForgettingReason.TTL_EXPIRED] == 1
        assert result.reasons[ForgettingReason.NATURAL_DECAY] == 1


class TestForgettingProtection:
    """测试遗忘保护。"""

    @pytest.mark.asyncio
    async def test_protect_memory_temporary(self, mock_storage):
        """测试临时保护记忆。"""
        protection = ForgettingProtection(mock_storage)

        await protection.protect_memory("test-memory", duration_days=30)

        # 验证存储更新
        mock_storage.update.assert_called_once()
        call_args = mock_storage.update.call_args

        memory_id = call_args[0][0]
        updates = call_args[0][1]

        assert memory_id == "test-memory"
        assert "metadata.extra.protected_until" in updates
        # 保护时间应该是大约30天后（允许少量误差）
        protected_until_str = updates["metadata.extra.protected_until"]
        protected_until = datetime.fromisoformat(protected_until_str.replace('Z', '+00:00'))
        expected_time = datetime.now() + timedelta(days=30)
        assert abs((protected_until.replace(tzinfo=None) - expected_time).total_seconds()) < 60

    @pytest.mark.asyncio
    async def test_protect_memory_permanent(self, mock_storage):
        """测试永久冻结记忆。"""
        protection = ForgettingProtection(mock_storage)

        await protection.protect_memory("test-memory", duration_days=None)

        # 验证存储更新
        mock_storage.update.assert_called_once()
        call_args = mock_storage.update.call_args

        memory_id = call_args[0][0]
        updates = call_args[0][1]

        assert memory_id == "test-memory"
        assert "metadata.extra.frozen" in updates
        assert updates["metadata.extra.frozen"] is True

    @pytest.mark.asyncio
    async def test_unprotect_memory(self, mock_storage):
        """测试取消保护记忆。"""
        protection = ForgettingProtection(mock_storage)

        await protection.unprotect_memory("test-memory")

        # 验证存储更新
        mock_storage.update.assert_called_once()
        call_args = mock_storage.update.call_args

        memory_id = call_args[0][0]
        updates = call_args[0][1]

        assert memory_id == "test-memory"
        assert "$unset" in updates
        unset_fields = updates["$unset"]
        assert "metadata.extra.protected_until" in unset_fields
        assert "metadata.extra.frozen" in unset_fields

    def test_is_protected_with_protection_time(self):
        """测试检查保护状态 - 有保护时间。"""
        protection = ForgettingProtection(MagicMock())

        # 未来时间保护
        memory = Memory(
            id="test",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=MemoryMetadata(extra={
                "protected_until": (datetime.now() + timedelta(days=10)).isoformat()
            }),
            importance=0.5,
        )

        assert protection.is_protected(memory) is True

    def test_is_protected_expired_protection(self):
        """测试检查保护状态 - 保护已过期。"""
        protection = ForgettingProtection(MagicMock())

        # 过去时间保护
        memory = Memory(
            id="test",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=MemoryMetadata(extra={
                "protected_until": (datetime.now() - timedelta(days=10)).isoformat()
            }),
            importance=0.5,
        )

        assert protection.is_protected(memory) is False

    def test_is_protected_frozen(self):
        """测试检查保护状态 - 永久冻结。"""
        protection = ForgettingProtection(MagicMock())

        memory = Memory(
            id="test",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=MemoryMetadata(extra={"frozen": True}),
            importance=0.5,
        )

        assert protection.is_protected(memory) is True

    def test_is_protected_not_protected(self):
        """测试检查保护状态 - 无保护。"""
        protection = ForgettingProtection(MagicMock())

        memory = Memory(
            id="test",
            type=MemoryType.SEMANTIC,
            content="test",
            importance=0.5,
        )

        assert protection.is_protected(memory) is False


class TestForgettingResult:
    """测试遗忘结果模型。"""

    def test_forgetting_result_defaults(self):
        """测试遗忘结果的默认值。"""
        result = ForgettingResult()

        assert result.evaluated == 0
        assert result.forgotten == 0
        assert result.protected == 0
        assert result.reasons == {}

    def test_forgetting_result_with_data(self):
        """测试包含数据的遗忘结果。"""
        result = ForgettingResult(
            evaluated=100,
            forgotten=25,
            protected=5,
            reasons={
                ForgettingReason.NATURAL_DECAY: 15,
                ForgettingReason.TTL_EXPIRED: 10,
            }
        )

        assert result.evaluated == 100
        assert result.forgotten == 25
        assert result.protected == 5
        assert result.reasons[ForgettingReason.NATURAL_DECAY] == 15
        assert result.reasons[ForgettingReason.TTL_EXPIRED] == 10