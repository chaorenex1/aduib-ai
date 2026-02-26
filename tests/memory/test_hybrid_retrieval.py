"""Tests for HybridRetrievalEngine."""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from runtime.memory.types.base import Memory, MemoryType, MemoryMetadata, MemoryScope, MemorySource
from runtime.memory.retrieval.engine import RetrievalResult


def _make_memory(
    memory_id: str = "mem-001",
    content: str = "test content",
    memory_type: MemoryType = MemoryType.SEMANTIC,
    scope: MemoryScope = MemoryScope.PERSONAL,
    embedding: list[float] | None = None,
) -> Memory:
    """Helper to create a Memory instance for testing."""
    return Memory(
        id=memory_id,
        type=memory_type,
        content=content,
        embedding=embedding or [0.1] * 1536,
        metadata=MemoryMetadata(
            user_id="user-1",
            scope=scope,
            source=MemorySource.CHAT,
        ),
    )


@pytest.fixture
def mock_milvus_store():
    """Mock MilvusStore with search capabilities."""
    store = AsyncMock()
    store.get = AsyncMock(return_value=None)
    return store


@pytest.fixture
def mock_graph_layer():
    """Mock KnowledgeGraphLayer."""
    layer = AsyncMock()
    layer.get_related_memories = AsyncMock(return_value=[])
    return layer


@pytest.fixture
def mock_embedder():
    """Mock embedding function."""

    async def embedder(text: str) -> list[float]:
        return [0.1] * 1536

    return embedder


class TestHybridRetrievalEngine:
    """Test HybridRetrievalEngine implementation."""

    def test_inherits_retrieval_engine(self):
        """AC1: HybridRetrievalEngine should implement RetrievalEngine ABC."""
        from runtime.memory.retrieval.hybrid import HybridRetrievalEngine
        from runtime.memory.retrieval.engine import RetrievalEngine

        assert issubclass(HybridRetrievalEngine, RetrievalEngine)

    def test_instantiation(self, mock_milvus_store, mock_embedder):
        """Test that HybridRetrievalEngine can be instantiated."""
        from runtime.memory.retrieval.hybrid import HybridRetrievalEngine

        engine = HybridRetrievalEngine(
            milvus_store=mock_milvus_store,
            embedder=mock_embedder,
        )
        assert engine is not None

    @pytest.mark.asyncio
    async def test_search_returns_retrieval_results(
        self, mock_milvus_store, mock_embedder
    ):
        """AC2: search() should return list of RetrievalResult."""
        from runtime.memory.retrieval.hybrid import HybridRetrievalEngine

        mem = _make_memory("mem-001", "Python programming guide")

        # Mock Milvus search returning results
        mock_milvus_store.vector_search = AsyncMock(
            return_value=[{"id": "mem-001", "distance": 0.95, "metadata_json": None}]
        )
        mock_milvus_store.get = AsyncMock(return_value=mem)

        engine = HybridRetrievalEngine(
            milvus_store=mock_milvus_store,
            embedder=mock_embedder,
        )

        results = await engine.search("Python programming", limit=5)

        assert isinstance(results, list)
        for result in results:
            assert isinstance(result, RetrievalResult)
            assert result.score >= 0.0

    @pytest.mark.asyncio
    async def test_search_with_memory_type_filter(
        self, mock_milvus_store, mock_embedder
    ):
        """search() should filter by memory type."""
        from runtime.memory.retrieval.hybrid import HybridRetrievalEngine

        semantic_mem = _make_memory("mem-s1", "knowledge fact", MemoryType.SEMANTIC)
        episodic_mem = _make_memory("mem-e1", "event log", MemoryType.EPISODIC)

        mock_milvus_store.vector_search = AsyncMock(
            return_value=[
                {"id": "mem-s1", "distance": 0.9},
                {"id": "mem-e1", "distance": 0.8},
            ]
        )
        mock_milvus_store.get = AsyncMock(
            side_effect=lambda mid: semantic_mem if mid == "mem-s1" else episodic_mem
        )

        engine = HybridRetrievalEngine(
            milvus_store=mock_milvus_store,
            embedder=mock_embedder,
        )

        results = await engine.search(
            "knowledge",
            memory_types=[MemoryType.SEMANTIC],
            limit=5,
        )

        memory_types = [r.memory.type for r in results]
        assert all(t == MemoryType.SEMANTIC for t in memory_types)

    @pytest.mark.asyncio
    async def test_search_with_scope_filter(
        self, mock_milvus_store, mock_embedder
    ):
        """search() should filter by scope."""
        from runtime.memory.retrieval.hybrid import HybridRetrievalEngine

        personal_mem = _make_memory("mem-p1", "personal", scope=MemoryScope.PERSONAL)
        work_mem = _make_memory("mem-w1", "work", scope=MemoryScope.WORK)

        mock_milvus_store.vector_search = AsyncMock(
            return_value=[
                {"id": "mem-p1", "distance": 0.9},
                {"id": "mem-w1", "distance": 0.8},
            ]
        )
        mock_milvus_store.get = AsyncMock(
            side_effect=lambda mid: personal_mem if mid == "mem-p1" else work_mem
        )

        engine = HybridRetrievalEngine(
            milvus_store=mock_milvus_store,
            embedder=mock_embedder,
        )

        results = await engine.search(
            "test query",
            scope=MemoryScope.PERSONAL,
            limit=5,
        )

        scopes = [r.memory.metadata.scope for r in results]
        assert all(s == MemoryScope.PERSONAL for s in scopes)

    @pytest.mark.asyncio
    async def test_search_by_embedding(self, mock_milvus_store, mock_embedder):
        """AC6: search_by_embedding() should search by vector similarity."""
        from runtime.memory.retrieval.hybrid import HybridRetrievalEngine

        mem = _make_memory("mem-001")
        mock_milvus_store.vector_search = AsyncMock(
            return_value=[{"id": "mem-001", "distance": 0.92}]
        )
        mock_milvus_store.get = AsyncMock(return_value=mem)

        engine = HybridRetrievalEngine(
            milvus_store=mock_milvus_store,
            embedder=mock_embedder,
        )

        embedding = [0.1] * 1536
        results = await engine.search_by_embedding(embedding, limit=5)

        assert len(results) >= 1
        assert results[0].source == "vector"

    @pytest.mark.asyncio
    async def test_search_by_entities(
        self, mock_milvus_store, mock_graph_layer, mock_embedder
    ):
        """AC6: search_by_entities() should use graph layer."""
        from runtime.memory.retrieval.hybrid import HybridRetrievalEngine

        mem = _make_memory("mem-graph-1", "Python FastAPI guide")

        # Mock graph layer returning memory references
        mock_graph_layer.get_related_memories = AsyncMock(
            return_value=[MagicMock(memory_id="mem-graph-1", score=0.8)]
        )
        mock_milvus_store.get = AsyncMock(return_value=mem)

        engine = HybridRetrievalEngine(
            milvus_store=mock_milvus_store,
            embedder=mock_embedder,
            graph_layer=mock_graph_layer,
        )

        results = await engine.search_by_entities(["entity-python"], limit=5)

        assert len(results) >= 1
        assert results[0].source == "graph"

    @pytest.mark.asyncio
    async def test_search_empty_query(self, mock_milvus_store, mock_embedder):
        """search() with empty query should return empty list."""
        from runtime.memory.retrieval.hybrid import HybridRetrievalEngine

        engine = HybridRetrievalEngine(
            milvus_store=mock_milvus_store,
            embedder=mock_embedder,
        )

        results = await engine.search("", limit=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_respects_min_score(
        self, mock_milvus_store, mock_embedder
    ):
        """search() should filter results below min_score."""
        from runtime.memory.retrieval.hybrid import HybridRetrievalEngine

        high_mem = _make_memory("mem-high", "high score")
        low_mem = _make_memory("mem-low", "low score")

        mock_milvus_store.vector_search = AsyncMock(
            return_value=[
                {"id": "mem-high", "distance": 0.95},
                {"id": "mem-low", "distance": 0.3},
            ]
        )
        mock_milvus_store.get = AsyncMock(
            side_effect=lambda mid: high_mem if mid == "mem-high" else low_mem
        )

        engine = HybridRetrievalEngine(
            milvus_store=mock_milvus_store,
            embedder=mock_embedder,
        )

        results = await engine.search("test", min_score=0.5, limit=10)

        assert all(r.score >= 0.5 for r in results)

    @pytest.mark.asyncio
    async def test_search_respects_limit(
        self, mock_milvus_store, mock_embedder
    ):
        """search() should respect the limit parameter."""
        from runtime.memory.retrieval.hybrid import HybridRetrievalEngine

        mems = [_make_memory(f"mem-{i}", f"content {i}") for i in range(10)]
        mock_milvus_store.vector_search = AsyncMock(
            return_value=[
                {"id": f"mem-{i}", "distance": 0.9 - i * 0.05}
                for i in range(10)
            ]
        )
        mock_milvus_store.get = AsyncMock(
            side_effect=lambda mid: next(
                (m for m in mems if m.id == mid), None
            )
        )

        engine = HybridRetrievalEngine(
            milvus_store=mock_milvus_store,
            embedder=mock_embedder,
        )

        results = await engine.search("test", limit=3)
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_results_sorted_by_score_descending(
        self, mock_milvus_store, mock_embedder
    ):
        """Results should be sorted by score in descending order."""
        from runtime.memory.retrieval.hybrid import HybridRetrievalEngine

        mems = [_make_memory(f"mem-{i}", f"content {i}") for i in range(5)]
        mock_milvus_store.vector_search = AsyncMock(
            return_value=[
                {"id": "mem-2", "distance": 0.5},
                {"id": "mem-0", "distance": 0.9},
                {"id": "mem-1", "distance": 0.7},
            ]
        )
        mock_milvus_store.get = AsyncMock(
            side_effect=lambda mid: next(
                (m for m in mems if m.id == mid), None
            )
        )

        engine = HybridRetrievalEngine(
            milvus_store=mock_milvus_store,
            embedder=mock_embedder,
        )

        results = await engine.search("test", limit=10)

        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)


class TestRRFFusion:
    """Test RRF score fusion."""

    def test_rrf_fusion_basic(self):
        """AC5: RRF fusion should combine scores from multiple sources."""
        from runtime.memory.retrieval.hybrid import rrf_fuse

        vector_results = [("mem-1", 0.9), ("mem-2", 0.8), ("mem-3", 0.7)]
        graph_results = [("mem-2", 0.85), ("mem-4", 0.6)]

        fused = rrf_fuse(
            {"vector": vector_results, "graph": graph_results}
        )

        # mem-2 appears in both sources, should rank higher
        fused_dict = {mid: score for mid, score in fused}
        assert "mem-2" in fused_dict
        assert "mem-1" in fused_dict

        # mem-2 should have higher fused score than mem-3 (only in vector)
        assert fused_dict["mem-2"] > fused_dict.get("mem-3", 0)

    def test_rrf_fusion_empty_input(self):
        """RRF fusion with empty input should return empty list."""
        from runtime.memory.retrieval.hybrid import rrf_fuse

        fused = rrf_fuse({})
        assert fused == []

    def test_rrf_fusion_single_source(self):
        """RRF fusion with single source should preserve order."""
        from runtime.memory.retrieval.hybrid import rrf_fuse

        vector_results = [("mem-1", 0.9), ("mem-2", 0.8)]
        fused = rrf_fuse({"vector": vector_results})

        ids = [mid for mid, _ in fused]
        assert ids[0] == "mem-1"
        assert ids[1] == "mem-2"

    def test_rrf_multi_hit_bonus(self):
        """Items found in multiple sources should get bonus score."""
        from runtime.memory.retrieval.hybrid import rrf_fuse

        # mem-1 appears in all 3 sources
        results = {
            "vector": [("mem-1", 0.9), ("mem-2", 0.8)],
            "graph": [("mem-1", 0.7), ("mem-3", 0.6)],
            "keyword": [("mem-1", 0.5), ("mem-4", 0.4)],
        }
        fused = rrf_fuse(results)

        fused_dict = {mid: score for mid, score in fused}
        # mem-1 in 3 sources should rank first
        assert fused[0][0] == "mem-1"
