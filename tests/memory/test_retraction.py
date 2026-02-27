"""Tests for decision retraction mechanism."""

from __future__ import annotations

from datetime import datetime

from runtime.memory.decision.models import Decision, DecisionCategory, DecisionCertainty, DecisionStatus
from runtime.memory.decision.retraction import (
    DecisionRetraction,
    RetractionReason,
    RetractionResult,
)


class TestRetractionReason:
    """Test RetractionReason enum values."""

    def test_retraction_reason_values(self):
        """Test that all required reason values are available."""
        assert RetractionReason.USER_REJECTED == "user_rejected"
        assert RetractionReason.CONFLICT_RESOLVED == "conflict_resolved"
        assert RetractionReason.EVIDENCE_INVALIDATED == "evidence_invalidated"
        assert RetractionReason.STALE_UNCONFIRMED == "stale_unconfirmed"
        assert RetractionReason.SUPERSEDED == "superseded"
        assert RetractionReason.ERROR == "error"


class TestRetractionResult:
    """Test RetractionResult model creation and defaults."""

    def test_retraction_result_creation(self):
        """Test basic RetractionResult creation."""
        result = RetractionResult(
            success=True,
            decision_id="test-123",
            reason=RetractionReason.USER_REJECTED
        )

        assert result.success is True
        assert result.decision_id == "test-123"
        assert result.reason == RetractionReason.USER_REJECTED
        assert result.affected_memories == []
        assert isinstance(result.retracted_at, datetime)
        assert result.retracted_by is None
        assert result.notes == ""

    def test_retraction_result_with_all_fields(self):
        """Test RetractionResult with all fields set."""
        now = datetime.now()
        result = RetractionResult(
            success=True,
            decision_id="test-456",
            reason=RetractionReason.CONFLICT_RESOLVED,
            affected_memories=["mem1", "mem2"],
            retracted_at=now,
            retracted_by="user123",
            notes="Test retraction"
        )

        assert result.success is True
        assert result.decision_id == "test-456"
        assert result.reason == RetractionReason.CONFLICT_RESOLVED
        assert result.affected_memories == ["mem1", "mem2"]
        assert result.retracted_at == now
        assert result.retracted_by == "user123"
        assert result.notes == "Test retraction"


class TestDecisionRetraction:
    """Test DecisionRetraction class methods."""

    def create_test_decision(self, certainty=DecisionCertainty.CONFIRMED,
                           status=DecisionStatus.DECIDED, quarantined=False):
        """Helper to create test decision."""
        return Decision(
            title="Test Decision",
            summary="Test summary",
            context="Test context",
            decision="Test decision content",
            rationale="Test rationale",
            category=DecisionCategory.TECHNOLOGY,
            certainty=certainty,
            status=status,
            quarantined=quarantined,
            source_memories=["mem1", "mem2"]
        )

    def test_retract_normal_case(self):
        """Test normal retraction case."""
        decision = self.create_test_decision()
        original_updated_at = decision.updated_at

        updated_decision, result = DecisionRetraction.retract(
            decision, RetractionReason.USER_REJECTED
        )

        # Check decision updates
        assert updated_decision.certainty == DecisionCertainty.RETRACTED
        assert updated_decision.quarantined is True
        assert updated_decision.status == DecisionStatus.REVERTED
        assert updated_decision.updated_at >= original_updated_at

        # Check result
        assert result.success is True
        assert result.decision_id == decision.id
        assert result.reason == RetractionReason.USER_REJECTED
        assert result.retracted_by is None
        assert result.notes == ""

    def test_retract_with_retracted_by_and_notes(self):
        """Test retraction with retracted_by and notes."""
        decision = self.create_test_decision()

        updated_decision, result = DecisionRetraction.retract(
            decision,
            RetractionReason.EVIDENCE_INVALIDATED,
            retracted_by="admin",
            notes="Evidence was found to be outdated"
        )

        # Check decision updates
        assert updated_decision.certainty == DecisionCertainty.RETRACTED
        assert updated_decision.quarantined is True
        assert updated_decision.status == DecisionStatus.REVERTED

        # Check result
        assert result.success is True
        assert result.decision_id == decision.id
        assert result.reason == RetractionReason.EVIDENCE_INVALIDATED
        assert result.retracted_by == "admin"
        assert result.notes == "Evidence was found to be outdated"

    def test_can_retract_normal_decision(self):
        """Test can_retract returns True for normal decision."""
        decision = self.create_test_decision()
        assert DecisionRetraction.can_retract(decision) is True

    def test_can_retract_already_retracted(self):
        """Test can_retract returns False for already retracted decision."""
        decision = self.create_test_decision(certainty=DecisionCertainty.RETRACTED)
        assert DecisionRetraction.can_retract(decision) is False

    def test_bulk_retract_multiple_decisions(self):
        """Test bulk retraction of multiple decisions."""
        decisions = [
            self.create_test_decision(),
            self.create_test_decision(),
            self.create_test_decision()
        ]

        results = DecisionRetraction.bulk_retract(
            decisions,
            RetractionReason.STALE_UNCONFIRMED,
            retracted_by="system"
        )

        assert len(results) == 3

        for i, result in enumerate(results):
            assert result.success is True
            assert result.decision_id == decisions[i].id
            assert result.reason == RetractionReason.STALE_UNCONFIRMED
            assert result.retracted_by == "system"

            # Check decision was updated
            assert decisions[i].certainty == DecisionCertainty.RETRACTED
            assert decisions[i].quarantined is True
            assert decisions[i].status == DecisionStatus.REVERTED

    def test_bulk_retract_skips_already_retracted(self):
        """Test bulk retraction skips already retracted decisions."""
        decisions = [
            self.create_test_decision(),  # Normal decision
            self.create_test_decision(certainty=DecisionCertainty.RETRACTED),  # Already retracted
            self.create_test_decision()   # Normal decision
        ]

        results = DecisionRetraction.bulk_retract(
            decisions,
            RetractionReason.SUPERSEDED
        )

        # Should only get results for non-retracted decisions
        assert len(results) == 2
        assert results[0].decision_id == decisions[0].id
        assert results[1].decision_id == decisions[2].id

        # Check only non-retracted decisions were modified
        assert decisions[0].certainty == DecisionCertainty.RETRACTED
        assert decisions[1].certainty == DecisionCertainty.RETRACTED  # Already was
        assert decisions[2].certainty == DecisionCertainty.RETRACTED

    def test_retracted_decision_has_correct_fields(self):
        """Test that retracted decision has all correct field values."""
        decision = self.create_test_decision()

        updated_decision, _ = DecisionRetraction.retract(
            decision, RetractionReason.ERROR
        )

        assert updated_decision.certainty == DecisionCertainty.RETRACTED
        assert updated_decision.quarantined is True
        assert updated_decision.status == DecisionStatus.REVERTED
        assert isinstance(updated_decision.updated_at, datetime)