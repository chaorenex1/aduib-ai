"""测试注意力评分系统。"""

from __future__ import annotations

import math
import pytest
from datetime import datetime, timedelta

from runtime.memory.lifecycle.attention import (
    AttentionSignalType,
    SignalRecord,
    AttentionScore,
    AttentionScorer,
    SIGNAL_WEIGHTS,
)


class TestAttentionSignalType:
    """测试注意力信号类型。"""

    def test_signal_weights(self):
        """测试信号权重正确性。"""
        # 强正向信号
        assert AttentionSignalType.EXPLICIT_SAVE.weight == 1.0
        assert AttentionSignalType.EXPLICIT_IMPORTANT.weight == 0.9
        assert AttentionSignalType.MANUAL_REFERENCE.weight == 0.8

        # 中正向信号
        assert AttentionSignalType.REPEAT_ACCESS.weight == 0.5
        assert AttentionSignalType.LONG_ENGAGEMENT.weight == 0.4
        assert AttentionSignalType.FOLLOW_UP_QUERY.weight == 0.4
        assert AttentionSignalType.TASK_SUCCESS.weight == 0.6

        # 弱正向信号
        assert AttentionSignalType.VIEW.weight == 0.1
        assert AttentionSignalType.COPY.weight == 0.2

        # 负向信号
        assert AttentionSignalType.SKIP.weight == -0.3
        assert AttentionSignalType.DISMISS.weight == -0.5
        assert AttentionSignalType.NEGATIVE_FEEDBACK.weight == -0.8
        assert AttentionSignalType.CORRECTION.weight == -0.6
        assert AttentionSignalType.REPORT.weight == -1.0

    def test_signal_weights_config(self):
        """测试信号权重配置字典。"""
        assert len(SIGNAL_WEIGHTS) == len(AttentionSignalType)

        for signal_type in AttentionSignalType:
            assert signal_type in SIGNAL_WEIGHTS
            assert SIGNAL_WEIGHTS[signal_type] == signal_type.weight


class TestSignalRecord:
    """测试信号记录数据结构。"""

    def test_create_signal_record(self):
        """测试创建信号记录。"""
        now = datetime.now()
        record = SignalRecord(
            signal_type=AttentionSignalType.VIEW,
            memory_id="test-memory-001",
            timestamp=now,
            payload={"duration": 30}
        )

        assert record.signal_type == AttentionSignalType.VIEW
        assert record.memory_id == "test-memory-001"
        assert record.timestamp == now
        assert record.payload == {"duration": 30}

    def test_signal_record_defaults(self):
        """测试信号记录默认值。"""
        record = SignalRecord(
            signal_type=AttentionSignalType.COPY,
            memory_id="test-memory-002",
            timestamp=datetime.now()
        )

        assert record.payload == {}


class TestAttentionScore:
    """测试注意力评分数据结构。"""

    def test_create_attention_score(self):
        """测试创建注意力评分。"""
        last_signal = datetime.now()
        score = AttentionScore(
            memory_id="test-memory-001",
            raw_score=0.75,
            normalized_score=0.68,
            signal_count=5,
            last_signal_at=last_signal,
            trend="rising"
        )

        assert score.memory_id == "test-memory-001"
        assert score.raw_score == 0.75
        assert score.normalized_score == 0.68
        assert score.signal_count == 5
        assert score.last_signal_at == last_signal
        assert score.trend == "rising"

    def test_attention_score_optional_fields(self):
        """测试可选字段。"""
        score = AttentionScore(
            memory_id="test-memory-002",
            raw_score=0.0,
            normalized_score=0.0,
            signal_count=0,
            trend="stable"
        )

        assert score.last_signal_at is None


class TestAttentionScorer:
    """测试注意力评分器。"""

    @pytest.fixture
    def scorer(self):
        """创建评分器实例。"""
        return AttentionScorer()

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_record_signal(self, scorer):
        """测试记录信号。"""
        memory_id = "test-memory-001"

        await scorer.record_signal(memory_id, AttentionSignalType.VIEW)
        signals = await scorer.get_signals(memory_id)

        assert len(signals) == 1
        assert signals[0].signal_type == AttentionSignalType.VIEW
        assert signals[0].memory_id == memory_id
        assert signals[0].payload == {}

    @pytest.mark.asyncio
    async def test_record_signal_with_payload(self, scorer):
        """测试记录带载荷的信号。"""
        memory_id = "test-memory-002"
        payload = {"duration": 120, "interaction": "deep"}

        await scorer.record_signal(memory_id, AttentionSignalType.LONG_ENGAGEMENT, payload)
        signals = await scorer.get_signals(memory_id)

        assert len(signals) == 1
        assert signals[0].payload == payload

    @pytest.mark.asyncio
    async def test_compute_score_empty_signals(self, scorer):
        """测试计算空信号的评分。"""
        memory_id = "test-memory-empty"
        score = await scorer.compute_score(memory_id)

        assert score.memory_id == memory_id
        assert score.raw_score == 0.0
        assert score.normalized_score == 0.0
        assert score.signal_count == 0
        assert score.last_signal_at is None
        assert score.trend == "stable"

    @pytest.mark.asyncio
    async def test_compute_score_single_signal(self, scorer):
        """测试单个信号的评分计算。"""
        memory_id = "test-memory-single"

        await scorer.record_signal(memory_id, AttentionSignalType.VIEW)
        score = await scorer.compute_score(memory_id)

        assert score.memory_id == memory_id
        assert score.signal_count == 1
        # 单个VIEW信号，权重0.1，满时间衰减因子1.0
        assert score.raw_score == pytest.approx(0.1, rel=1e-3)
        assert score.last_signal_at is not None
        assert score.trend == "stable"  # 单个信号无趋势

    @pytest.mark.asyncio
    async def test_compute_score_multiple_signals(self, scorer):
        """测试多个信号的评分计算。"""
        memory_id = "test-memory-multi"

        # 记录多个不同类型的信号
        await scorer.record_signal(memory_id, AttentionSignalType.VIEW)
        await scorer.record_signal(memory_id, AttentionSignalType.COPY)
        await scorer.record_signal(memory_id, AttentionSignalType.REPEAT_ACCESS)

        score = await scorer.compute_score(memory_id)

        assert score.signal_count == 3
        # 预期原始分数: 0.1 + 0.2 + 0.5 = 0.8 (无时间衰减)
        assert score.raw_score == pytest.approx(0.8, rel=1e-3)
        assert score.normalized_score > 0.0

    @pytest.mark.asyncio
    async def test_compute_score_negative_signals(self, scorer):
        """测试负向信号的评分计算。"""
        memory_id = "test-memory-negative"

        # 混合正负信号
        await scorer.record_signal(memory_id, AttentionSignalType.EXPLICIT_SAVE)  # +1.0
        await scorer.record_signal(memory_id, AttentionSignalType.SKIP)  # -0.3
        await scorer.record_signal(memory_id, AttentionSignalType.NEGATIVE_FEEDBACK)  # -0.8

        score = await scorer.compute_score(memory_id)

        assert score.signal_count == 3
        # 预期原始分数: 1.0 - 0.3 - 0.8 = -0.1
        assert score.raw_score == pytest.approx(-0.1, rel=1e-3)

    @pytest.mark.asyncio
    async def test_time_decay(self, scorer):
        """测试时间衰减因子。"""
        memory_id = "test-memory-decay"

        # 创建过去的信号
        past_time = datetime.now() - timedelta(days=7)  # 7天前，半衰期衰减

        # 模拟过去时间的信号记录
        old_signal = SignalRecord(
            signal_type=AttentionSignalType.VIEW,
            memory_id=memory_id,
            timestamp=past_time
        )
        scorer._signals[memory_id] = [old_signal]

        score = await scorer.compute_score(memory_id)

        # 7天前的信号，衰减因子应该是 0.5^(7/7) = 0.5
        expected_raw = 0.1 * 0.5  # VIEW权重 * 衰减因子
        assert score.raw_score == pytest.approx(expected_raw, rel=1e-2)

    @pytest.mark.asyncio
    async def test_normalization(self, scorer):
        """测试归一化。"""
        memory_id = "test-memory-norm"

        # 记录10个强信号以测试归一化
        for _ in range(10):
            await scorer.record_signal(memory_id, AttentionSignalType.EXPLICIT_SAVE)

        score = await scorer.compute_score(memory_id)

        # 10个1.0权重的信号，应该接近满分
        assert score.raw_score == pytest.approx(10.0, rel=1e-3)
        assert score.signal_count == 10
        # 归一化后应该在0-1之间
        assert 0.0 <= score.normalized_score <= 1.0
        # 10个信号达到满分潜力，sigmoid函数应该趋近1
        assert score.normalized_score > 0.9

    @pytest.mark.asyncio
    async def test_trend_computation_rising(self, scorer):
        """测试上升趋势计算。"""
        memory_id = "test-memory-rising"

        # 模拟信号：过去有1个，最近有3个
        old_time = datetime.now() - timedelta(days=10)
        recent_time = datetime.now() - timedelta(days=3)

        old_signal = SignalRecord(
            signal_type=AttentionSignalType.VIEW,
            memory_id=memory_id,
            timestamp=old_time
        )
        recent_signals = [
            SignalRecord(
                signal_type=AttentionSignalType.VIEW,
                memory_id=memory_id,
                timestamp=recent_time
            ) for _ in range(3)
        ]

        scorer._signals[memory_id] = [old_signal] + recent_signals
        score = await scorer.compute_score(memory_id)

        # 最近3个 > 之前1个 * 1.5，应该是上升趋势
        assert score.trend == "rising"

    @pytest.mark.asyncio
    async def test_trend_computation_declining(self, scorer):
        """测试下降趋势计算。"""
        memory_id = "test-memory-declining"

        # 模拟信号：过去有4个，最近有1个
        old_time = datetime.now() - timedelta(days=10)
        recent_time = datetime.now() - timedelta(days=3)

        old_signals = [
            SignalRecord(
                signal_type=AttentionSignalType.VIEW,
                memory_id=memory_id,
                timestamp=old_time
            ) for _ in range(4)
        ]
        recent_signal = SignalRecord(
            signal_type=AttentionSignalType.VIEW,
            memory_id=memory_id,
            timestamp=recent_time
        )

        scorer._signals[memory_id] = old_signals + [recent_signal]
        score = await scorer.compute_score(memory_id)

        # 最近1个 < 之前4个 * 0.5，应该是下降趋势
        assert score.trend == "declining"

    @pytest.mark.asyncio
    async def test_trend_computation_stable(self, scorer):
        """测试稳定趋势计算。"""
        memory_id = "test-memory-stable"

        # 模拟信号：过去2个，最近2个
        old_time = datetime.now() - timedelta(days=10)
        recent_time = datetime.now() - timedelta(days=3)

        old_signals = [
            SignalRecord(
                signal_type=AttentionSignalType.VIEW,
                memory_id=memory_id,
                timestamp=old_time
            ) for _ in range(2)
        ]
        recent_signals = [
            SignalRecord(
                signal_type=AttentionSignalType.VIEW,
                memory_id=memory_id,
                timestamp=recent_time
            ) for _ in range(2)
        ]

        scorer._signals[memory_id] = old_signals + recent_signals
        score = await scorer.compute_score(memory_id)

        # 最近2个与之前2个基本相当，应该是稳定趋势
        assert score.trend == "stable"

    @pytest.mark.asyncio
    async def test_has_negative_signals(self, scorer):
        """测试检测负向信号。"""
        memory_id = "test-memory-neg-check"

        # 记录一个正向和一个负向信号
        await scorer.record_signal(memory_id, AttentionSignalType.VIEW)
        await scorer.record_signal(memory_id, AttentionSignalType.SKIP)

        has_negative = await scorer.has_negative_signals(memory_id)
        assert has_negative is True

    @pytest.mark.asyncio
    async def test_has_no_negative_signals(self, scorer):
        """测试无负向信号。"""
        memory_id = "test-memory-pos-only"

        # 只记录正向信号
        await scorer.record_signal(memory_id, AttentionSignalType.VIEW)
        await scorer.record_signal(memory_id, AttentionSignalType.COPY)

        has_negative = await scorer.has_negative_signals(memory_id)
        assert has_negative is False

    @pytest.mark.asyncio
    async def test_has_strong_negative_signals(self, scorer):
        """测试检测强负向信号。"""
        memory_id = "test-memory-strong-neg"

        # 记录强负向信号
        await scorer.record_signal(memory_id, AttentionSignalType.REPORT)  # -1.0权重

        has_strong_negative = await scorer.has_strong_negative_signals(memory_id)
        assert has_strong_negative is True

    @pytest.mark.asyncio
    async def test_has_no_strong_negative_signals(self, scorer):
        """测试无强负向信号。"""
        memory_id = "test-memory-weak-neg"

        # 记录弱负向信号
        await scorer.record_signal(memory_id, AttentionSignalType.SKIP)  # -0.3权重

        has_strong_negative = await scorer.has_strong_negative_signals(memory_id)
        assert has_strong_negative is False

    @pytest.mark.asyncio
    async def test_multiple_memories(self, scorer):
        """测试多个记忆的信号隔离。"""
        memory1 = "test-memory-001"
        memory2 = "test-memory-002"

        await scorer.record_signal(memory1, AttentionSignalType.VIEW)
        await scorer.record_signal(memory2, AttentionSignalType.COPY)

        signals1 = await scorer.get_signals(memory1)
        signals2 = await scorer.get_signals(memory2)

        assert len(signals1) == 1
        assert len(signals2) == 1
        assert signals1[0].signal_type == AttentionSignalType.VIEW
        assert signals2[0].signal_type == AttentionSignalType.COPY

    @pytest.mark.asyncio
    async def test_recency_half_life_constant(self, scorer):
        """测试时间衰减半衰期常数。"""
        assert scorer.RECENCY_HALF_LIFE_DAYS == 7