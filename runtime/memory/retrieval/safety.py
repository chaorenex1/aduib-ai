"""Safety filtering for memory retrieval.

This module provides post-retrieval safety filtering for memory results,
focusing on:
- Decision certainty filtering based on safety levels
- Scope permission filtering
- Quarantine filtering (always excluded)
- Safety annotation for results requiring verification
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from runtime.memory.retrieval.reranker import RankedMemory
from runtime.memory.types.base import Memory, MemoryScope


class SafetyLevel(StrEnum):
    """Controls strictness of retrieval filtering for decision memories.

    STRICT: Only CONFIRMED + EVIDENCED decisions with status IMPLEMENTED
    STANDARD: High-certainty decisions (CONFIRMED, EVIDENCED, EXPLICIT)
    LOOSE: Include inferred/implicit decisions (with warning markers)
    """

    STRICT = "strict"
    STANDARD = "standard"
    LOOSE = "loose"


@dataclass(slots=True)
class SafetyAnnotation:
    """Safety annotation attached to a retrieval result."""

    can_cite: bool
    needs_verification: bool
    warning: str | None


@dataclass(slots=True)
class SafeRetrievalResult:
    """Retrieval result with safety annotation."""

    memory: Memory
    score: float
    sources: list[str]
    safety: SafetyAnnotation


class SafetyFilter:
    """Post-retrieval safety filter for memory results."""

    def __init__(self, safety_level: SafetyLevel = SafetyLevel.STANDARD):
        """Initialize safety filter.

        Args:
            safety_level: Safety level for filtering decisions
        """
        self.safety_level = safety_level

    def apply(
        self,
        results: list[RankedMemory],
        user_id: str | None = None,
        allowed_scopes: list[MemoryScope] | None = None,
    ) -> list[SafeRetrievalResult]:
        """Filter and annotate retrieval results based on safety rules.

        Args:
            results: List of ranked memories to filter
            user_id: User ID for permission filtering
            allowed_scopes: List of allowed scopes for filtering

        Returns:
            List of filtered and annotated safe retrieval results
        """
        if not results:
            return []

        safe_results: list[SafeRetrievalResult] = []

        for ranked_memory in results:
            memory = ranked_memory.memory

            # Skip if user doesn't have access
            if not self._has_user_access(memory, user_id):
                continue

            # Skip if scope not allowed
            if not self._has_scope_access(memory, allowed_scopes):
                continue

            # Always filter out quarantined memories
            if self._is_quarantined(memory):
                continue

            # Apply decision certainty filtering
            if self._is_decision_memory(memory) and not self._passes_decision_filter(memory):
                continue

            # Create safety annotation
            safety = self._create_safety_annotation(memory)

            safe_results.append(
                SafeRetrievalResult(
                    memory=memory,
                    score=ranked_memory.final_score,
                    sources=ranked_memory.sources,
                    safety=safety,
                )
            )

        return safe_results

    def _has_user_access(self, memory: Memory, user_id: str | None) -> bool:
        """Check if user has access to memory.

        Args:
            memory: Memory to check
            user_id: User ID to check access for

        Returns:
            True if user has access, False otherwise
        """
        if user_id is None:
            return True

        # User always has access to their own memories
        return memory.metadata.user_id == user_id

    def _has_scope_access(self, memory: Memory, allowed_scopes: list[MemoryScope] | None) -> bool:
        """Check if memory scope is allowed.

        Args:
            memory: Memory to check
            allowed_scopes: List of allowed scopes

        Returns:
            True if scope is allowed, False otherwise
        """
        if allowed_scopes is None:
            return True

        return memory.metadata.scope in allowed_scopes

    def _is_quarantined(self, memory: Memory) -> bool:
        """Check if memory is quarantined.

        Args:
            memory: Memory to check

        Returns:
            True if memory is quarantined
        """
        return memory.metadata.extra.get("quarantined", False)

    def _is_decision_memory(self, memory: Memory) -> bool:
        """Check if memory is a decision memory.

        Args:
            memory: Memory to check

        Returns:
            True if memory is a decision
        """
        return memory.metadata.extra.get("is_decision", False)

    def _passes_decision_filter(self, memory: Memory) -> bool:
        """Check if decision memory passes certainty filter.

        Args:
            memory: Decision memory to check

        Returns:
            True if decision passes filter for current safety level
        """
        certainty = memory.metadata.extra.get("certainty", "").lower()
        status = memory.metadata.extra.get("status", "").lower()

        # Decision filtering rules by safety level
        if self.safety_level == SafetyLevel.STRICT:
            # Only confirmed decisions with implemented status
            return certainty in ["confirmed", "evidenced"] and status == "implemented"

        if self.safety_level == SafetyLevel.STANDARD:
            # High-certainty decisions
            return certainty in ["confirmed", "evidenced", "explicit"]

        if self.safety_level == SafetyLevel.LOOSE:
            # All except retracted/disputed
            return certainty not in ["retracted", "disputed"]

        return True

    def _create_safety_annotation(self, memory: Memory) -> SafetyAnnotation:
        """Create safety annotation for memory.

        Args:
            memory: Memory to annotate

        Returns:
            Safety annotation
        """
        if not self._is_decision_memory(memory):
            # Non-decision memories are safe to cite
            return SafetyAnnotation(
                can_cite=True,
                needs_verification=False,
                warning=None,
            )

        certainty = memory.metadata.extra.get("certainty", "").lower()

        # High-certainty decisions are safe to cite
        if certainty in ["confirmed", "evidenced", "explicit"]:
            return SafetyAnnotation(
                can_cite=True,
                needs_verification=False,
                warning=None,
            )

        # Low-certainty decisions need verification
        warning = f"This decision has low certainty ({certainty}). Please verify before using."
        return SafetyAnnotation(
            can_cite=False,
            needs_verification=True,
            warning=warning,
        )