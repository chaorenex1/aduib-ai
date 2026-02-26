from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from runtime.memory.retrieval.engine import RetrievalEngine, RetrievalResult
from runtime.memory.scope.hierarchy import InheritanceMode, ScopePath
from runtime.memory.scope.retriever import ScopeAwareResult, ScopeAwareRetriever
from runtime.memory.types.base import Memory, MemoryMetadata, MemoryScope, MemoryType


def _make_memory(scope_str: str | MemoryScope, memory_id: str, user_id: str = "user-1") -> Memory:
    scope = MemoryScope(scope_str)
    metadata = MemoryMetadata(scope=scope, user_id=user_id)
    timestamp = datetime(2025, 1, 1)
    return Memory(
        id=memory_id,
        type=MemoryType.WORKING,
        content=f"content-{memory_id}",
        metadata=metadata,
        created_at=timestamp,
        updated_at=timestamp,
        accessed_at=timestamp,
    )


def _make_result(memory: Memory, score: float, source: str = "vector") -> RetrievalResult:
    return RetrievalResult(memory=memory, score=score, source=source)


class TestScopeAwareResult:
    def test_dataclass_fields(self) -> None:
        memory = _make_memory(MemoryScope.WORK, "mem-1")
        result = ScopeAwareResult(memory=memory, score=0.75, source="unit", scope_distance=-2)

        assert result.memory is memory
        assert result.memory.id == "mem-1"
        assert result.score == 0.75
        assert result.source == "unit"
        assert result.scope_distance == -2


class TestScopeAwareRetriever:
    pytestmark = pytest.mark.asyncio

    async def test_retrieve_exact_mode(self) -> None:
        retrieval_engine = MagicMock(spec=RetrievalEngine)
        retrieval_engine.search = AsyncMock(
            return_value=[
                _make_result(_make_memory(MemoryScope.PROJECT, "m1"), 0.2),
                _make_result(_make_memory(MemoryScope.PROJECT, "m2"), 0.8),
                _make_result(_make_memory(MemoryScope.PROJECT, "m3"), 0.5),
            ]
        )

        current_scope = ScopePath.project("user-1", "default", "Project")
        retriever = ScopeAwareRetriever(retrieval_engine)

        results = await retriever.retrieve("query", current_scope, inheritance=InheritanceMode.EXACT)

        assert [result.memory.id for result in results] == ["m2", "m3", "m1"]
        assert all(result.scope_distance == 0 for result in results)

    async def test_retrieve_ancestors_mode(self) -> None:
        retrieval_engine = MagicMock(spec=RetrievalEngine)
        retrieval_engine.search = AsyncMock(
            return_value=[
                _make_result(_make_memory(MemoryScope.MODULE, "module"), 0.7),
                _make_result(_make_memory(MemoryScope.PROJECT, "project"), 0.6),
                _make_result(_make_memory(MemoryScope.WORK, "work"), 0.5),
                _make_result(_make_memory(MemoryScope.PERSONAL, "personal"), 0.4),
            ]
        )

        current_scope = ScopePath.module("user-1", "default", "Project", "default", "Module")
        retriever = ScopeAwareRetriever(retrieval_engine)

        results = await retriever.retrieve("query", current_scope, inheritance=InheritanceMode.ANCESTORS)

        assert [result.memory.id for result in results] == ["module", "project", "work", "personal"]

    async def test_retrieve_filters_out_of_scope(self, monkeypatch: pytest.MonkeyPatch) -> None:
        retrieval_engine = MagicMock(spec=RetrievalEngine)
        retrieval_engine.search = AsyncMock(
            return_value=[_make_result(_make_memory(MemoryScope.WORK, "foreign", user_id="other-user"), 0.9)]
        )

        monkeypatch.setattr(
            ScopePath,
            "from_legacy_scope",
            classmethod(lambda cls, scope_value, user_id: ScopePath.personal("other-user")),
        )

        current_scope = ScopePath.personal("user-1")
        retriever = ScopeAwareRetriever(retrieval_engine)

        results = await retriever.retrieve("query", current_scope, inheritance=InheritanceMode.ANCESTORS)

        assert results == []

    async def test_retrieve_sorts_by_distance_then_score(self) -> None:
        retrieval_engine = MagicMock(spec=RetrievalEngine)
        retrieval_engine.search = AsyncMock(
            return_value=[
                _make_result(_make_memory(MemoryScope.WORK, "current"), 0.4),
                _make_result(_make_memory(MemoryScope.PERSONAL, "personal"), 0.9),
                _make_result(_make_memory(MemoryScope.PROJECT, "project"), 0.6),
                _make_result(_make_memory(MemoryScope.MODULE, "module"), 0.8),
            ]
        )

        current_scope = ScopePath.work("user-1")
        retriever = ScopeAwareRetriever(retrieval_engine)

        results = await retriever.retrieve("query", current_scope, inheritance=InheritanceMode.FULL)

        assert [result.memory.id for result in results] == ["current", "personal", "project", "module"]
        assert [result.scope_distance for result in results] == [0, -1, 1, 2]

    async def test_retrieve_limit(self) -> None:
        retrieval_engine = MagicMock(spec=RetrievalEngine)
        retrieval_engine.search = AsyncMock(
            return_value=[
                _make_result(_make_memory(MemoryScope.MODULE, "m1"), 0.9),
                _make_result(_make_memory(MemoryScope.PROJECT, "m2"), 0.8),
                _make_result(_make_memory(MemoryScope.WORK, "m3"), 0.7),
                _make_result(_make_memory(MemoryScope.PERSONAL, "m4"), 0.6),
                _make_result(_make_memory(MemoryScope.PERSONAL, "m5"), 0.5),
            ]
        )

        current_scope = ScopePath.module("user-1", "default", "Project", "default", "Module")
        retriever = ScopeAwareRetriever(retrieval_engine)

        results = await retriever.retrieve("query", current_scope, limit=3)

        assert len(results) == 3
        assert [result.memory.id for result in results] == ["m1", "m2", "m3"]
        assert retrieval_engine.search.await_args.kwargs["limit"] == 3

    async def test_retrieve_default_mode(self) -> None:
        retrieval_engine = MagicMock(spec=RetrievalEngine)
        retrieval_engine.search = AsyncMock(
            return_value=[
                _make_result(_make_memory(MemoryScope.WORK, "work"), 0.8),
                _make_result(_make_memory(MemoryScope.PERSONAL, "personal"), 0.7),
                _make_result(_make_memory(MemoryScope.MODULE, "module"), 0.9),
            ]
        )

        current_scope = ScopePath.work("user-1")
        retriever = ScopeAwareRetriever(retrieval_engine)

        results = await retriever.retrieve("query", current_scope)

        assert [result.memory.id for result in results] == ["work", "personal"]

    async def test_retrieve_descendants_mode(self) -> None:
        retrieval_engine = MagicMock(spec=RetrievalEngine)
        retrieval_engine.search = AsyncMock(
            return_value=[
                _make_result(_make_memory(MemoryScope.WORK, "parent"), 0.6),
                _make_result(_make_memory(MemoryScope.MODULE, "child"), 0.9),
            ]
        )

        current_scope = ScopePath.project("user-1", "default", "Project")
        retriever = ScopeAwareRetriever(retrieval_engine)

        results = await retriever.retrieve("query", current_scope, inheritance=InheritanceMode.DESCENDANTS)

        assert [result.memory.id for result in results] == ["child"]

    async def test_retrieve_full_mode(self) -> None:
        retrieval_engine = MagicMock(spec=RetrievalEngine)
        retrieval_engine.search = AsyncMock(
            return_value=[
                _make_result(_make_memory(MemoryScope.PROJECT, "current"), 0.5),
                _make_result(_make_memory(MemoryScope.WORK, "ancestor"), 0.8),
                _make_result(_make_memory(MemoryScope.PERSONAL, "root"), 0.7),
                _make_result(_make_memory(MemoryScope.MODULE, "descendant"), 0.9),
            ]
        )

        current_scope = ScopePath.project("user-1", "default", "Project")
        retriever = ScopeAwareRetriever(retrieval_engine)

        results = await retriever.retrieve("query", current_scope, inheritance=InheritanceMode.FULL)

        assert [result.memory.id for result in results] == ["current", "descendant", "ancestor", "root"]
