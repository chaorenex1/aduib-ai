"""Tests for decision recognizer."""

from __future__ import annotations

from runtime.memory.decision import (
    CertaintyAssessor,
    Decision,
    DecisionCategory,
    DecisionCertainty,
)
from runtime.memory.decision.recognizer import (
    DecisionRecognizer,
    RecognitionResult,
    SignalMatch,
    SignalType,
)


class TestSignalDetection:
    """Test signal detection functionality."""

    def test_detect_strong_signals_chinese(self):
        """Test detection of strong decision signals in Chinese."""
        recognizer = DecisionRecognizer(CertaintyAssessor())

        text = "经过讨论，我们决定使用 Redis 作为缓存解决方案"
        signals = recognizer.detect_signals(text)

        assert len(signals) >= 1
        strong_signals = [s for s in signals if s.signal_type == SignalType.STRONG]
        assert len(strong_signals) >= 1
        assert strong_signals[0].confidence_contribution == 0.8

    def test_detect_strong_signals_english(self):
        """Test detection of strong decision signals in English."""
        recognizer = DecisionRecognizer(CertaintyAssessor())

        text = "We decided to use PostgreSQL as our primary database"
        signals = recognizer.detect_signals(text)

        assert len(signals) >= 1
        strong_signals = [s for s in signals if s.signal_type == SignalType.STRONG]
        assert len(strong_signals) >= 1
        assert strong_signals[0].confidence_contribution == 0.8

    def test_detect_medium_signals(self):
        """Test detection of medium decision signals."""
        recognizer = DecisionRecognizer(CertaintyAssessor())

        text = "我们应该使用 TypeScript 而不是 JavaScript"
        signals = recognizer.detect_signals(text)

        medium_signals = [s for s in signals if s.signal_type == SignalType.MEDIUM]
        assert len(medium_signals) >= 1
        assert medium_signals[0].confidence_contribution == 0.5

    def test_detect_weak_signals(self):
        """Test detection of weak decision signals."""
        recognizer = DecisionRecognizer(CertaintyAssessor())

        text = "我们考虑使用 GraphQL 来替代 REST API"
        signals = recognizer.detect_signals(text)

        weak_signals = [s for s in signals if s.signal_type == SignalType.WEAK]
        assert len(weak_signals) >= 1
        assert weak_signals[0].confidence_contribution == 0.3

    def test_detect_change_signals(self):
        """Test detection of change decision signals."""
        recognizer = DecisionRecognizer(CertaintyAssessor())

        text = "我们正在将数据库从 MySQL 迁移到 PostgreSQL"
        signals = recognizer.detect_signals(text)

        change_signals = [s for s in signals if s.signal_type == SignalType.CHANGE]
        assert len(change_signals) >= 1
        assert change_signals[0].confidence_contribution == 0.1

    def test_detect_execution_signals(self):
        """Test detection of execution decision signals."""
        recognizer = DecisionRecognizer(CertaintyAssessor())

        text = "已完成配置 Redis 集群"
        signals = recognizer.detect_signals(text)

        execution_signals = [s for s in signals if s.signal_type == SignalType.EXECUTION]
        assert len(execution_signals) >= 1
        assert execution_signals[0].confidence_contribution == 0.2

    def test_detect_no_signals(self):
        """Test detection with neutral text containing no signals."""
        recognizer = DecisionRecognizer(CertaintyAssessor())

        text = "今天天气很好，适合写代码"
        signals = recognizer.detect_signals(text)

        assert len(signals) == 0


class TestConfidenceCalculation:
    """Test confidence calculation functionality."""

    def test_single_strong_signal(self):
        """Test confidence calculation with single strong signal."""
        recognizer = DecisionRecognizer(CertaintyAssessor())

        signals = [
            SignalMatch(
                signal_type=SignalType.STRONG,
                pattern=r"决定使用",
                matched_text="决定使用",
                confidence_contribution=0.8
            )
        ]

        confidence = recognizer.calculate_confidence(signals)
        assert confidence == 0.8

    def test_multiple_signals_accumulation(self):
        """Test confidence accumulation with multiple signals."""
        recognizer = DecisionRecognizer(CertaintyAssessor())

        signals = [
            SignalMatch(
                signal_type=SignalType.STRONG,
                pattern=r"决定使用",
                matched_text="决定使用",
                confidence_contribution=0.8
            ),
            SignalMatch(
                signal_type=SignalType.EXECUTION,
                pattern=r"已完成",
                matched_text="已完成",
                confidence_contribution=0.2
            )
        ]

        confidence = recognizer.calculate_confidence(signals)
        assert confidence == 1.0

    def test_confidence_caps_at_one(self):
        """Test that confidence calculation caps at 1.0."""
        recognizer = DecisionRecognizer(CertaintyAssessor())

        signals = [
            SignalMatch(
                signal_type=SignalType.STRONG,
                pattern=r"决定使用",
                matched_text="决定使用",
                confidence_contribution=0.8
            ),
            SignalMatch(
                signal_type=SignalType.STRONG,
                pattern=r"确定方案",
                matched_text="确定方案",
                confidence_contribution=0.8
            ),
            SignalMatch(
                signal_type=SignalType.EXECUTION,
                pattern=r"已完成",
                matched_text="已完成",
                confidence_contribution=0.2
            )
        ]

        confidence = recognizer.calculate_confidence(signals)
        assert confidence == 1.0


class TestRecognitionWorkflow:
    """Test complete recognition workflow."""

    def test_recognize_returns_decision_for_strong_signal(self):
        """Test that recognize() returns is_decision=True for strong signal."""
        recognizer = DecisionRecognizer(CertaintyAssessor())

        content = "我们决定使用 Redis 作为缓存系统"
        result = recognizer.recognize(content)

        assert result.is_decision is True
        assert result.confidence >= recognizer.CONFIDENCE_THRESHOLD
        assert result.decision is not None
        assert result.decision.title
        assert result.decision.decision

    def test_recognize_returns_false_below_threshold(self):
        """Test that recognize() returns is_decision=False below threshold."""
        recognizer = DecisionRecognizer(CertaintyAssessor())

        content = "今天天气很好，适合写代码"
        result = recognizer.recognize(content)

        assert result.is_decision is False
        assert result.confidence < recognizer.CONFIDENCE_THRESHOLD
        assert result.decision is None
        assert result.reason

    def test_recognize_populates_decision_on_success(self):
        """Test that recognize() populates Decision on success."""
        recognizer = DecisionRecognizer(CertaintyAssessor())

        content = "经过评估，我们最终决定使用 PostgreSQL 作为主数据库"
        result = recognizer.recognize(content)

        assert result.is_decision is True
        assert result.decision is not None
        assert result.decision.title
        assert result.decision.summary
        assert result.decision.decision == content
        assert result.decision.category in DecisionCategory
        assert result.decision.certainty in DecisionCertainty
        assert result.decision.confidence == result.confidence


class TestDecisionExtraction:
    """Test decision extraction functionality."""

    def test_extract_decision_creates_valid_model(self):
        """Test that extract_decision creates valid Decision model."""
        recognizer = DecisionRecognizer(CertaintyAssessor())

        content = "我们决定使用 TypeScript 来提高代码质量"
        confidence = 0.8
        signals = [
            SignalMatch(
                signal_type=SignalType.STRONG,
                pattern=r"决定使用",
                matched_text="决定使用",
                confidence_contribution=0.8
            )
        ]
        context = {"project_id": "test-project"}

        decision = recognizer.extract_decision(content, confidence, signals, context)

        assert isinstance(decision, Decision)
        assert decision.title
        assert decision.summary
        assert decision.decision == content
        assert decision.confidence == confidence
        assert decision.project_id == "test-project"
        assert decision.category in DecisionCategory
        assert decision.certainty in DecisionCertainty

    def test_infer_category_for_different_content(self):
        """Test category inference for different types of content."""
        recognizer = DecisionRecognizer(CertaintyAssessor())

        # Architecture content
        arch_content = "我们采用微服务架构来提高系统可扩展性"
        category = recognizer._infer_category(arch_content)
        assert category == DecisionCategory.ARCHITECTURE

        # Technology content
        tech_content = "选择 Redis 作为缓存框架"
        category = recognizer._infer_category(tech_content)
        assert category == DecisionCategory.TECHNOLOGY

        # Design content
        content = "采用观察者模式来实现事件通知"
        category = recognizer._infer_category(content)
        assert category == DecisionCategory.DESIGN

        # Default to technology
        generic_content = "我们做了一个重要决定"
        category = recognizer._infer_category(generic_content)
        assert category == DecisionCategory.TECHNOLOGY

    def test_extract_title_truncation(self):
        """Test title extraction and truncation."""
        recognizer = DecisionRecognizer(CertaintyAssessor())

        # Short content
        short_content = "使用 Redis"
        title = recognizer._extract_title(short_content)
        assert title == "使用 Redis"

        # Long content that needs truncation (>50 chars)
        long_content = (
            "这是一个非常非常非常长的决策内容，它明确地超过了五十个字符的限制，"
            "因此必须要被截断处理以确保标题长度保持合理范围内"
        )
        title = recognizer._extract_title(long_content)
        assert len(title) <= 50
        assert title.endswith("...")


class TestRecognitionResult:
    """Test RecognitionResult structure."""

    def test_recognition_result_structure(self):
        """Test RecognitionResult structure and fields."""
        result = RecognitionResult(
            is_decision=True,
            confidence=0.8,
            signals=[
                SignalMatch(
                    signal_type=SignalType.STRONG,
                    pattern=r"决定使用",
                    matched_text="决定使用",
                    confidence_contribution=0.8
                )
            ],
            decision=Decision(
                title="使用 Redis",
                summary="使用 Redis 作为缓存",
                context="",
                decision="我们决定使用 Redis",
                rationale="",
                category=DecisionCategory.TECHNOLOGY,
            ),
            reason="Strong signal detected"
        )

        assert result.is_decision is True
        assert result.confidence == 0.8
        assert len(result.signals) == 1
        assert result.decision is not None
        assert result.reason == "Strong signal detected"


class TestContextHandling:
    """Test context dictionary handling."""

    def test_context_dict_passed_through(self):
        """Test that context dict is properly passed through."""
        recognizer = DecisionRecognizer(CertaintyAssessor())

        content = "我们决定使用 MongoDB"
        context = {
            "project_id": "my-project",
            "source": "meeting-notes",
            "timestamp": "2024-01-01T10:00:00Z"
        }

        result = recognizer.recognize(content, context)

        assert result.is_decision is True
        assert result.decision.project_id == "my-project"
        # Note: other context fields would be stored in decision.context if implemented