"""Test decision isolation and context injection system."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from runtime.memory.decision.isolation import (
    DecisionContextInjector,
    DecisionIsolation,
    InjectedDecision,
    InjectionRule,
    IsolationLayer,
)
from runtime.memory.decision.models import Decision, DecisionCategory, DecisionCertainty


class TestIsolationLayer:
    """Test IsolationLayer enum."""

    def test_layer_values(self):
        """Test that all expected layer values exist."""
        assert IsolationLayer.TRUSTED == "trusted"
        assert IsolationLayer.CANDIDATE == "candidate"
        assert IsolationLayer.DISCUSSION == "discussion"
        assert IsolationLayer.QUARANTINE == "quarantine"

    def test_layer_count(self):
        """Test that exactly 4 layers exist."""
        assert len(IsolationLayer) == 4


class TestInjectionRule:
    """Test InjectionRule model."""

    def test_injection_rule_defaults(self):
        """Test InjectionRule with defaults."""
        rule = InjectionRule(inject=True)
        assert rule.inject is True
        assert rule.prefix is None
        assert rule.max_age_days is None

    def test_injection_rule_with_values(self):
        """Test InjectionRule with all values."""
        rule = InjectionRule(
            inject=True,
            prefix="[待确认] ",
            max_age_days=30,
        )
        assert rule.inject is True
        assert rule.prefix == "[待确认] "
        assert rule.max_age_days == 30


class TestDecisionIsolation:
    """Test DecisionIsolation class."""

    def setup_method(self):
        """Set up test."""
        self.isolation = DecisionIsolation()

    def test_layer_mapping_trusted(self):
        """Test TRUSTED layer mapping."""
        trusted_certainties = [
            DecisionCertainty.CONFIRMED,
            DecisionCertainty.EVIDENCED,
            DecisionCertainty.EXPLICIT,
        ]
        for certainty in trusted_certainties:
            assert DecisionIsolation.LAYER_MAPPING[certainty] == IsolationLayer.TRUSTED

    def test_layer_mapping_candidate(self):
        """Test CANDIDATE layer mapping."""
        candidate_certainties = [
            DecisionCertainty.INFERRED,
            DecisionCertainty.IMPLICIT,
        ]
        for certainty in candidate_certainties:
            assert DecisionIsolation.LAYER_MAPPING[certainty] == IsolationLayer.CANDIDATE

    def test_layer_mapping_discussion(self):
        """Test DISCUSSION layer mapping."""
        discussion_certainties = [
            DecisionCertainty.TENTATIVE,
            DecisionCertainty.DISCUSSING,
            DecisionCertainty.UNCERTAIN,
        ]
        for certainty in discussion_certainties:
            assert DecisionIsolation.LAYER_MAPPING[certainty] == IsolationLayer.DISCUSSION

    def test_layer_mapping_quarantine(self):
        """Test QUARANTINE layer mapping."""
        quarantine_certainties = [
            DecisionCertainty.DISPUTED,
            DecisionCertainty.RETRACTED,
        ]
        for certainty in quarantine_certainties:
            assert DecisionIsolation.LAYER_MAPPING[certainty] == IsolationLayer.QUARANTINE

    def test_classify_layer_normal(self):
        """Test classify_layer for normal decisions."""
        decision = Decision(
            title="Test Decision",
            summary="Test summary",
            context="Test context",
            decision="Test decision",
            rationale="Test rationale",
            category=DecisionCategory.ARCHITECTURE,
            certainty=DecisionCertainty.CONFIRMED,
        )
        layer = self.isolation.classify_layer(decision)
        assert layer == IsolationLayer.TRUSTED

    def test_classify_layer_quarantined_override(self):
        """Test classify_layer when quarantined=True overrides certainty."""
        decision = Decision(
            title="Test Decision",
            summary="Test summary",
            context="Test context",
            decision="Test decision",
            rationale="Test rationale",
            category=DecisionCategory.ARCHITECTURE,
            certainty=DecisionCertainty.CONFIRMED,  # Should be TRUSTED normally
            quarantined=True,  # But this overrides to QUARANTINE
        )
        layer = self.isolation.classify_layer(decision)
        assert layer == IsolationLayer.QUARANTINE

    def test_is_retrievable_trusted(self):
        """Test is_retrievable for TRUSTED layer."""
        decision = Decision(
            title="Test Decision",
            summary="Test summary",
            context="Test context",
            decision="Test decision",
            rationale="Test rationale",
            category=DecisionCategory.ARCHITECTURE,
            certainty=DecisionCertainty.CONFIRMED,
        )
        assert self.isolation.is_retrievable(decision) is True

    def test_is_retrievable_candidate(self):
        """Test is_retrievable for CANDIDATE layer."""
        decision = Decision(
            title="Test Decision",
            summary="Test summary",
            context="Test context",
            decision="Test decision",
            rationale="Test rationale",
            category=DecisionCategory.ARCHITECTURE,
            certainty=DecisionCertainty.INFERRED,
        )
        assert self.isolation.is_retrievable(decision) is True

    def test_is_retrievable_discussion(self):
        """Test is_retrievable for DISCUSSION layer."""
        decision = Decision(
            title="Test Decision",
            summary="Test summary",
            context="Test context",
            decision="Test decision",
            rationale="Test rationale",
            category=DecisionCategory.ARCHITECTURE,
            certainty=DecisionCertainty.TENTATIVE,
        )
        assert self.isolation.is_retrievable(decision) is False

    def test_is_retrievable_quarantine(self):
        """Test is_retrievable for QUARANTINE layer."""
        decision = Decision(
            title="Test Decision",
            summary="Test summary",
            context="Test context",
            decision="Test decision",
            rationale="Test rationale",
            category=DecisionCategory.ARCHITECTURE,
            certainty=DecisionCertainty.DISPUTED,
        )
        assert self.isolation.is_retrievable(decision) is False

    def test_is_injectable_trusted(self):
        """Test is_injectable only returns True for TRUSTED layer."""
        decision = Decision(
            title="Test Decision",
            summary="Test summary",
            context="Test context",
            decision="Test decision",
            rationale="Test rationale",
            category=DecisionCategory.ARCHITECTURE,
            certainty=DecisionCertainty.CONFIRMED,
        )
        assert self.isolation.is_injectable(decision) is True

    def test_is_injectable_candidate(self):
        """Test is_injectable returns False for CANDIDATE layer."""
        decision = Decision(
            title="Test Decision",
            summary="Test summary",
            context="Test context",
            decision="Test decision",
            rationale="Test rationale",
            category=DecisionCategory.ARCHITECTURE,
            certainty=DecisionCertainty.INFERRED,
        )
        assert self.isolation.is_injectable(decision) is False

    def test_get_decisions_by_layer(self):
        """Test get_decisions_by_layer filtering."""
        decisions = [
            Decision(
                title="Trusted Decision",
                summary="Test summary",
                context="Test context",
                decision="Test decision",
                rationale="Test rationale",
                category=DecisionCategory.ARCHITECTURE,
                certainty=DecisionCertainty.CONFIRMED,
            ),
            Decision(
                title="Candidate Decision",
                summary="Test summary",
                context="Test context",
                decision="Test decision",
                rationale="Test rationale",
                category=DecisionCategory.ARCHITECTURE,
                certainty=DecisionCertainty.INFERRED,
            ),
            Decision(
                title="Discussion Decision",
                summary="Test summary",
                context="Test context",
                decision="Test decision",
                rationale="Test rationale",
                category=DecisionCategory.ARCHITECTURE,
                certainty=DecisionCertainty.TENTATIVE,
            ),
        ]

        trusted = self.isolation.get_decisions_by_layer(decisions, IsolationLayer.TRUSTED)
        assert len(trusted) == 1
        assert trusted[0].title == "Trusted Decision"

        candidate = self.isolation.get_decisions_by_layer(decisions, IsolationLayer.CANDIDATE)
        assert len(candidate) == 1
        assert candidate[0].title == "Candidate Decision"

        discussion = self.isolation.get_decisions_by_layer(decisions, IsolationLayer.DISCUSSION)
        assert len(discussion) == 1
        assert discussion[0].title == "Discussion Decision"

    def test_quarantine(self):
        """Test quarantine sets quarantined flag."""
        decision = Decision(
            title="Test Decision",
            summary="Test summary",
            context="Test context",
            decision="Test decision",
            rationale="Test rationale",
            category=DecisionCategory.ARCHITECTURE,
            certainty=DecisionCertainty.CONFIRMED,
        )
        assert decision.quarantined is False

        quarantined_decision = self.isolation.quarantine(decision)
        assert quarantined_decision.quarantined is True
        assert quarantined_decision is decision  # Same object

    def test_release_from_quarantine(self):
        """Test release_from_quarantine clears flag and reclassifies."""
        decision = Decision(
            title="Test Decision",
            summary="Test summary",
            context="Test context",
            decision="Test decision",
            rationale="Test rationale",
            category=DecisionCategory.ARCHITECTURE,
            certainty=DecisionCertainty.CONFIRMED,
            quarantined=True,
        )

        released_decision = self.isolation.release_from_quarantine(decision)
        assert released_decision.quarantined is False
        assert released_decision is decision  # Same object

        # Should now classify based on certainty
        layer = self.isolation.classify_layer(released_decision)
        assert layer == IsolationLayer.TRUSTED


class TestDecisionContextInjector:
    """Test DecisionContextInjector class."""

    def setup_method(self):
        """Set up test."""
        self.isolation = DecisionIsolation()
        self.injector = DecisionContextInjector(self.isolation)

    def test_injection_rules_configuration(self):
        """Test INJECTION_RULES configuration matches spec."""
        rules = DecisionContextInjector.INJECTION_RULES

        # Trusted - inject without prefix, no age limit for CONFIRMED
        assert rules[DecisionCertainty.CONFIRMED].inject is True
        assert rules[DecisionCertainty.CONFIRMED].prefix is None
        assert rules[DecisionCertainty.CONFIRMED].max_age_days is None

        # Trusted - inject without prefix, with age limit
        assert rules[DecisionCertainty.EVIDENCED].inject is True
        assert rules[DecisionCertainty.EVIDENCED].prefix is None
        assert rules[DecisionCertainty.EVIDENCED].max_age_days == 365

        assert rules[DecisionCertainty.EXPLICIT].inject is True
        assert rules[DecisionCertainty.EXPLICIT].prefix is None
        assert rules[DecisionCertainty.EXPLICIT].max_age_days == 180

        # Candidate - inject with prefix, with age limit
        assert rules[DecisionCertainty.INFERRED].inject is True
        assert rules[DecisionCertainty.INFERRED].prefix == "[待确认] "
        assert rules[DecisionCertainty.INFERRED].max_age_days == 30

        assert rules[DecisionCertainty.IMPLICIT].inject is True
        assert rules[DecisionCertainty.IMPLICIT].prefix == "[推断] "
        assert rules[DecisionCertainty.IMPLICIT].max_age_days == 14

        # Discussion and below - don't inject
        assert rules[DecisionCertainty.TENTATIVE].inject is False
        assert rules[DecisionCertainty.DISCUSSING].inject is False
        assert rules[DecisionCertainty.UNCERTAIN].inject is False
        assert rules[DecisionCertainty.DISPUTED].inject is False
        assert rules[DecisionCertainty.RETRACTED].inject is False

    def test_get_injectable_decisions_mixed_certainties(self):
        """Test get_injectable_decisions with mixed certainty levels."""
        now = datetime.now()
        decisions = [
            Decision(
                title="Confirmed Decision",
                summary="Test summary",
                context="Test context",
                decision="Test decision",
                rationale="Test rationale",
                category=DecisionCategory.ARCHITECTURE,
                certainty=DecisionCertainty.CONFIRMED,
                decided_at=now - timedelta(days=10),
            ),
            Decision(
                title="Inferred Decision",
                summary="Test summary",
                context="Test context",
                decision="Test decision",
                rationale="Test rationale",
                category=DecisionCategory.ARCHITECTURE,
                certainty=DecisionCertainty.INFERRED,
                decided_at=now - timedelta(days=10),
            ),
            Decision(
                title="Tentative Decision",
                summary="Test summary",
                context="Test context",
                decision="Test decision",
                rationale="Test rationale",
                category=DecisionCategory.ARCHITECTURE,
                certainty=DecisionCertainty.TENTATIVE,
                decided_at=now - timedelta(days=10),
            ),
        ]

        injectable = self.injector.get_injectable_decisions(decisions)

        # Only CONFIRMED and INFERRED should be injectable
        assert len(injectable) == 2
        titles = [d.content for d in injectable]
        assert any("Confirmed Decision" in content for content in titles)
        assert any("Inferred Decision" in content for content in titles)
        assert not any("Tentative Decision" in content for content in titles)

    def test_get_injectable_decisions_respects_max_age(self):
        """Test get_injectable_decisions respects max_age_days."""
        now = datetime.now()
        decisions = [
            Decision(
                title="Recent Inferred",
                summary="Test summary",
                context="Test context",
                decision="Test decision",
                rationale="Test rationale",
                category=DecisionCategory.ARCHITECTURE,
                certainty=DecisionCertainty.INFERRED,
                decided_at=now - timedelta(days=10),  # Within 30 days
            ),
            Decision(
                title="Old Inferred",
                summary="Test summary",
                context="Test context",
                decision="Test decision",
                rationale="Test rationale",
                category=DecisionCategory.ARCHITECTURE,
                certainty=DecisionCertainty.INFERRED,
                decided_at=now - timedelta(days=50),  # Over 30 days
            ),
        ]

        injectable = self.injector.get_injectable_decisions(decisions)

        # Only recent decision should be injectable
        assert len(injectable) == 1
        assert "Recent Inferred" in injectable[0].content

    def test_get_injectable_decisions_respects_limit(self):
        """Test get_injectable_decisions respects max_decisions limit."""
        now = datetime.now()
        decisions = [
            Decision(
                title=f"Decision {i}",
                summary="Test summary",
                context="Test context",
                decision="Test decision",
                rationale="Test rationale",
                category=DecisionCategory.ARCHITECTURE,
                certainty=DecisionCertainty.CONFIRMED,
                decided_at=now - timedelta(days=i),
            )
            for i in range(10)
        ]

        injectable = self.injector.get_injectable_decisions(decisions, max_decisions=3)

        # Should limit to 3 decisions
        assert len(injectable) == 3

    def test_format_for_context_with_prefix(self):
        """Test format_for_context applies prefix for candidate decisions."""
        decision = Decision(
            title="Inferred Decision",
            summary="This is a summary",
            context="Test context",
            decision="We should use approach X",
            rationale="Because it's better",
            category=DecisionCategory.ARCHITECTURE,
            certainty=DecisionCertainty.INFERRED,
        )

        formatted = self.injector.format_for_context(decision)

        # Should include prefix and all key information
        assert formatted.startswith("[待确认] ")
        assert "Inferred Decision" in formatted
        assert "We should use approach X" in formatted

    def test_format_for_context_without_prefix(self):
        """Test format_for_context for trusted decisions without prefix."""
        decision = Decision(
            title="Confirmed Decision",
            summary="This is a summary",
            context="Test context",
            decision="We will use approach X",
            rationale="Because it's proven",
            category=DecisionCategory.ARCHITECTURE,
            certainty=DecisionCertainty.CONFIRMED,
        )

        formatted = self.injector.format_for_context(decision)

        # Should not include prefix but include key information
        assert not formatted.startswith("[")
        assert "Confirmed Decision" in formatted
        assert "We will use approach X" in formatted

    def test_format_for_response_certainty_badges(self):
        """Test format_for_response with certainty badges."""
        confirmed_decision = Decision(
            title="Confirmed Decision",
            summary="Test summary",
            context="Test context",
            decision="Test decision",
            rationale="Test rationale",
            category=DecisionCategory.ARCHITECTURE,
            certainty=DecisionCertainty.CONFIRMED,
        )

        evidenced_decision = Decision(
            title="Evidenced Decision",
            summary="Test summary",
            context="Test context",
            decision="Test decision",
            rationale="Test rationale",
            category=DecisionCategory.ARCHITECTURE,
            certainty=DecisionCertainty.EVIDENCED,
        )

        inferred_decision = Decision(
            title="Inferred Decision",
            summary="Test summary",
            context="Test context",
            decision="Test decision",
            rationale="Test rationale",
            category=DecisionCategory.ARCHITECTURE,
            certainty=DecisionCertainty.INFERRED,
        )

        uncertain_decision = Decision(
            title="Uncertain Decision",
            summary="Test summary",
            context="Test context",
            decision="Test decision",
            rationale="Test rationale",
            category=DecisionCategory.ARCHITECTURE,
            certainty=DecisionCertainty.UNCERTAIN,
        )

        confirmed_formatted = self.injector.format_for_response(confirmed_decision)
        assert "✅ 已确认" in confirmed_formatted

        evidenced_formatted = self.injector.format_for_response(evidenced_decision)
        assert "📝 有证据" in evidenced_formatted

        inferred_formatted = self.injector.format_for_response(inferred_decision)
        assert "⚠️ 待确认" in inferred_formatted

        uncertain_formatted = self.injector.format_for_response(uncertain_decision)
        assert "❓ 不确定" in uncertain_formatted


class TestInjectedDecision:
    """Test InjectedDecision model."""

    def test_injected_decision_creation(self):
        """Test InjectedDecision creation."""
        now = datetime.now()
        injected = InjectedDecision(
            decision_id="test-id",
            content="[待确认] Test Decision: Use approach X",
            certainty=DecisionCertainty.INFERRED,
            decided_at=now,
            layer=IsolationLayer.CANDIDATE,
        )

        assert injected.decision_id == "test-id"
        assert injected.content == "[待确认] Test Decision: Use approach X"
        assert injected.certainty == DecisionCertainty.INFERRED
        assert injected.decided_at == now
        assert injected.layer == IsolationLayer.CANDIDATE

    def test_injected_decision_optional_fields(self):
        """Test InjectedDecision with optional fields."""
        injected = InjectedDecision(
            decision_id="test-id",
            content="Test Decision: Use approach X",
            certainty=DecisionCertainty.CONFIRMED,
            layer=IsolationLayer.TRUSTED,
        )

        assert injected.decided_at is None