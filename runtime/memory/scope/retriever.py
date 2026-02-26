from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from runtime.memory.retrieval.engine import RetrievalEngine, RetrievalResult
from runtime.memory.scope.hierarchy import InheritanceMode, ScopeFilter, ScopePath
from runtime.memory.types.base import Memory, MemoryType


@dataclass(slots=True)
class ScopeAwareResult:
    memory: Memory
    score: float
    source: str
    scope_distance: int


class ScopeAwareRetriever:
    """范围感知检索器，在 RetrievalEngine 之上添加范围过滤和相关性排序。"""

    def __init__(
        self,
        retrieval_engine: RetrievalEngine,
        default_mode: InheritanceMode = InheritanceMode.ANCESTORS,
    ) -> None:
        self._retrieval_engine = retrieval_engine
        self._default_mode = default_mode

    async def retrieve(
        self,
        query: str,
        current_scope: ScopePath,
        inheritance: Optional[InheritanceMode] = None,
        memory_types: Optional[list[MemoryType]] = None,
        time_range: Optional[tuple[datetime, datetime]] = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[ScopeAwareResult]:
        """执行带范围过滤与排序的检索。"""

        mode = inheritance or self._default_mode
        scope_filter = ScopeFilter.from_scope(current_scope, mode)

        raw_results = await self._retrieval_engine.search(
            query=query,
            memory_types=memory_types,
            scope=current_scope.to_legacy_scope(),
            time_range=time_range,
            limit=limit,
            min_score=min_score,
        )

        filtered_results: list[tuple[RetrievalResult, ScopePath]] = []
        for result in raw_results:
            memory_scope_path = ScopePath.from_legacy_scope(
                result.memory.metadata.scope, current_scope.user_id
            )
            if scope_filter.matches(memory_scope_path):
                filtered_results.append((result, memory_scope_path))

        sorted_results = self._sort_by_scope_relevance(filtered_results, current_scope)
        return sorted_results[:limit]

    def _sort_by_scope_relevance(
        self,
        results: list[tuple[RetrievalResult, ScopePath]],
        current_scope: ScopePath,
    ) -> list[ScopeAwareResult]:
        scoped_results: list[ScopeAwareResult] = []
        for result, memory_scope in results:
            scope_distance = self._compute_scope_distance(memory_scope, current_scope)
            scoped_results.append(
                ScopeAwareResult(
                    memory=result.memory,
                    score=result.score,
                    source=result.source,
                    scope_distance=scope_distance,
                )
            )

        return sorted(scoped_results, key=lambda item: (abs(item.scope_distance), -item.score))

    def _compute_scope_distance(self, memory_scope: ScopePath, current_scope: ScopePath) -> int:
        return current_scope.distance_to(memory_scope)
