"""Decision isolation and context injection system."""

from __future__ import annotations

import logging
from datetime import datetime
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel

from .models import Decision, DecisionCertainty

logger = logging.getLogger(__name__)


class IsolationLayer(StrEnum):
    """Isolation layer enumeration for decision access control."""

    TRUSTED = "trusted"  # Layer 1: Full retrieval + context injection
    CANDIDATE = "candidate"  # Layer 2: Only on explicit query, not auto-injected
    DISCUSSION = "discussion"  # Layer 3: History only, no retrieval
    QUARANTINE = "quarantine"  # Layer 4: Admin only, fully isolated


class InjectionRule(BaseModel):
    """Rule for decision context injection."""

    inject: bool
    prefix: Optional[str] = None
    max_age_days: Optional[int] = None

    model_config = {"from_attributes": True}


class InjectedDecision(BaseModel):
    """Decision formatted for context injection."""

    decision_id: str
    content: str  # formatted content with prefix
    certainty: DecisionCertainty
    decided_at: Optional[datetime] = None
    layer: IsolationLayer

    model_config = {"from_attributes": True}


class DecisionIsolation:
    """Decision isolation layer management."""

    # Mapping: certainty → layer
    LAYER_MAPPING: dict[DecisionCertainty, IsolationLayer] = {
        DecisionCertainty.CONFIRMED: IsolationLayer.TRUSTED,
        DecisionCertainty.EVIDENCED: IsolationLayer.TRUSTED,
        DecisionCertainty.EXPLICIT: IsolationLayer.TRUSTED,
        DecisionCertainty.INFERRED: IsolationLayer.CANDIDATE,
        DecisionCertainty.IMPLICIT: IsolationLayer.CANDIDATE,
        DecisionCertainty.TENTATIVE: IsolationLayer.DISCUSSION,
        DecisionCertainty.DISCUSSING: IsolationLayer.DISCUSSION,
        DecisionCertainty.UNCERTAIN: IsolationLayer.DISCUSSION,
        DecisionCertainty.DISPUTED: IsolationLayer.QUARANTINE,
        DecisionCertainty.RETRACTED: IsolationLayer.QUARANTINE,
    }

    def classify_layer(self, decision: Decision) -> IsolationLayer:
        """
        Determine which isolation layer a decision belongs to.

        Args:
            decision: Decision to classify

        Returns:
            IsolationLayer for the decision
        """
        # If quarantined=True → QUARANTINE regardless of certainty
        if decision.quarantined:
            return IsolationLayer.QUARANTINE

        # Otherwise map by certainty
        return self.LAYER_MAPPING[decision.certainty]

    def is_retrievable(self, decision: Decision) -> bool:
        """
        Check if decision can appear in search results.

        Args:
            decision: Decision to check

        Returns:
            True if decision is retrievable
        """
        layer = self.classify_layer(decision)
        # Trusted + Candidate are retrievable
        return layer in (IsolationLayer.TRUSTED, IsolationLayer.CANDIDATE)

    def is_injectable(self, decision: Decision) -> bool:
        """
        Check if decision can be auto-injected into context.

        Args:
            decision: Decision to check

        Returns:
            True if decision can be auto-injected
        """
        layer = self.classify_layer(decision)
        # Only Trusted layer
        return layer == IsolationLayer.TRUSTED

    def get_decisions_by_layer(self, decisions: list[Decision], layer: IsolationLayer) -> list[Decision]:
        """
        Filter decisions by isolation layer.

        Args:
            decisions: List of decisions to filter
            layer: Target isolation layer

        Returns:
            Filtered list of decisions
        """
        return [d for d in decisions if self.classify_layer(d) == layer]

    def quarantine(self, decision: Decision) -> Decision:
        """
        Move decision to quarantine.

        Args:
            decision: Decision to quarantine

        Returns:
            Same decision instance with quarantined=True
        """
        decision.quarantined = True
        return decision

    def release_from_quarantine(self, decision: Decision) -> Decision:
        """
        Release decision from quarantine.

        Args:
            decision: Decision to release

        Returns:
            Same decision instance with quarantined=False
        """
        decision.quarantined = False
        return decision


class DecisionContextInjector:
    """Context injection rules and formatting for decisions."""

    # Configuration based on design spec
    INJECTION_RULES: dict[DecisionCertainty, InjectionRule] = {
        DecisionCertainty.CONFIRMED: InjectionRule(inject=True, prefix=None, max_age_days=None),
        DecisionCertainty.EVIDENCED: InjectionRule(inject=True, prefix=None, max_age_days=365),
        DecisionCertainty.EXPLICIT: InjectionRule(inject=True, prefix=None, max_age_days=180),
        DecisionCertainty.INFERRED: InjectionRule(inject=True, prefix="[待确认] ", max_age_days=30),
        DecisionCertainty.IMPLICIT: InjectionRule(inject=True, prefix="[推断] ", max_age_days=14),
        DecisionCertainty.TENTATIVE: InjectionRule(inject=False),
        DecisionCertainty.DISCUSSING: InjectionRule(inject=False),
        DecisionCertainty.UNCERTAIN: InjectionRule(inject=False),
        DecisionCertainty.DISPUTED: InjectionRule(inject=False),
        DecisionCertainty.RETRACTED: InjectionRule(inject=False),
    }

    def __init__(self, isolation: DecisionIsolation):
        """
        Initialize injector.

        Args:
            isolation: DecisionIsolation instance for layer classification
        """
        self.isolation = isolation

    def get_injectable_decisions(
        self,
        decisions: list[Decision],
        max_decisions: int = 5,
    ) -> list[InjectedDecision]:
        """
        Filter and format decisions for context injection.

        Args:
            decisions: List of decisions to filter
            max_decisions: Maximum number of decisions to return

        Returns:
            List of formatted decisions ready for injection
        """
        injectable = []
        now = datetime.now()

        for decision in decisions:
            rule = self.INJECTION_RULES[decision.certainty]

            # 1. Check if decision is injectable
            if not rule.inject:
                continue

            # 2. Check max_age_days against decided_at
            if rule.max_age_days is not None and decision.decided_at is not None:
                age_days = (now - decision.decided_at).days
                if age_days > rule.max_age_days:
                    continue

            # 3. Format and create InjectedDecision
            content = self.format_for_context(decision)
            layer = self.isolation.classify_layer(decision)

            injected = InjectedDecision(
                decision_id=decision.id,
                content=content,
                certainty=decision.certainty,
                decided_at=decision.decided_at,
                layer=layer,
            )
            injectable.append(injected)

        # 4. Return up to max_decisions
        return injectable[:max_decisions]

    def format_for_context(self, decision: Decision) -> str:
        """
        Format a single decision for context injection.

        Args:
            decision: Decision to format

        Returns:
            Formatted string for context injection
        """
        rule = self.INJECTION_RULES[decision.certainty]

        # Build basic content
        content_parts = [
            f"**{decision.title}**",
            f"决策: {decision.decision}",
        ]

        # Add summary if meaningful
        if decision.summary and decision.summary != decision.title:
            content_parts.insert(1, f"摘要: {decision.summary}")

        # Add rationale if available
        if decision.rationale:
            content_parts.append(f"理由: {decision.rationale}")

        content = "\n".join(content_parts)

        # Apply prefix if configured
        if rule.prefix:
            content = rule.prefix + content

        return content

    def format_for_response(self, decision: Decision) -> str:
        """
        Format decision for user-facing response with certainty badge.

        Args:
            decision: Decision to format

        Returns:
            Formatted string with certainty badge
        """
        # Certainty badges based on design spec
        certainty_badges = {
            DecisionCertainty.CONFIRMED: "✅ 已确认",
            DecisionCertainty.EVIDENCED: "📝 有证据",
            DecisionCertainty.EXPLICIT: "📝 有证据",
            DecisionCertainty.INFERRED: "⚠️ 待确认",
            DecisionCertainty.IMPLICIT: "⚠️ 待确认",
        }

        # Default badge for discussion/quarantine levels
        badge = certainty_badges.get(decision.certainty, "❓ 不确定")

        # Build content
        content_parts = [
            f"{badge} **{decision.title}**",
            f"决策: {decision.decision}",
        ]

        # Add summary if meaningful
        if decision.summary and decision.summary != decision.title:
            content_parts.insert(1, f"摘要: {decision.summary}")

        # Add rationale if available
        if decision.rationale:
            content_parts.append(f"理由: {decision.rationale}")

        return "\n".join(content_parts)
