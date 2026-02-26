"""Attention-weighted reranking for retrieval results."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from runtime.memory.retrieval.fusion import FusedResult
from runtime.memory.types.base import Memory


@dataclass(slots=True)
class RankedMemory:
    """Result of attention-weighted reranking."""

    memory: Memory
    final_score: float
    sources: list[str]


class AttentionWeightedReranker:
    """Reranks memories using level-based, attention, and freshness weighting.

    Applies multiple weighting factors to improve relevance ranking:
    - Level-based weights (L4_CORE gets highest weight)
    - Attention score weighting (up to 30% boost)
    - Freshness/recency weighting with exponential decay
    """

    def __init__(
        self,
        level_weights: dict[str, float] | None = None,
        attention_weight: float = 0.3,
        freshness_decay_hours: float = 48.0,
    ) -> None:
        """Initialize reranker with weighting configuration.

        Args:
            level_weights: Weight multipliers by memory level
            attention_weight: Maximum boost from attention score (0.0-1.0)
            freshness_decay_hours: Hours for freshness to decay to ~37% (1/e)
        """
        self.level_weights = level_weights or {
            "L4_CORE": 1.5,
            "L3_LONG": 1.3,
            "L2_SHORT": 1.1,
            "L1_WORKING": 1.0,
            "L0_TRANSIENT": 0.8,
        }
        self.attention_weight = attention_weight
        self.freshness_decay_hours = freshness_decay_hours

    def rerank(
        self,
        fused_results: list[FusedResult],
        memory_lookup: dict[str, Memory],
    ) -> list[RankedMemory]:
        """Rerank fused results using attention and level weighting.

        Args:
            fused_results: List of RRF-fused results
            memory_lookup: Mapping from memory_id to Memory object

        Returns:
            List of RankedMemory objects sorted by final score (best first).
        """
        ranked_results: list[RankedMemory] = []

        for fused_result in fused_results:
            memory = memory_lookup.get(fused_result.memory_id)
            if memory is None:
                continue

            # Calculate final score with all weighting factors
            final_score = self._calculate_final_score(fused_result.score, memory)

            ranked_results.append(
                RankedMemory(
                    memory=memory,
                    final_score=final_score,
                    sources=fused_result.sources
                )
            )

        # Sort by final score descending
        ranked_results.sort(key=lambda r: r.final_score, reverse=True)
        return ranked_results

    def _calculate_final_score(self, base_score: float, memory: Memory) -> float:
        """Calculate final weighted score for a memory.

        Args:
            base_score: Base RRF fusion score
            memory: Memory object with metadata

        Returns:
            Final weighted score
        """
        final_score = base_score

        # Apply level-based weighting
        level_weight = self._get_level_weight(memory)
        final_score *= level_weight

        # Apply attention score weighting
        attention_multiplier = self._get_attention_multiplier(memory)
        final_score *= attention_multiplier

        # Apply freshness weighting
        freshness_multiplier = self._get_freshness_multiplier(memory)
        final_score *= freshness_multiplier

        return final_score

    def _get_level_weight(self, memory: Memory) -> float:
        """Get level-based weight multiplier.

        Args:
            memory: Memory object

        Returns:
            Weight multiplier based on memory level
        """
        level = memory.metadata.extra.get("level")
        if level is None:
            return 1.0  # Default weight for unknown level
        return self.level_weights.get(level, 1.0)

    def _get_attention_multiplier(self, memory: Memory) -> float:
        """Get attention score multiplier.

        Args:
            memory: Memory object

        Returns:
            Multiplier based on attention score (1.0 + boost)
        """
        attention_score = memory.metadata.extra.get("attention_score")
        if attention_score is None:
            # Fallback to importance if no attention_score
            attention_score = memory.importance

        # Convert to multiplier: attention_score of 1.0 gives max boost
        boost = self.attention_weight * attention_score
        return 1.0 + boost

    def _get_freshness_multiplier(self, memory: Memory) -> float:
        """Get freshness/recency weight multiplier.

        Args:
            memory: Memory object

        Returns:
            Multiplier based on memory age (newer = higher)
        """
        now = datetime.now()
        age_hours = (now - memory.created_at).total_seconds() / 3600.0

        # Exponential decay: e^(-age/decay_time)
        decay_factor = math.exp(-age_hours / self.freshness_decay_hours)

        # Convert to multiplier (minimum 0.5, maximum 1.5)
        return 0.5 + decay_factor