"""Tests for safety filtering in memory retrieval."""

from __future__ import annotations

import pytest

from runtime.memory.retrieval.reranker import RankedMemory
from runtime.memory.retrieval.safety import SafeRetrievalResult, SafetyAnnotation, SafetyFilter, SafetyLevel
from runtime.memory.types.base import Memory, MemoryMetadata, MemoryScope, MemoryType


class TestSafetyLevel:
    """Test SafetyLevel enum."""

    def test_safety_levels(self):
        """Test all safety levels are defined."""
        assert SafetyLevel.STRICT == "strict"
        assert SafetyLevel.STANDARD == "standard"
        assert SafetyLevel.LOOSE == "loose"


class TestSafetyAnnotation:
    """Test SafetyAnnotation dataclass."""

    def test_safety_annotation_creation(self):
        """Test creating safety annotation."""
        annotation = SafetyAnnotation(
            can_cite=True,
            needs_verification=False,
            warning=None
        )
        assert annotation.can_cite is True
        assert annotation.needs_verification is False
        assert annotation.warning is None


class TestSafeRetrievalResult:
    """Test SafeRetrievalResult dataclass."""

    def test_safe_retrieval_result_creation(self):
        """Test creating safe retrieval result."""
        memory = Memory(
            type=MemoryType.SEMANTIC,
            content="Test memory",
            metadata=MemoryMetadata()
        )

        annotation = SafetyAnnotation(
            can_cite=True,
            needs_verification=False,
            warning=None
        )

        result = SafeRetrievalResult(
            memory=memory,
            score=0.95,
            sources=["vector", "keyword"],
            safety=annotation
        )

        assert result.memory == memory
        assert result.score == 0.95
        assert result.sources == ["vector", "keyword"]
        assert result.safety == annotation


class TestSafetyFilter:
    """Test SafetyFilter class."""

    @pytest.fixture
    def sample_memories(self) -> list[RankedMemory]:
        """Create sample ranked memories for testing."""
        # Decision memory - confirmed
        decision_confirmed = Memory(
            id="decision-1",
            type=MemoryType.SEMANTIC,
            content="We decided to use React for the frontend",
            metadata=MemoryMetadata(
                user_id="user1",
                scope=MemoryScope.WORK,
                extra={
                    "is_decision": True,
                    "certainty": "confirmed",
                    "status": "implemented"
                }
            )
        )

        # Decision memory - evidenced
        decision_evidenced = Memory(
            id="decision-2",
            type=MemoryType.SEMANTIC,
            content="Database migration is approved",
            metadata=MemoryMetadata(
                user_id="user1",
                scope=MemoryScope.PROJECT,
                extra={
                    "is_decision": True,
                    "certainty": "evidenced"
                }
            )
        )

        # Decision memory - inferred (low certainty)
        decision_inferred = Memory(
            id="decision-3",
            type=MemoryType.SEMANTIC,
            content="Might switch to TypeScript",
            metadata=MemoryMetadata(
                user_id="user1",
                scope=MemoryScope.WORK,
                extra={
                    "is_decision": True,
                    "certainty": "inferred"
                }
            )
        )

        # Decision memory - quarantined
        decision_quarantined = Memory(
            id="decision-4",
            type=MemoryType.SEMANTIC,
            content="Old deprecated decision",
            metadata=MemoryMetadata(
                user_id="user1",
                scope=MemoryScope.WORK,
                extra={
                    "is_decision": True,
                    "certainty": "confirmed",
                    "quarantined": True
                }
            )
        )

        # Non-decision memory
        regular_memory = Memory(
            id="regular-1",
            type=MemoryType.EPISODIC,
            content="Had a meeting with the team",
            metadata=MemoryMetadata(
                user_id="user1",
                scope=MemoryScope.WORK
            )
        )

        # Memory from different user
        other_user_memory = Memory(
            id="other-1",
            type=MemoryType.SEMANTIC,
            content="Personal note from another user",
            metadata=MemoryMetadata(
                user_id="user2",
                scope=MemoryScope.PERSONAL
            )
        )

        return [
            RankedMemory(memory=decision_confirmed, final_score=0.95, sources=["vector"]),
            RankedMemory(memory=decision_evidenced, final_score=0.90, sources=["keyword"]),
            RankedMemory(memory=decision_inferred, final_score=0.85, sources=["vector"]),
            RankedMemory(memory=decision_quarantined, final_score=0.80, sources=["vector"]),
            RankedMemory(memory=regular_memory, final_score=0.75, sources=["vector", "keyword"]),
            RankedMemory(memory=other_user_memory, final_score=0.70, sources=["vector"]),
        ]

    def test_strict_safety_level(self, sample_memories):
        """Test STRICT safety level filters out non-confirmed decisions."""
        filter = SafetyFilter(safety_level=SafetyLevel.STRICT)
        results = filter.apply(sample_memories, user_id="user1")

        # Only decision-1 (confirmed+implemented) and regular memory should pass
        assert len(results) == 2
        memory_ids = [r.memory.id for r in results]
        assert "decision-1" in memory_ids
        assert "regular-1" in memory_ids
        assert "decision-2" not in memory_ids  # evidenced but not implemented
        assert "decision-3" not in memory_ids  # inferred
        assert "decision-4" not in memory_ids  # quarantined

    def test_standard_safety_level(self, sample_memories):
        """Test STANDARD safety level allows high-certainty decisions."""
        filter = SafetyFilter(safety_level=SafetyLevel.STANDARD)
        results = filter.apply(sample_memories, user_id="user1")

        # confirmed, evidenced decisions + regular memory should pass
        assert len(results) == 3
        memory_ids = [r.memory.id for r in results]
        assert "decision-1" in memory_ids
        assert "decision-2" in memory_ids
        assert "regular-1" in memory_ids
        assert "decision-3" not in memory_ids  # inferred
        assert "decision-4" not in memory_ids  # quarantined

    def test_loose_safety_level(self, sample_memories):
        """Test LOOSE safety level includes inferred decisions with warning."""
        filter = SafetyFilter(safety_level=SafetyLevel.LOOSE)
        results = filter.apply(sample_memories, user_id="user1")

        # All except quarantined should pass
        assert len(results) == 4
        memory_ids = [r.memory.id for r in results]
        assert "decision-1" in memory_ids
        assert "decision-2" in memory_ids
        assert "decision-3" in memory_ids  # inferred with warning
        assert "regular-1" in memory_ids
        assert "decision-4" not in memory_ids  # quarantined

        # Check that inferred decision has warning
        inferred_result = next(r for r in results if r.memory.id == "decision-3")
        assert inferred_result.safety.needs_verification is True
        assert inferred_result.safety.warning is not None
        assert "low certainty" in inferred_result.safety.warning.lower()

    def test_quarantined_always_filtered(self, sample_memories):
        """Test quarantined memories are always filtered regardless of safety level."""
        for safety_level in [SafetyLevel.STRICT, SafetyLevel.STANDARD, SafetyLevel.LOOSE]:
            filter = SafetyFilter(safety_level=safety_level)
            results = filter.apply(sample_memories, user_id="user1")

            memory_ids = [r.memory.id for r in results]
            assert "decision-4" not in memory_ids

    def test_scope_filtering(self, sample_memories):
        """Test scope permission filtering."""
        filter = SafetyFilter()

        # Only allow WORK scope
        results = filter.apply(sample_memories, user_id="user1", allowed_scopes=[MemoryScope.WORK])

        # Only memories with WORK scope should pass
        for result in results:
            assert result.memory.metadata.scope == MemoryScope.WORK

    def test_user_id_filtering(self, sample_memories):
        """Test user ID filtering."""
        filter = SafetyFilter()

        # Filter for user1
        results = filter.apply(sample_memories, user_id="user1")

        # Only user1 memories should pass
        for result in results:
            assert result.memory.metadata.user_id == "user1"

    def test_non_decision_memories_always_pass(self, sample_memories):
        """Test non-decision memories pass through regardless of safety level."""
        regular_memories = [m for m in sample_memories if not m.memory.metadata.extra.get("is_decision")]

        for safety_level in [SafetyLevel.STRICT, SafetyLevel.STANDARD, SafetyLevel.LOOSE]:
            filter = SafetyFilter(safety_level=safety_level)
            results = filter.apply(regular_memories, user_id="user1")

            # All non-decision memories from user1 should pass
            user1_regular = [m for m in regular_memories if m.memory.metadata.user_id == "user1"]
            assert len(results) == len(user1_regular)

    def test_empty_results(self):
        """Test handling of empty input."""
        filter = SafetyFilter()
        results = filter.apply([])
        assert results == []

    def test_safety_annotation_details(self, sample_memories):
        """Test safety annotation details are correct."""
        filter = SafetyFilter(safety_level=SafetyLevel.LOOSE)
        results = filter.apply(sample_memories, user_id="user1")

        # Find different types of results
        confirmed_result = next(r for r in results if r.memory.id == "decision-1")
        inferred_result = next(r for r in results if r.memory.id == "decision-3")
        regular_result = next(r for r in results if r.memory.id == "regular-1")

        # Confirmed decision should be safe to cite
        assert confirmed_result.safety.can_cite is True
        assert confirmed_result.safety.needs_verification is False
        assert confirmed_result.safety.warning is None

        # Inferred decision needs verification
        assert inferred_result.safety.can_cite is False
        assert inferred_result.safety.needs_verification is True
        assert inferred_result.safety.warning is not None

        # Regular memory should be safe
        assert regular_result.safety.can_cite is True
        assert regular_result.safety.needs_verification is False
        assert regular_result.safety.warning is None