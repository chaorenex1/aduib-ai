"""Hybrid retrieval engine combining vector, graph, and keyword recall."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Coroutine, Optional

from runtime.memory.retrieval.engine import RetrievalEngine, RetrievalResult
from runtime.memory.types.base import Memory, MemoryScope, MemoryType

logger = logging.getLogger(__name__)

# RRF constant
RRF_K = 60


def rrf_fuse(
    source_results: dict[str, list[tuple[str, float]]],
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion across multiple recall sources.

    Args:
        source_results: mapping of source name to list of (memory_id, score)
            tuples, ordered by relevance (best first).

    Returns:
        Fused list of (memory_id, fused_score) sorted descending.
    """
    from runtime.memory.retrieval.fusion import RRFFusion

    # Delegate to new RRFFusion class for consistency
    fusion = RRFFusion(k=RRF_K)
    fused_results = fusion.fuse(source_results)

    # Convert back to original format for backward compatibility
    return [(result.memory_id, result.score) for result in fused_results]


class HybridRetrievalEngine(RetrievalEngine):
    """Concrete hybrid retrieval engine combining vector and graph recall.

    Implements the RetrievalEngine ABC with multi-path parallel recall
    and RRF score fusion.
    """

    def __init__(
        self,
        milvus_store: Any,
        embedder: Callable[[str], Coroutine[Any, Any, list[float]]],
        graph_layer: Any | None = None,
        recall_top_k: int = 100,
    ) -> None:
        self._milvus = milvus_store
        self._embedder = embedder
        self._graph = graph_layer
        self._recall_top_k = recall_top_k

    # ------------------------------------------------------------------
    # Public API (RetrievalEngine ABC)
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        memory_types: Optional[list[MemoryType]] = None,
        scope: Optional[MemoryScope] = None,
        time_range: Optional[tuple[datetime, datetime]] = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[RetrievalResult]:
        """Execute hybrid multi-path retrieval."""
        if not query or not query.strip():
            return []

        # Phase 1: Embed query
        query_embedding = await self._embedder(query)

        # Phase 2: Parallel multi-path recall
        recall_tasks: dict[str, Coroutine] = {
            "vector": self._vector_recall(query_embedding, self._recall_top_k),
        }

        if self._graph is not None:
            recall_tasks["graph"] = self._graph_recall_by_query(query)

        task_results = await asyncio.gather(
            *recall_tasks.values(), return_exceptions=True
        )

        # Collect recall results per source
        source_results: dict[str, list[tuple[str, float]]] = {}
        for name, result in zip(recall_tasks.keys(), task_results):
            if isinstance(result, Exception):
                logger.warning("Recall path %s failed: %s", name, result)
                continue
            source_results[name] = result

        # Phase 3: RRF fusion
        fused = rrf_fuse(source_results)

        # Phase 4: Fetch full memories and build results
        results = await self._build_results(
            fused, limit, min_score, memory_types, scope, time_range
        )

        return results

    async def search_by_embedding(
        self,
        embedding: list[float],
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[RetrievalResult]:
        """Vector similarity search."""
        raw = await self._vector_recall(embedding, limit * 2)

        results: list[RetrievalResult] = []
        for memory_id, score in raw:
            if score < min_score:
                continue
            memory = await self._milvus.get(memory_id)
            if memory is None:
                continue
            results.append(RetrievalResult(memory=memory, score=score, source="vector"))
            if len(results) >= limit:
                break

        return results

    async def search_by_entities(
        self,
        entity_ids: list[str],
        relation_types: Optional[list[str]] = None,
        limit: int = 10,
    ) -> list[RetrievalResult]:
        """Entity-based graph search."""
        if self._graph is None:
            return []

        results: list[RetrievalResult] = []
        seen: set[str] = set()

        for entity_id in entity_ids:
            refs = await self._graph.get_related_memories(entity_id, limit=limit)
            for ref in refs:
                mid = ref.memory_id if hasattr(ref, "memory_id") else str(ref)
                if mid in seen:
                    continue
                seen.add(mid)

                memory = await self._milvus.get(mid)
                if memory is None:
                    continue

                score = ref.score if hasattr(ref, "score") else 0.5
                results.append(
                    RetrievalResult(memory=memory, score=score, source="graph")
                )

            if len(results) >= limit:
                break

        results.sort(key=lambda r: -r.score)
        return results[:limit]

    # ------------------------------------------------------------------
    # Recall Paths (internal)
    # ------------------------------------------------------------------

    async def _vector_recall(
        self, embedding: list[float], top_k: int
    ) -> list[tuple[str, float]]:
        """Vector ANN recall via Milvus."""
        raw = await self._milvus.vector_search(embedding, top_k)
        return [
            (item["id"], item.get("distance", item.get("score", 0.0)))
            for item in raw
        ]

    async def _graph_recall_by_query(
        self, query: str, top_k: int = 30
    ) -> list[tuple[str, float]]:
        """Graph recall: find memories related to entities in query."""
        if self._graph is None:
            return []

        try:
            # Try to extract entities from query and find related memories
            entities = await self._graph.query_entities(query, limit=5)
            results: list[tuple[str, float]] = []
            seen: set[str] = set()

            for entity in entities:
                entity_id = entity.id if hasattr(entity, "id") else str(entity)
                refs = await self._graph.get_related_memories(entity_id, limit=top_k)
                for ref in refs:
                    mid = ref.memory_id if hasattr(ref, "memory_id") else str(ref)
                    if mid not in seen:
                        seen.add(mid)
                        score = ref.score if hasattr(ref, "score") else 0.5
                        results.append((mid, score))

            return results[:top_k]
        except Exception as e:
            logger.warning("Graph recall failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Result Building
    # ------------------------------------------------------------------

    async def _build_results(
        self,
        fused: list[tuple[str, float]],
        limit: int,
        min_score: float,
        memory_types: Optional[list[MemoryType]],
        scope: Optional[MemoryScope],
        time_range: Optional[tuple[datetime, datetime]],
    ) -> list[RetrievalResult]:
        """Fetch memories and apply filters."""
        results: list[RetrievalResult] = []

        # Fetch up to 2x limit to account for filtering
        candidates = fused[: limit * 3]

        for memory_id, score in candidates:
            if score < min_score:
                continue

            memory = await self._milvus.get(memory_id)
            if memory is None:
                continue

            # Apply filters
            if memory_types and memory.type not in memory_types:
                continue
            if scope and memory.metadata.scope != scope:
                continue
            if time_range:
                start, end = time_range
                if memory.created_at < start or memory.created_at > end:
                    continue

            results.append(
                RetrievalResult(memory=memory, score=score, source="hybrid")
            )
            if len(results) >= limit:
                break

        # Sort by score descending
        results.sort(key=lambda r: -r.score)
        return results
