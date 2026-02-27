"""Decision recognition module."""

from __future__ import annotations

import logging
import re
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel

from .certainty import CertaintyAssessor
from .models import Decision, DecisionCategory

logger = logging.getLogger(__name__)


class SignalType(StrEnum):
    """Signal type enumeration for decision recognition."""

    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"
    CHANGE = "change"
    EXECUTION = "execution"


class SignalMatch(BaseModel):
    """Individual signal match in text."""

    signal_type: SignalType
    pattern: str
    matched_text: str
    confidence_contribution: float

    model_config = {"from_attributes": True}


class RecognitionResult(BaseModel):
    """Result of decision recognition process."""

    is_decision: bool
    confidence: float              # 0-1
    signals: list[SignalMatch]
    decision: Optional[Decision] = None  # Populated if is_decision=True
    reason: str = ""               # Why it is/isn't a decision

    model_config = {"from_attributes": True}


class DecisionRecognizer:
    """Recognize decisions from text content using signal pattern matching."""

    # Strong signal patterns - explicit decision statements
    STRONG_PATTERNS = [
        r"决定(使用|采用|选择|实施|放弃)",
        r"(确定|敲定|最终)方案",
        r"(经过|经|综合).*?(讨论|评估|考虑).*?(决定|采用)",
        r"ADR[:\s]*",
        r"技术选型[:\s]*",
        r"(we|I)\s+(decided|choose|selected|agreed)",
        r"(decision|conclusion)[:\s]",
    ]

    # Medium signal patterns - likely decisions
    MEDIUM_PATTERNS = [
        r"(应该|需要|必须)(使用|采用)",
        r"(建议|推荐)(使用|采用).*?(因为|由于)",
        r"(优先|首选|默认)(使用|选择)",
        r"(will|should|must)\s+use",
    ]

    # Weak signal patterns - potential decisions
    WEAK_PATTERNS = [
        r"(考虑|计划|打算)(使用|采用)",
        r"(可能|或许)(会|要)",
        r"(might|may|could)\s+use",
    ]

    # Change signal patterns - migration/modification decisions
    CHANGE_PATTERNS = [
        r"(迁移|切换|替换|升级)(到|为)",
        r"(不再|停止|放弃)(使用|采用)",
        r"(migrate|switch|replace|upgrade)\s+(to|from)",
        r"(deprecate|abandon|remove)",
    ]

    # Execution signal patterns - implementation evidence
    EXECUTION_PATTERNS = [
        r"(已|完成)(实现|配置|部署|上线)",
        r"(implemented|deployed|configured|completed)",
        r"(merged|committed)\s+.*?(PR|pull request)",
    ]

    # Category inference keywords
    CATEGORY_KEYWORDS = {
        DecisionCategory.ARCHITECTURE: ["架构", "architecture", "microservice", "monolith", "模块", "分层"],
        DecisionCategory.TECHNOLOGY: ["框架", "库", "framework", "library", "redis", "postgres", "技术", "选型"],
        DecisionCategory.DESIGN: ["设计", "模式", "pattern", "UI", "UX", "接口", "API"],
        DecisionCategory.PROCESS: ["流程", "部署", "CI/CD", "workflow", "process", "pipeline"],
        DecisionCategory.SECURITY: ["安全", "security", "auth", "加密", "权限"],
        DecisionCategory.PERFORMANCE: ["性能", "performance", "优化", "缓存", "cache"],
    }

    # Minimum confidence threshold to consider as decision
    CONFIDENCE_THRESHOLD = 0.3

    def __init__(self, certainty_assessor: CertaintyAssessor):
        """
        Initialize decision recognizer.

        Args:
            certainty_assessor: CertaintyAssessor instance for decision assessment
        """
        self.certainty_assessor = certainty_assessor

    def recognize(self, content: str, context: dict[str, Any] | None = None) -> RecognitionResult:
        """
        Recognize decision from text content.

        Args:
            content: Text to analyze
            context: Optional context (project_id, source, etc.)

        Returns:
            RecognitionResult with decision if recognized
        """
        if context is None:
            context = {}

        # Step 1: Detect signals
        signals = self.detect_signals(content)

        # Step 2: Calculate confidence
        confidence = self.calculate_confidence(signals)

        # Step 3: Check if above threshold
        if confidence < self.CONFIDENCE_THRESHOLD:
            return RecognitionResult(
                is_decision=False,
                confidence=confidence,
                signals=signals,
                reason="Confidence below threshold"
            )

        # Step 4: Extract decision
        decision = self.extract_decision(content, confidence, signals, context)

        logger.debug(
            "Recognized decision: %s (confidence=%.3f, signals=%d)",
            decision.title,
            confidence,
            len(signals)
        )

        return RecognitionResult(
            is_decision=True,
            confidence=confidence,
            signals=signals,
            decision=decision,
            reason="Decision recognized with sufficient confidence"
        )

    def detect_signals(self, text: str) -> list[SignalMatch]:
        """
        Detect all decision signals in text.

        Args:
            text: Text to analyze

        Returns:
            List of signal matches found
        """
        signals = []
        text_lower = text.lower()

        # Define pattern groups with their signal types and confidence contributions
        pattern_groups = [
            (self.STRONG_PATTERNS, SignalType.STRONG, 0.8),
            (self.MEDIUM_PATTERNS, SignalType.MEDIUM, 0.5),
            (self.WEAK_PATTERNS, SignalType.WEAK, 0.3),
            (self.CHANGE_PATTERNS, SignalType.CHANGE, 0.1),
            (self.EXECUTION_PATTERNS, SignalType.EXECUTION, 0.2),
        ]

        for patterns, signal_type, contribution in pattern_groups:
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    signals.append(SignalMatch(
                        signal_type=signal_type,
                        pattern=pattern,
                        matched_text=match.group(),
                        confidence_contribution=contribution
                    ))
                    logger.debug(
                        "Found %s signal: %s -> %s",
                        signal_type.value,
                        pattern,
                        match.group()
                    )

        return signals

    def calculate_confidence(self, signals: list[SignalMatch]) -> float:
        """
        Calculate overall confidence from signals.

        Args:
            signals: List of signal matches

        Returns:
            Confidence score (0.0-1.0)
        """
        if not signals:
            return 0.0

        # Base confidence from strongest signal
        base_confidence = max(s.confidence_contribution for s in signals)

        # Bonus from multiple strong signals (cap at 1.0)
        strong_signals = [s for s in signals if s.signal_type == SignalType.STRONG]
        if len(strong_signals) > 1:
            bonus = (len(strong_signals) - 1) * 0.1
            base_confidence = min(1.0, base_confidence + bonus)

        # Bonuses from change and execution signals
        change_bonus = sum(
            s.confidence_contribution for s in signals
            if s.signal_type == SignalType.CHANGE
        )
        execution_bonus = sum(
            s.confidence_contribution for s in signals
            if s.signal_type == SignalType.EXECUTION
        )

        total_confidence = base_confidence + change_bonus + execution_bonus

        # Ensure confidence is capped at 1.0
        return min(1.0, total_confidence)

    def extract_decision(
        self,
        content: str,
        confidence: float,
        signals: list[SignalMatch],
        context: dict[str, Any] | None = None
    ) -> Decision:
        """
        Extract structured Decision from text.

        Creates a Decision with:
        - title: first 50 chars of content or first sentence
        - summary: first 100 chars
        - decision: the content itself
        - context: from context dict if available
        - category: inferred from content keywords
        - confidence: from signal analysis
        - certainty: assessed by CertaintyAssessor

        Args:
            content: Decision text content
            confidence: Calculated confidence score
            signals: List of detected signals
            context: Optional context dictionary

        Returns:
            Decision instance
        """
        if context is None:
            context = {}

        # Extract title (first 50 chars)
        title = self._extract_title(content)

        # Extract summary (first 100 chars)
        summary = content[:100]
        if len(content) > 100:
            summary += "..."

        # Infer category from content
        category = self._infer_category(content)

        # Create decision with basic fields
        decision = Decision(
            title=title,
            summary=summary,
            context="",  # Empty for now, could be populated from context dict
            decision=content,
            rationale="",  # Empty for now, could be extracted via LLM
            category=category,
            confidence=confidence,
            project_id=context.get("project_id"),
        )

        # Assess certainty using CertaintyAssessor
        certainty_result = self.certainty_assessor.assess(decision)
        decision.certainty = certainty_result.certainty

        return decision

    def _infer_category(self, content: str) -> DecisionCategory:
        """
        Infer decision category from content keywords.

        Args:
            content: Decision text content

        Returns:
            Inferred DecisionCategory
        """
        content_lower = content.lower()

        # Count keyword matches for each category
        category_scores = {}
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword.lower() in content_lower)
            if score > 0:
                category_scores[category] = score

        # Return category with highest score, default to TECHNOLOGY
        if category_scores:
            return max(category_scores.keys(), key=lambda c: category_scores[c])
        return DecisionCategory.TECHNOLOGY

    def _extract_title(self, content: str) -> str:
        """
        Extract a short title from content (max 50 chars).

        Args:
            content: Decision text content

        Returns:
            Title string (max 50 chars)
        """
        # Try to get first sentence
        sentences = re.split(r'[.。!！?？]', content.strip())
        first_sentence = sentences[0].strip()

        # If first sentence is short enough, use it
        if len(first_sentence) <= 50:
            return first_sentence

        # Otherwise truncate to 50 chars
        if len(content) > 50:
            truncated = content[:47].strip()
            return truncated + "..."
        else:
            return content.strip()