"""记忆升级服务测试。"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

from runtime.memory.types.base import Memory, MemoryMetadata, MemoryType, MemoryLifecycle
from runtime.memory.lifecycle.promotion import (
    PromotionRule,
    PromotionEvent,
    PromotionResult,
    MemoryPromotion,
    PROMOTION_RULES
)
from runtime.memory.lifecycle.attention import AttentionScore, AttentionScorer
from runtime.memory.storage.adapter import StorageAdapter


class TestPromotionRule:
    """测试升级规则类。"""

    def test_promotion_rule_creation(self):
        """测试升级规则创建。"""
        rule = PromotionRule(
            source_level=MemoryLifecycle.TRANSIENT,
            target_level=MemoryLifecycle.SHORT,
            min_attention=0.4,
            min_access_count=2,
        )
        assert rule.source_level == MemoryLifecycle.TRANSIENT
        assert rule.target_level == MemoryLifecycle.SHORT
        assert rule.min_attention == 0.4
        assert rule.min_access_count == 2
        assert rule.min_validations == 0
        assert rule.no_negative_signals is False


class TestPromotionEvent:
    """测试升级事件类。"""

    def test_promotion_event_creation(self):
        """测试升级事件创建。"""
        event = PromotionEvent(
            memory_id="test-memory",
            from_level=MemoryLifecycle.TRANSIENT,
            to_level=MemoryLifecycle.SHORT,
            reason="meets promotion criteria",
            attention_score=0.6,
            promoted_at=datetime.now(),
        )
        assert event.memory_id == "test-memory"
        assert event.from_level == MemoryLifecycle.TRANSIENT
        assert event.to_level == MemoryLifecycle.SHORT


class TestMemoryPromotion:
    """测试记忆升级服务。"""

    @pytest.fixture
    def mock_storage(self):
        """Mock 存储适配器。"""
        return AsyncMock(spec=StorageAdapter)

    @pytest.fixture
    def mock_scorer(self):
        """Mock 注意力评分器。"""
        return AsyncMock(spec=AttentionScorer)

    @pytest.fixture
    def promotion_service(self, mock_storage, mock_scorer):
        """创建升级服务实例。"""
        return MemoryPromotion(mock_storage, mock_scorer)

    @pytest.fixture
    def sample_memory(self):
        """创建样本记忆。"""
        metadata = MemoryMetadata(extra={
            "lifecycle": MemoryLifecycle.TRANSIENT,
            "access_count": 3,
            "validation_count": 1,
        })
        return Memory(
            id="test-memory",
            type=MemoryType.SEMANTIC,
            content="test content",
            metadata=metadata,
            importance=0.5,
        )

    def test_get_current_level_from_metadata(self, promotion_service, sample_memory):
        """测试从元数据获取当前等级。"""
        level = promotion_service.get_current_level(sample_memory)
        assert level == MemoryLifecycle.TRANSIENT

    def test_get_current_level_default(self, promotion_service):
        """测试默认等级。"""
        memory = Memory(
            id="test",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=MemoryMetadata(),
        )
        level = promotion_service.get_current_level(memory)
        assert level == MemoryLifecycle.TRANSIENT

    def test_get_current_level_from_classification(self, promotion_service):
        """测试从分类信息获取当前等级。"""
        metadata = MemoryMetadata(extra={
            "classification": {"lifecycle": MemoryLifecycle.LONG}
        })
        memory = Memory(
            id="test",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=metadata,
        )
        level = promotion_service.get_current_level(memory)
        assert level == MemoryLifecycle.LONG

    @pytest.mark.asyncio
    async def test_evaluate_promotion_transient_to_short_success(self, promotion_service, mock_scorer):
        """测试 TRANSIENT → SHORT 升级成功。"""
        # 创建满足条件的记忆
        metadata = MemoryMetadata(extra={
            "lifecycle": MemoryLifecycle.TRANSIENT,
            "access_count": 3,  # >= 2
        })
        memory = Memory(
            id="test-memory",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=metadata,
        )

        # Mock 注意力评分器返回满足条件的分数
        mock_scorer.compute_score.return_value = AttentionScore(
            memory_id="test-memory",
            raw_score=1.0,
            normalized_score=0.5,  # >= 0.4
            signal_count=5,
            trend="rising",
        )

        result = await promotion_service.evaluate_promotion(memory)
        assert result == MemoryLifecycle.SHORT

    @pytest.mark.asyncio
    async def test_evaluate_promotion_transient_to_short_attention_too_low(self, promotion_service, mock_scorer):
        """测试 TRANSIENT → SHORT 升级失败（注意力得分过低）。"""
        metadata = MemoryMetadata(extra={
            "lifecycle": MemoryLifecycle.TRANSIENT,
            "access_count": 3,
        })
        memory = Memory(
            id="test-memory",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=metadata,
        )

        # Mock 注意力分数过低
        mock_scorer.compute_score.return_value = AttentionScore(
            memory_id="test-memory",
            raw_score=0.5,
            normalized_score=0.3,  # < 0.4
            signal_count=2,
            trend="stable",
        )

        result = await promotion_service.evaluate_promotion(memory)
        assert result is None

    @pytest.mark.asyncio
    async def test_evaluate_promotion_short_to_long_with_negative_signals(self, promotion_service, mock_scorer):
        """测试 SHORT → LONG 升级失败（有强负向信号）。"""
        metadata = MemoryMetadata(extra={
            "lifecycle": MemoryLifecycle.SHORT,
            "validation_count": 5,  # >= 3
        })
        memory = Memory(
            id="test-memory",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=metadata,
        )

        # Mock 满足注意力要求但有强负向信号
        mock_scorer.compute_score.return_value = AttentionScore(
            memory_id="test-memory",
            raw_score=2.0,
            normalized_score=0.8,  # >= 0.7
            signal_count=8,
            trend="rising",
        )
        mock_scorer.has_strong_negative_signals.return_value = True

        result = await promotion_service.evaluate_promotion(memory)
        assert result is None

    @pytest.mark.asyncio
    async def test_evaluate_promotion_long_to_permanent_declining_trend(self, promotion_service, mock_scorer):
        """测试 LONG → PERMANENT 升级失败（趋势下降）。"""
        metadata = MemoryMetadata(extra={
            "lifecycle": MemoryLifecycle.LONG,
            "validation_count": 8,  # >= 5
        })
        memory = Memory(
            id="test-memory",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=metadata,
        )

        # Mock 满足大部分条件但趋势下降
        mock_scorer.compute_score.return_value = AttentionScore(
            memory_id="test-memory",
            raw_score=3.0,
            normalized_score=0.95,  # >= 0.9
            signal_count=15,
            trend="declining",  # 趋势下降
        )
        mock_scorer.has_negative_signals.return_value = False

        result = await promotion_service.evaluate_promotion(memory)
        assert result is None

    @pytest.mark.asyncio
    async def test_evaluate_promotion_permanent_no_further_promotion(self, promotion_service):
        """测试 PERMANENT 级别不会进一步升级。"""
        metadata = MemoryMetadata(extra={
            "lifecycle": MemoryLifecycle.PERMANENT,
        })
        memory = Memory(
            id="test-memory",
            type=MemoryType.SEMANTIC,
            content="test",
            metadata=metadata,
        )

        result = await promotion_service.evaluate_promotion(memory)
        assert result is None

    @pytest.mark.asyncio
    async def test_promote_memory_updates_storage(self, promotion_service, mock_storage, sample_memory):
        """测试升级记忆时更新存储。"""
        target_level = MemoryLifecycle.SHORT

        # Mock 存储更新
        memory_dict = sample_memory.model_dump()
        memory_dict["importance"] = 0.7  # 升级后的重要性
        memory_dict["decay_rate"] = 0.005  # 升级后的衰减率
        updated_memory = Memory(**memory_dict)
        updated_memory.metadata.extra["lifecycle"] = target_level
        mock_storage.update.return_value = updated_memory

        event = await promotion_service.promote(sample_memory, target_level)

        # 验证存储更新调用
        mock_storage.update.assert_called_once()
        call_args = mock_storage.update.call_args
        assert call_args[0][0] == sample_memory.id  # memory_id

        updates = call_args[0][1]  # updates dict
        assert updates["importance"] == 0.7
        assert updates["decay_rate"] == 0.005

        # 验证事件
        assert event.memory_id == sample_memory.id
        assert event.from_level == MemoryLifecycle.TRANSIENT
        assert event.to_level == target_level
        assert "promotion criteria" in event.reason

    @pytest.mark.asyncio
    async def test_run_promotion_batch_mixed_results(self, promotion_service, mock_storage, mock_scorer):
        """测试批量升级处理混合结果。"""
        # 创建多个记忆
        memories = []
        for i in range(3):
            metadata = MemoryMetadata(extra={
                "lifecycle": MemoryLifecycle.TRANSIENT,
                "access_count": 5,
            })
            memory = Memory(
                id=f"memory-{i}",
                type=MemoryType.SEMANTIC,
                content=f"content {i}",
                metadata=metadata,
            )
            memories.append(memory)

        # Mock 评分器：前两个满足升级条件，第三个不满足
        def mock_compute_score(memory_id):
            if memory_id == "memory-2":
                return AttentionScore(
                    memory_id=memory_id,
                    raw_score=0.2,
                    normalized_score=0.2,  # 不满足
                    signal_count=1,
                    trend="stable",
                )
            return AttentionScore(
                memory_id=memory_id,
                raw_score=1.0,
                normalized_score=0.6,  # 满足
                signal_count=5,
                trend="rising",
            )

        mock_scorer.compute_score.side_effect = mock_compute_score

        # Mock 存储更新
        def mock_update(memory_id, updates):
            memory = next(m for m in memories if m.id == memory_id)
            updated = Memory(**memory.model_dump())
            updated.importance = updates["importance"]
            updated.decay_rate = updates["decay_rate"]
            return updated

        mock_storage.update.side_effect = mock_update

        result = await promotion_service.run_promotion_batch(memories)

        assert result.evaluated == 3
        assert result.promoted == 2  # 前两个升级成功
        assert result.skipped == 1   # 第三个跳过
        assert len(result.events) == 2

    def test_promotion_rules_configuration(self):
        """测试升级规则配置。"""
        # 验证 TRANSIENT → SHORT 规则
        assert MemoryLifecycle.TRANSIENT in PROMOTION_RULES
        transient_rule = PROMOTION_RULES[MemoryLifecycle.TRANSIENT]
        assert transient_rule.source_level == MemoryLifecycle.TRANSIENT
        assert transient_rule.target_level == MemoryLifecycle.SHORT
        assert transient_rule.min_attention == 0.4
        assert transient_rule.min_access_count == 2

        # 验证 SHORT → LONG 规则
        assert MemoryLifecycle.SHORT in PROMOTION_RULES
        short_rule = PROMOTION_RULES[MemoryLifecycle.SHORT]
        assert short_rule.source_level == MemoryLifecycle.SHORT
        assert short_rule.target_level == MemoryLifecycle.LONG
        assert short_rule.min_attention == 0.7
        assert short_rule.min_validations == 3
        assert short_rule.no_strong_negative is True

        # 验证 LONG → PERMANENT 规则
        assert MemoryLifecycle.LONG in PROMOTION_RULES
        long_rule = PROMOTION_RULES[MemoryLifecycle.LONG]
        assert long_rule.source_level == MemoryLifecycle.LONG
        assert long_rule.target_level == MemoryLifecycle.PERMANENT
        assert long_rule.min_attention == 0.9
        assert long_rule.min_validations == 5
        assert long_rule.trend_not_declining is True
        assert long_rule.no_negative_signals is True