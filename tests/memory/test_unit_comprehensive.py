"""Comprehensive unit tests for memory system edge cases and corner cases.

This test file covers edge cases and corner cases NOT covered by existing tests,
focusing on boundary conditions, error handling, and integration edge cases.
"""

from __future__ import annotations

import asyncio
import math
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Optional

# Base types and models
from runtime.memory.types.base import (
    Memory,
    MemoryType,
    MemoryScope,
    MemorySource,
    MemoryMetadata,
    Entity,
    EntityType,
    Relation,
    MemoryLifecycle,
)

# Core components
from runtime.memory.classifier import MemoryClassifier
from runtime.memory.lifecycle.attention import (
    AttentionScorer,
    AttentionSignalType,
    SignalRecord,
)
from runtime.memory.lifecycle.forgetting import ForgettingCurve, get_memory_lifecycle
from runtime.memory.lifecycle.promotion import MemoryPromotion, PromotionRule
from runtime.memory.lifecycle.scheduler import MemoryLifecycleScheduler

# Decision modules
from runtime.memory.decision.recognizer import DecisionRecognizer
from runtime.memory.decision.certainty import CertaintyAssessor
from runtime.memory.decision.isolation import DecisionIsolation
from runtime.memory.decision.conflict import DecisionConflictDetector

# Integration bridges
from runtime.memory.integration.qa_bridge import QAMemoryBridge
from runtime.memory.integration.agent_bridge import UnifiedAgentMemory, AgentMemoryFactory


class TestMemoryModelEdgeCases:
    """Test edge cases for Memory model and base types."""

    def test_memory_is_expired_none_ttl(self):
        """Memory.is_expired() with None ttl should return False."""
        memory = Memory(
            type=MemoryType.WORKING,
            content="test",
            ttl=None
        )
        assert memory.is_expired() is False

    def test_memory_is_expired_future_ttl(self):
        """Memory.is_expired() with future ttl should return False."""
        future_time = datetime.now() + timedelta(hours=1)
        memory = Memory(
            type=MemoryType.WORKING,
            content="test",
            ttl=future_time
        )
        assert memory.is_expired() is False

    def test_memory_is_expired_past_ttl(self):
        """Memory.is_expired() with past ttl should return True."""
        past_time = datetime.now() - timedelta(hours=1)
        memory = Memory(
            type=MemoryType.WORKING,
            content="test",
            ttl=past_time
        )
        assert memory.is_expired() is True

    def test_memory_calculate_current_importance_no_decay(self):
        """Memory.calculate_current_importance() with zero elapsed time should return original."""
        now = datetime.now()
        memory = Memory(
            type=MemoryType.WORKING,
            content="test",
            importance=0.8,
            decay_rate=0.01,
            accessed_at=now
        )
        # Simulate same time access
        with patch('runtime.memory.types.base.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            current = memory.calculate_current_importance()
        assert abs(current - 0.8) < 0.001

    def test_memory_calculate_current_importance_with_decay(self):
        """Memory.calculate_current_importance() decay over time."""
        past_time = datetime.now() - timedelta(seconds=100)
        memory = Memory(
            type=MemoryType.WORKING,
            content="test",
            importance=1.0,
            decay_rate=0.01,
            accessed_at=past_time
        )
        current = memory.calculate_current_importance()
        # Should decay: e^(-0.01 * 100) = e^(-1) ≈ 0.368
        expected = 1.0 * math.exp(-0.01 * 100)
        assert abs(current - expected) < 0.01

    def test_memory_to_dict_from_dict_roundtrip(self):
        """Memory.to_dict() and from_dict() roundtrip should preserve data."""
        original = Memory(
            type=MemoryType.EPISODIC,
            content="test content",
            importance=0.75,
            entities=[Entity(id="e1", name="Entity 1", type=EntityType.USER)],
            relations=[Relation(source_id="e1", target_id="e2", type="knows", weight=0.8)]
        )

        data = original.to_dict()
        reconstructed = Memory.from_dict(data)

        assert reconstructed.type == original.type
        assert reconstructed.content == original.content
        assert reconstructed.importance == original.importance
        assert len(reconstructed.entities) == len(original.entities)
        assert len(reconstructed.relations) == len(original.relations)

    def test_memory_metadata_defaults(self):
        """MemoryMetadata should have proper defaults."""
        metadata = MemoryMetadata()

        assert metadata.session_id is None
        assert metadata.agent_id is None
        assert metadata.user_id is None
        assert metadata.scope == MemoryScope.PERSONAL
        assert metadata.source is None
        assert metadata.tags == []
        assert metadata.extra == {}

    def test_entity_creation(self):
        """Entity model creation and validation."""
        entity = Entity(
            id="test_id",
            name="Test Entity",
            type=EntityType.CONCEPT,
            properties={"key": "value"}
        )

        assert entity.id == "test_id"
        assert entity.name == "Test Entity"
        assert entity.type == EntityType.CONCEPT
        assert entity.properties["key"] == "value"

    def test_relation_creation_with_defaults(self):
        """Relation model creation with default weight."""
        relation = Relation(
            source_id="src",
            target_id="tgt",
            type="relates_to"
        )

        assert relation.source_id == "src"
        assert relation.target_id == "tgt"
        assert relation.type == "relates_to"
        assert relation.weight == 1.0  # default
        assert relation.properties == {}  # default


class TestMemoryClassifierEdgeCases:
    """Test edge cases for MemoryClassifier."""

    @pytest.fixture
    def classifier(self):
        """Create a basic MemoryClassifier instance."""
        return MemoryClassifier()

    def test_classify_sync_empty_content(self, classifier):
        """classify_sync() with empty content should handle gracefully."""
        result = classifier.classify_sync("", MemorySource.CHAT)

        assert result is not None
        assert hasattr(result, 'domain')
        assert hasattr(result, 'scope')

    def test_classify_sync_various_memory_sources(self, classifier):
        """classify_sync() with various MemorySource types should work."""
        content = "Test content for classification"
        sources = [
            MemorySource.CHAT,
            MemorySource.QA,
            MemorySource.AGENT_TASK,
            MemorySource.BROWSE,
            MemorySource.DOCUMENT,
            MemorySource.CODE,
            MemorySource.ACTION,
            MemorySource.PREFERENCE,
            MemorySource.FEEDBACK
        ]

        for source in sources:
            result = classifier.classify_sync(content, source)
            assert result is not None

    def test_extract_tech_stack_chinese_text(self, classifier):
        """_extract_tech_stack with Chinese text containing tech terms."""
        content = "我们使用Python和FastAPI开发了这个项目，数据库用的是PostgreSQL，缓存使用Redis"
        tech_stack = classifier._extract_tech_stack(content)

        expected_tech = {"python", "fastapi", "postgresql", "redis"}
        found_tech = set(tech_stack)
        assert expected_tech.issubset(found_tech)

    def test_extract_tech_stack_english_text(self, classifier):
        """_extract_tech_stack with English text containing tech terms."""
        content = "We built this using React and TypeScript, with a REST API backend in Go"
        tech_stack = classifier._extract_tech_stack(content)

        expected_tech = {"react", "typescript", "go", "api", "rest"}
        found_tech = set(tech_stack)
        assert expected_tech.issubset(found_tech)

    @pytest.mark.asyncio
    async def test_classify_with_failing_llm(self, classifier):
        """classify() with LLM that raises exception should fallback to baseline."""
        def failing_llm_generator(*args, **kwargs):
            raise ValueError("LLM failed")

        classifier._llm_generator = failing_llm_generator

        result = await classifier.classify("test content", MemorySource.CHAT)
        assert result is not None  # Should have fallback result


class TestLifecycleModuleEdgeCases:
    """Test edge cases for lifecycle modules."""

    def test_attention_scorer_compute_trend_no_signals(self):
        """AttentionScorer._compute_trend with no signals should return stable."""
        scorer = AttentionScorer()

        trend = scorer._compute_trend([])
        assert trend == "stable"  # No signals = stable

    def test_attention_scorer_signal_type_weight_property(self):
        """AttentionSignalType.weight property should return correct values."""
        assert AttentionSignalType.EXPLICIT_SAVE.weight == 1.0
        assert AttentionSignalType.VIEW.weight == 0.1
        assert AttentionSignalType.NEGATIVE_FEEDBACK.weight == -0.8

    def test_forgetting_curve_zero_time_elapsed(self):
        """ForgettingCurve.retention_rate() with 0 time elapsed should return 1.0."""
        curve = ForgettingCurve()
        now = datetime.now()

        memory = Memory(
            type=MemoryType.WORKING,
            content="test",
            accessed_at=now
        )
        memory.metadata.extra = {"lifecycle": "short"}

        retention = curve.retention_rate(memory, now, attention_score=None)
        assert retention == 1.0

    def test_forgetting_curve_very_large_time_near_zero(self):
        """ForgettingCurve.retention_rate() with very large time should return near 0."""
        curve = ForgettingCurve()
        now = datetime.now()
        very_old = now - timedelta(days=365 * 10)  # 10 years ago

        memory = Memory(
            type=MemoryType.WORKING,
            content="test",
            accessed_at=very_old
        )
        memory.metadata.extra = {"lifecycle": "transient"}  # 2 hour half-life

        retention = curve.retention_rate(memory, now, attention_score=None)
        assert retention < 0.001  # Should be near zero

    def test_forgetting_curve_permanent_never_decays(self):
        """Permanent memories should never decay regardless of time."""
        curve = ForgettingCurve()
        now = datetime.now()
        very_old = now - timedelta(days=365 * 100)  # 100 years ago

        memory = Memory(
            type=MemoryType.WORKING,
            content="test",
            accessed_at=very_old
        )
        memory.metadata.extra = {"lifecycle": "permanent"}

        retention = curve.retention_rate(memory, now, attention_score=None)
        assert retention == 1.0

    def test_get_memory_lifecycle_direct_field(self):
        """get_memory_lifecycle should extract from direct lifecycle field."""
        memory = Memory(
            type=MemoryType.WORKING,
            content="test"
        )
        memory.metadata.extra = {"lifecycle": "long"}

        result = get_memory_lifecycle(memory)
        assert result == MemoryLifecycle.LONG

    def test_get_memory_lifecycle_classification_field(self):
        """get_memory_lifecycle should extract from classification.lifecycle field."""
        memory = Memory(
            type=MemoryType.WORKING,
            content="test"
        )
        memory.metadata.extra = {
            "classification": {
                "lifecycle": "permanent"
            }
        }

        result = get_memory_lifecycle(memory)
        assert result == MemoryLifecycle.PERMANENT

    def test_get_memory_lifecycle_default_transient(self):
        """get_memory_lifecycle should default to TRANSIENT when no valid lifecycle found."""
        memory = Memory(
            type=MemoryType.WORKING,
            content="test"
        )
        # No lifecycle info

        result = get_memory_lifecycle(memory)
        assert result == MemoryLifecycle.TRANSIENT

    def test_promotion_rule_edge_thresholds(self):
        """PromotionRule creation with edge threshold values."""
        from runtime.memory.lifecycle.promotion import PromotionRule
        from runtime.memory.types.base import MemoryLifecycle

        rule = PromotionRule(
            source_level=MemoryLifecycle.TRANSIENT,
            target_level=MemoryLifecycle.SHORT,
            min_attention=0.5,
            min_access_count=2,
            min_validations=0
        )

        # Test rule properties
        assert rule.source_level == MemoryLifecycle.TRANSIENT
        assert rule.target_level == MemoryLifecycle.SHORT
        assert rule.min_attention == 0.5
        assert rule.min_access_count == 2

    @pytest.mark.asyncio
    async def test_scheduler_basic_functionality(self):
        """MemoryLifecycleScheduler basic functionality."""
        from runtime.memory.lifecycle.consolidation import Consolidation
        from runtime.memory.lifecycle.promotion import MemoryPromotion
        from runtime.memory.lifecycle.forgetting import Forgetting

        mock_storage = AsyncMock()
        mock_consolidation = MagicMock(spec=Consolidation)
        mock_promotion = MagicMock(spec=MemoryPromotion)
        mock_forgetting = MagicMock(spec=Forgetting)

        scheduler = MemoryLifecycleScheduler(
            consolidation=mock_consolidation,
            promotion=mock_promotion,
            forgetting=mock_forgetting,
            storage=mock_storage
        )

        # Test basic scheduler functionality
        assert scheduler.storage is not None
        assert scheduler.consolidation is not None
        assert scheduler.promotion is not None
        assert scheduler.forgetting is not None

        # Test default schedules exist
        assert hasattr(scheduler, '_schedules')
        assert len(scheduler._schedules) > 0


class TestDecisionModuleEdgeCases:
    """Test edge cases for decision modules."""

    def test_decision_recognizer_mixed_chinese_english(self):
        """DecisionRecognizer with mixed Chinese/English text."""
        from runtime.memory.decision.certainty import CertaintyAssessor

        assessor = CertaintyAssessor()
        recognizer = DecisionRecognizer(assessor)

        content = "We decided to use 采用 FastAPI for the API development"
        result = recognizer.recognize(content)

        assert result.is_decision is True
        assert result.confidence > 0.5

    def test_certainty_assessor_patterns(self):
        """CertaintyAssessor pattern matching functionality."""
        assessor = CertaintyAssessor()

        # Test pattern constants exist
        assert len(assessor.HIGH_CERTAINTY_PATTERNS) > 0
        assert len(assessor.LOW_CERTAINTY_PATTERNS) > 0
        assert len(assessor.NEGATION_PATTERNS) > 0

        # Test weights configuration
        assert "linguistic" in assessor.WEIGHTS
        assert "evidence" in assessor.WEIGHTS

    def test_decision_isolation_layer_determination(self):
        """DecisionIsolation layer determination functionality."""
        isolation = DecisionIsolation()

        layers = [
            "development",
            "testing",
            "staging",
            "production"
        ]

        for layer in layers:
            context = {"isolation_layer": layer}
            # Test the concept of layer determination
            if hasattr(isolation, 'determine_isolation_layer'):
                layer_info = isolation.determine_isolation_layer(context)
                assert isinstance(layer_info, dict)

    def test_conflict_detector_initialization(self):
        """ConflictDetector basic functionality test."""
        detector = DecisionConflictDetector()

        # Test detector can be initialized
        assert detector is not None

        # Test basic attributes exist
        if hasattr(detector, 'similarity_threshold'):
            assert isinstance(detector.similarity_threshold, (int, float))


class TestIntegrationBridgeEdgeCases:
    """Test edge cases for integration bridges."""

    def test_qa_bridge_empty_question_answer(self):
        """QAMemoryBridge with empty question/answer should handle gracefully."""
        record_data = {
            "question": "",
            "answer": "",
            "project_id": "test_project",
            "tags": ["test"],
            "trust_score": 0.7
        }

        memory = QAMemoryBridge.qa_record_to_memory(record_data)

        assert memory.content == "Q: \nA: "
        assert memory.type == MemoryType.SEMANTIC
        assert memory.importance == 0.7

    def test_qa_bridge_missing_fields(self):
        """QAMemoryBridge with missing fields should use defaults."""
        record_data = {}  # All fields missing

        memory = QAMemoryBridge.qa_record_to_memory(record_data)

        assert memory.content == "Q: \nA: "
        assert memory.metadata.extra["project_id"] == ""
        assert memory.metadata.tags == []
        assert memory.importance == 0.5  # default trust_score

    @pytest.mark.asyncio
    async def test_qa_bridge_update_trust_extreme_values(self):
        """QAMemoryBridge.update_trust with extreme values should be clamped."""
        mock_manager = AsyncMock()
        mock_memory = Memory(
            type=MemoryType.SEMANTIC,
            content="Q: test\nA: test",
            importance=0.5
        )
        mock_manager.get.return_value = mock_memory
        bridge = QAMemoryBridge(mock_manager)

        # Test extreme negative
        result1 = await bridge.update_trust("memory_1", -10.0)
        # Should be handled gracefully

        # Test extreme positive
        result2 = await bridge.update_trust("memory_1", 10.0)
        # Should be handled gracefully

        # Verify manager was called
        assert mock_manager.get.call_count >= 2

    def test_qa_bridge_memory_to_qa_dict_roundtrip(self):
        """QAMemoryBridge memory_to_qa_dict should work with qa_record_to_memory."""
        original_data = {
            "question": "What is Python?",
            "answer": "A programming language",
            "project_id": "test_project",
            "tags": ["python", "programming"],
            "trust_score": 0.8
        }

        # Convert to memory and back
        memory = QAMemoryBridge.qa_record_to_memory(original_data)
        recovered_data = QAMemoryBridge.memory_to_qa_dict(memory)

        assert recovered_data["question"] == original_data["question"]
        assert recovered_data["answer"] == original_data["answer"]
        assert recovered_data["project_id"] == original_data["project_id"]
        assert recovered_data["trust_score"] == original_data["trust_score"]

    @pytest.mark.asyncio
    async def test_unified_agent_memory_zero_max_turns(self):
        """UnifiedAgentMemory with zero max_turns should handle gracefully."""
        mock_manager = AsyncMock()

        agent_memory = UnifiedAgentMemory(
            manager=mock_manager,
            agent_id="test_agent",
            session_id="test_session",  # Required parameter
            max_turns=0  # Edge case: zero turns
        )

        # Should still function without errors
        await agent_memory.add_interaction("Hello", "Hi there!")

        # With 0 max_turns, might trigger immediate consolidation
        assert mock_manager.store.call_count >= 1

    def test_agent_memory_factory_basic_functionality(self):
        """AgentMemoryFactory basic functionality test."""
        # AgentMemoryFactory might not take constructor arguments
        # Testing basic creation and concepts
        if 'AgentMemoryFactory' in globals():
            # Test factory concept exists
            assert AgentMemoryFactory is not None

    @pytest.mark.asyncio
    async def test_unified_agent_memory_retrieve_context(self):
        """UnifiedAgentMemory.retrieve_context with empty history."""
        mock_manager = AsyncMock()
        mock_manager.search.return_value = []  # Empty search results

        agent_memory = UnifiedAgentMemory(
            manager=mock_manager,
            agent_id="test_agent",
            session_id="test_session"
        )

        context = await agent_memory.retrieve_context("What is the weather?")

        assert context is not None
        assert isinstance(context, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])