"""RRF fusion for multi-source retrieval results."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(slots=True)
class FusedResult:
    """Result of RRF fusion combining multiple sources."""

    memory_id: str
    score: float
    sources: list[str]


class RRFFusion:
    """Reciprocal Rank Fusion for combining retrieval results from multiple sources.

    Implements the RRF algorithm with configurable parameters for source weighting
    and multi-hit bonuses.
    """

    def __init__(
        self,
        k: int = 60,
        source_weights: dict[str, float] | None = None,
        multi_hit_bonus: float = 0.1,
    ) -> None:
        """Initialize RRF fusion with configuration.

        Args:
            k: RRF constant for rank normalization (default 60)
            source_weights: Weight multipliers per source type
            multi_hit_bonus: Bonus multiplier for items found in 2+ sources
        """
        self.k = k
        self.source_weights = source_weights or {}
        self.multi_hit_bonus = multi_hit_bonus

    def fuse(
        self,
        source_results: dict[str, list[tuple[str, float]]],
    ) -> list[FusedResult]:
        """Fuse results from multiple sources using RRF algorithm.

        Args:
            source_results: Mapping of source name to list of (memory_id, score)
                tuples, ordered by relevance (best first).

        Returns:
            List of FusedResult objects sorted by fused score (best first).
        """
        if not source_results:
            return []

        scores: dict[str, float] = defaultdict(float)
        sources: dict[str, set[str]] = defaultdict(set)

        # Calculate RRF scores for each memory from each source
        for source, results in source_results.items():
            if not results:
                continue

            source_weight = self.source_weights.get(source, 1.0)

            for rank, (memory_id, _original_score) in enumerate(results, 1):
                rrf_score = source_weight / (self.k + rank)
                scores[memory_id] += rrf_score
                sources[memory_id].add(source)

        # Apply multi-hit bonus for items found in 2+ sources
        for memory_id in scores:
            source_count = len(sources[memory_id])
            if source_count >= 2:
                scores[memory_id] *= 1 + self.multi_hit_bonus * source_count

        # Sort by score descending and build results
        sorted_items = sorted(scores.items(), key=lambda x: -x[1])

        return [
            FusedResult(
                memory_id=memory_id,
                score=score,
                sources=list(sources[memory_id])
            )
            for memory_id, score in sorted_items
        ]