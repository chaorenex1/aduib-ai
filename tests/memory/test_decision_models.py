"""Tests for decision memory data models."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from uuid import UUID

from runtime.memory.decision.models import (
    Decision,
    DecisionStatus,
    DecisionCategory,
    DecisionScope,
    DecisionCertainty,
    DecisionPriority,
    Alternative,
    Evidence,
    EvidenceType,
    TimelineEvent,
    TimelineEventType,
    DecisionTimeline,
    ConflictType,
)


class TestEnums:
    """Test all enum values exist and are correct."""

    def test_decision_status_enum(self):
        """Test DecisionStatus enum has all expected values."""
        expected_values = {
            "PROPOSED", "UNDER_REVIEW", "DECIDED", "APPROVED", "IMPLEMENTING",
            "IMPLEMENTED", "SUPERSEDED", "DEPRECATED", "REVERTED"
        }
        actual_values = {status.value.upper() for status in DecisionStatus}
        assert actual_values == expected_values

    def test_decision_category_enum(self):
        """Test DecisionCategory enum has all expected values."""
        expected_values = {
            "ARCHITECTURE", "TECHNOLOGY", "DESIGN", "PROCESS", "REQUIREMENT",
            "SECURITY", "PERFORMANCE", "COST"
        }
        actual_values = {category.value.upper() for category in DecisionCategory}
        assert actual_values == expected_values

    def test_decision_scope_enum(self):
        """Test DecisionScope enum has all expected values."""
        expected_values = {"GLOBAL", "PROJECT", "MODULE", "COMPONENT"}
        actual_values = {scope.value.upper() for scope in DecisionScope}
        assert actual_values == expected_values

    def test_decision_certainty_enum(self):
        """Test DecisionCertainty enum has all expected values."""
        expected_values = {
            "CONFIRMED", "EVIDENCED", "EXPLICIT", "INFERRED", "IMPLICIT",
            "TENTATIVE", "DISCUSSING", "UNCERTAIN", "DISPUTED", "RETRACTED"
        }
        actual_values = {certainty.value.upper() for certainty in DecisionCertainty}
        assert actual_values == expected_values

    def test_decision_priority_enum(self):
        """Test DecisionPriority enum has all expected values."""
        expected_values = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        actual_values = {priority.value.upper() for priority in DecisionPriority}
        assert actual_values == expected_values

    def test_evidence_type_enum(self):
        """Test EvidenceType enum has all expected values."""
        expected_values = {
            "CODE_COMMIT", "PULL_REQUEST", "CONFIG_CHANGE", "DOCUMENT",
            "TEST_RESULT", "DEPLOYMENT", "MANUAL_CONFIRM"
        }
        actual_values = {etype.value.upper() for etype in EvidenceType}
        assert actual_values == expected_values

    def test_timeline_event_type_enum(self):
        """Test TimelineEventType enum has all expected values."""
        expected_values = {
            "PROPOSED", "DISCUSSED", "DECIDED", "APPROVED", "STARTED",
            "PROGRESS", "COMPLETED", "VERIFIED", "CHANGED", "SUPERSEDED", "REVERTED"
        }
        actual_values = {etype.value.upper() for etype in TimelineEventType}
        assert actual_values == expected_values

    def test_conflict_type_enum(self):
        """Test ConflictType enum has all expected values."""
        expected_values = {
            "DIRECT_CONTRADICTION", "PARTIAL_OVERLAP", "SUPERSEDES", "UNRELATED"
        }
        actual_values = {ctype.value.upper() for ctype in ConflictType}
        assert actual_values == expected_values


class TestAlternative:
    """Test Alternative model."""

    def test_alternative_creation_minimal(self):
        """Test Alternative creation with minimal fields."""
        alt = Alternative(
            name="Option A",
            description="First option"
        )
        assert alt.name == "Option A"
        assert alt.description == "First option"
        assert alt.pros == []
        assert alt.cons == []
        assert alt.rejected_reason == ""

    def test_alternative_creation_full(self):
        """Test Alternative creation with all fields."""
        alt = Alternative(
            name="Option B",
            description="Second option",
            pros=["Fast", "Simple"],
            cons=["Limited", "Expensive"],
            rejected_reason="Too costly"
        )
        assert alt.name == "Option B"
        assert alt.pros == ["Fast", "Simple"]
        assert alt.cons == ["Limited", "Expensive"]
        assert alt.rejected_reason == "Too costly"


class TestEvidence:
    """Test Evidence model."""

    def test_evidence_creation_minimal(self):
        """Test Evidence creation with minimal fields."""
        evidence = Evidence(
            type=EvidenceType.CODE_COMMIT,
            description="Added new feature",
            reference="abc123"
        )
        # Auto-generated UUID
        assert evidence.id is not None
        assert UUID(evidence.id, version=4)
        assert evidence.type == EvidenceType.CODE_COMMIT
        assert evidence.description == "Added new feature"
        assert evidence.reference == "abc123"
        assert evidence.verified is False
        assert evidence.verified_at is None
        assert evidence.verified_by is None

    def test_evidence_creation_full(self):
        """Test Evidence creation with all fields."""
        now = datetime.now(timezone.utc)
        evidence = Evidence(
            id="custom-id",
            type=EvidenceType.PULL_REQUEST,
            description="PR merged",
            reference="https://github.com/repo/pull/123",
            verified=True,
            verified_at=now,
            verified_by="alice"
        )
        assert evidence.id == "custom-id"
        assert evidence.verified is True
        assert evidence.verified_at == now
        assert evidence.verified_by == "alice"


class TestTimelineEvent:
    """Test TimelineEvent creation."""

    def test_timeline_event_creation_minimal(self):
        """Test TimelineEvent creation with minimal fields."""
        now = datetime.now(timezone.utc)
        event = TimelineEvent(
            timestamp=now,
            type=TimelineEventType.PROPOSED,
            description="Initial proposal"
        )
        assert event.timestamp == now
        assert event.type == TimelineEventType.PROPOSED
        assert event.description == "Initial proposal"
        assert event.actor is None
        assert event.evidence_id is None
        assert event.metadata == {}

    def test_timeline_event_creation_full(self):
        """Test TimelineEvent creation with all fields."""
        now = datetime.now(timezone.utc)
        event = TimelineEvent(
            timestamp=now,
            type=TimelineEventType.DECIDED,
            description="Decision made",
            actor="bob",
            evidence_id="evidence-123",
            metadata={"review_id": "review-456"}
        )
        assert event.actor == "bob"
        assert event.evidence_id == "evidence-123"
        assert event.metadata == {"review_id": "review-456"}


class TestDecisionTimeline:
    """Test DecisionTimeline model."""

    def test_decision_timeline_creation(self):
        """Test DecisionTimeline creation."""
        timeline = DecisionTimeline(
            decision_id="decision-123",
            title="Feature X Implementation",
            events=[]
        )
        assert timeline.decision_id == "decision-123"
        assert timeline.title == "Feature X Implementation"
        assert timeline.events == []

    def test_decision_timeline_with_events(self):
        """Test DecisionTimeline with events."""
        now = datetime.now(timezone.utc)
        event = TimelineEvent(
            timestamp=now,
            type=TimelineEventType.PROPOSED,
            description="Initial proposal"
        )
        timeline = DecisionTimeline(
            decision_id="decision-123",
            title="Feature X Implementation",
            events=[event]
        )
        assert len(timeline.events) == 1
        assert timeline.events[0].type == TimelineEventType.PROPOSED


class TestDecision:
    """Test Decision model."""

    def test_decision_creation_minimal(self):
        """Test Decision creation with minimal fields."""
        decision = Decision(
            title="Use React for frontend",
            summary="Choose React framework",
            context="Need modern frontend framework",
            decision="We will use React",
            rationale="React has good ecosystem",
            category=DecisionCategory.TECHNOLOGY
        )
        # Auto-generated UUID
        assert decision.id is not None
        assert UUID(decision.id, version=4)
        assert decision.title == "Use React for frontend"
        assert decision.category == DecisionCategory.TECHNOLOGY
        # Test default values
        assert decision.alternatives == []
        assert decision.consequences == []
        assert decision.scope == DecisionScope.PROJECT
        assert decision.priority == DecisionPriority.MEDIUM
        assert decision.project_id is None
        assert decision.module_ids == []
        assert decision.related_decisions == []
        assert decision.supersedes is None
        assert decision.status == DecisionStatus.PROPOSED
        assert decision.certainty == DecisionCertainty.UNCERTAIN
        assert decision.decided_at is None
        assert decision.decided_by is None
        assert decision.implemented_at is None
        assert decision.evidence == []
        assert decision.source_memories == []
        assert decision.confidence == 0.0
        assert decision.user_confirmed is False
        assert decision.quarantined is False
        # Auto-generated timestamps
        assert decision.created_at is not None
        assert decision.updated_at is not None

    def test_decision_creation_full(self):
        """Test Decision creation with all fields."""
        now = datetime.now(timezone.utc)
        alt = Alternative(name="Vue", description="Alternative framework")
        evidence = Evidence(
            type=EvidenceType.DOCUMENT,
            description="Tech comparison doc",
            reference="/docs/comparison.md"
        )
        decision = Decision(
            id="custom-decision-id",
            title="Use React for frontend",
            summary="Choose React framework",
            context="Need modern frontend framework",
            decision="We will use React",
            rationale="React has good ecosystem",
            alternatives=[alt],
            consequences=["Learning curve", "Migration effort"],
            category=DecisionCategory.TECHNOLOGY,
            scope=DecisionScope.GLOBAL,
            priority=DecisionPriority.HIGH,
            project_id="project-123",
            module_ids=["module-1", "module-2"],
            related_decisions=["decision-456"],
            supersedes="old-decision-789",
            status=DecisionStatus.DECIDED,
            certainty=DecisionCertainty.EXPLICIT,
            decided_at=now,
            decided_by="alice",
            implemented_at=now,
            evidence=[evidence],
            source_memories=["memory-1", "memory-2"],
            confidence=0.9,
            user_confirmed=True,
            quarantined=False,
            created_at=now,
            updated_at=now
        )
        assert decision.id == "custom-decision-id"
        assert len(decision.alternatives) == 1
        assert decision.alternatives[0].name == "Vue"
        assert decision.consequences == ["Learning curve", "Migration effort"]
        assert decision.scope == DecisionScope.GLOBAL
        assert decision.priority == DecisionPriority.HIGH
        assert decision.project_id == "project-123"
        assert decision.module_ids == ["module-1", "module-2"]
        assert decision.related_decisions == ["decision-456"]
        assert decision.supersedes == "old-decision-789"
        assert decision.status == DecisionStatus.DECIDED
        assert decision.certainty == DecisionCertainty.EXPLICIT
        assert decision.decided_at == now
        assert decision.decided_by == "alice"
        assert decision.implemented_at == now
        assert len(decision.evidence) == 1
        assert decision.evidence[0].type == EvidenceType.DOCUMENT
        assert decision.source_memories == ["memory-1", "memory-2"]
        assert decision.confidence == 0.9
        assert decision.user_confirmed is True
        assert decision.quarantined is False

    def test_decision_serialization(self):
        """Test Decision.model_dump() serialization."""
        decision = Decision(
            title="Test Decision",
            summary="Test summary",
            context="Test context",
            decision="Test decision",
            rationale="Test rationale",
            category=DecisionCategory.DESIGN
        )
        data = decision.model_dump()
        assert isinstance(data, dict)
        assert data["title"] == "Test Decision"
        assert data["category"] == "design"
        assert data["status"] == "proposed"

    def test_decision_deserialization(self):
        """Test Decision.model_validate() deserialization."""
        data = {
            "title": "Test Decision",
            "summary": "Test summary",
            "context": "Test context",
            "decision": "Test decision",
            "rationale": "Test rationale",
            "category": "design",
            "status": "decided"
        }
        decision = Decision.model_validate(data)
        assert decision.title == "Test Decision"
        assert decision.category == DecisionCategory.DESIGN
        assert decision.status == DecisionStatus.DECIDED

    def test_decision_default_values(self):
        """Test Decision default values are correct."""
        decision = Decision(
            title="Default Test",
            summary="Test summary",
            context="Test context",
            decision="Test decision",
            rationale="Test rationale",
            category=DecisionCategory.PROCESS
        )
        # Verify specific default values
        assert decision.status == DecisionStatus.PROPOSED
        assert decision.certainty == DecisionCertainty.UNCERTAIN
        assert decision.scope == DecisionScope.PROJECT
        assert decision.priority == DecisionPriority.MEDIUM
        assert decision.confidence == 0.0
        assert decision.user_confirmed is False
        assert decision.quarantined is False
        assert decision.alternatives == []
        assert decision.consequences == []
        assert decision.module_ids == []
        assert decision.related_decisions == []
        assert decision.evidence == []
        assert decision.source_memories == []