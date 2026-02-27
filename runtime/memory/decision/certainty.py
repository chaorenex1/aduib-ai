"""Decision certainty assessment module."""

from __future__ import annotations

import logging
import re
from typing import Optional

from pydantic import BaseModel, Field

from .models import Decision, DecisionCertainty, Evidence

logger = logging.getLogger(__name__)


class DecisionContext(BaseModel):
    """Context for decision certainty assessment."""

    subsequent_references: int = 0
    conflicting_decisions: list[str] = Field(default_factory=list)
    occurrence_count: int = 1

    model_config = {"from_attributes": True}


class CertaintyFactor(BaseModel):
    """Individual factor contributing to certainty score."""

    name: str
    score: float
    weight: float
    details: str = ""

    model_config = {"from_attributes": True}


class CertaintyResult(BaseModel):
    """Result of certainty assessment."""

    certainty: DecisionCertainty
    score: float
    factors: list[CertaintyFactor] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class CertaintyAssessor:
    """Assess decision certainty using multi-factor scoring."""

    # Pattern lists for linguistic analysis
    HIGH_CERTAINTY_PATTERNS = [
        r"(决定|确定|敲定|最终)(了|使用|采用)",
        r"(我们|团队)(已经|已)(决定|确认)",
        r"(approved|decided|confirmed|finalized)",
    ]

    LOW_CERTAINTY_PATTERNS = [
        r"(考虑|讨论|商量|研究)(一下|中|ing)",
        r"(可能|或许|也许|暂时)(会|要|用)",
        r"(如果|假设|万一)",
        r"(还没|尚未|待)(决定|确认)",
        r"(might|maybe|perhaps|considering|discussing)",
        r"(not yet|haven't decided|still thinking)",
    ]

    NEGATION_PATTERNS = [
        r"(没有|不要|别|勿)(决定|使用|采用)",
        r"(取消|放弃|撤销)(了|这个)",
        r"(don't|won't|didn't|not going to)",
    ]

    # Weight configuration
    WEIGHTS = {
        "linguistic": 0.3,
        "evidence": 0.3,
        "user_confirmed": 0.25,
        "references": 0.15,
    }

    CONFLICT_PENALTY = 0.3

    def assess(
        self, decision: Decision, context: Optional[DecisionContext] = None
    ) -> CertaintyResult:
        """
        Assess certainty of a decision.

        Args:
            decision: Decision to assess
            context: Additional context for assessment

        Returns:
            CertaintyResult with score and certainty level
        """
        if context is None:
            context = DecisionContext()

        factors = []
        score = 0.0

        # Factor 1: Linguistic certainty
        linguistic_text = f"{decision.decision} {decision.rationale}".strip()
        linguistic_score = self.assess_linguistic(linguistic_text)
        linguistic_weight = self.WEIGHTS["linguistic"]
        score += linguistic_score * linguistic_weight

        factors.append(
            CertaintyFactor(
                name="linguistic",
                score=linguistic_score,
                weight=linguistic_weight,
                details="Language analysis of decision text",
            )
        )

        # Factor 2: Evidence score
        evidence_score = self._compute_evidence_score(decision.evidence)
        evidence_weight = self.WEIGHTS["evidence"]
        score += evidence_score * evidence_weight

        factors.append(
            CertaintyFactor(
                name="evidence",
                score=evidence_score,
                weight=evidence_weight,
                details=f"Based on {len(decision.evidence)} evidence items",
            )
        )

        # Factor 3: User confirmation
        user_confirmed_score = 1.0 if decision.user_confirmed else 0.0
        user_confirmed_weight = self.WEIGHTS["user_confirmed"]
        score += user_confirmed_score * user_confirmed_weight

        factors.append(
            CertaintyFactor(
                name="user_confirmed",
                score=user_confirmed_score,
                weight=user_confirmed_weight,
                details="User explicitly confirmed" if decision.user_confirmed else "No user confirmation",
            )
        )

        # Factor 4: Reference score
        reference_score = self._compute_reference_score(context.subsequent_references)
        reference_weight = self.WEIGHTS["references"]
        score += reference_score * reference_weight

        factors.append(
            CertaintyFactor(
                name="references",
                score=reference_score,
                weight=reference_weight,
                details=f"Referenced {context.subsequent_references} times later",
            )
        )

        # Factor 5: Conflict penalty
        if context.conflicting_decisions:
            conflict_penalty = self.CONFLICT_PENALTY
            score -= conflict_penalty

            factors.append(
                CertaintyFactor(
                    name="conflict_penalty",
                    score=-conflict_penalty,
                    weight=1.0,
                    details=f"Conflicts with {len(context.conflicting_decisions)} other decisions",
                )
            )

        # Ensure score is within bounds
        score = max(0.0, min(1.0, score))

        certainty = self.score_to_certainty(score)

        logger.debug(
            "Assessed decision certainty: %s (score=%.3f, factors=%d)",
            certainty.value,
            score,
            len(factors),
        )

        return CertaintyResult(
            certainty=certainty,
            score=score,
            factors=factors,
        )

    def assess_linguistic(self, text: str) -> float:
        """
        Analyze linguistic certainty of text.

        Args:
            text: Text to analyze

        Returns:
            Score between 0.0 and 1.0
        """
        if not text.strip():
            return 0.5

        text_lower = text.lower()

        # Check negation patterns first
        for pattern in self.NEGATION_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                logger.debug("Found negation pattern: %s", pattern)
                return 0.1

        # Check low certainty patterns before high certainty to catch "还没决定", "haven't decided" etc.
        for pattern in self.LOW_CERTAINTY_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                logger.debug("Found low certainty pattern: %s", pattern)
                return 0.3

        # Check high certainty patterns after low certainty
        for pattern in self.HIGH_CERTAINTY_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                logger.debug("Found high certainty pattern: %s", pattern)
                return 0.9

        # Default for neutral text
        return 0.5

    def score_to_certainty(self, score: float) -> DecisionCertainty:
        """
        Map numeric score to certainty level.

        Args:
            score: Numeric score (0.0-1.0)

        Returns:
            DecisionCertainty level
        """
        if score >= 0.85:
            return DecisionCertainty.CONFIRMED
        elif score >= 0.7:
            return DecisionCertainty.EVIDENCED
        elif score >= 0.55:
            return DecisionCertainty.EXPLICIT
        elif score >= 0.4:
            return DecisionCertainty.INFERRED
        elif score >= 0.3:
            return DecisionCertainty.IMPLICIT
        elif score >= 0.2:
            return DecisionCertainty.TENTATIVE
        elif score >= 0.1:
            return DecisionCertainty.DISCUSSING
        else:
            return DecisionCertainty.UNCERTAIN

    def _compute_evidence_score(self, evidence: list[Evidence]) -> float:
        """Compute evidence-based score."""
        verified_evidence = [e for e in evidence if e.verified]
        return min(1.0, len(verified_evidence) * 0.3)

    def _compute_reference_score(self, references: int) -> float:
        """Compute reference-based score."""
        return round(min(1.0, references * 0.2), 1)