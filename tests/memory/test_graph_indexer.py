"""Tests for GraphIndexer - graph index precomputation."""

import asyncio
import hashlib

import pytest
from unittest.mock import AsyncMock, MagicMock

from runtime.memory.types.base import (
    Memory, MemoryType, MemoryMetadata, MemoryScope, MemorySource,
    Entity, EntityType,
)


def _make_entity(name: str, entity_type: EntityType = EntityType.CONCEPT) -> Entity:
    """Helper to create an Entity with deterministic ID."""
    entity_id = f"entity_{hashlib.md5(name.encode()).hexdigest()[:8]}"
    return Entity(id=entity_id, name=name, type=entity_type, properties={})


def _make_memory(
    memory_id: str = "mem-001",
    content: str = "test content",
    entities: list[Entity] | None = None,
) -> Memory:
    """Helper to create a Memory instance for testing."""
    return Memory(
        id=memory_id,
        type=MemoryType.SEMANTIC,
        content=content,
        metadata=MemoryMetadata(
            user_id="user-1",
            scope=MemoryScope.PERSONAL,
            source=MemorySource.CHAT,
        ),
        entities=entities or [],
    )


class FakeRedis:
    """In-memory Redis mock supporting sets and sorted sets."""

    def __init__(self):
        self._sets: dict[str, set] = {}
        self._zsets: dict[str, dict[str, float]] = {}
        self._ttls: dict[str, int] = {}

    def pipeline(self):
        return FakePipeline(self)

    def sadd(self, key: str, *members) -> int:
        if key not in self._sets:
            self._sets[key] = set()
        added = 0
        for m in members:
            if m not in self._sets[key]:
                self._sets[key].add(m)
                added += 1
        return added

    def srem(self, key: str, *members) -> int:
        if key not in self._sets:
            return 0
        removed = 0
        for m in members:
            if m in self._sets[key]:
                self._sets[key].discard(m)
                removed += 1
        return removed

    def smembers(self, key: str) -> set:
        return self._sets.get(key, set()).copy()

    def zadd(self, key: str, mapping: dict) -> int:
        if key not in self._zsets:
            self._zsets[key] = {}
        self._zsets[key].update(mapping)
        return len(mapping)

    def zrevrange(self, key: str, start: int, stop: int, withscores: bool = False):
        if key not in self._zsets:
            return []
        items = sorted(self._zsets[key].items(), key=lambda x: -x[1])
        sliced = items[start:stop + 1] if stop >= 0 else items[start:]
        if withscores:
            return sliced
        return [item[0] for item in sliced]

    def expire(self, key: str, seconds: int) -> bool:
        self._ttls[key] = seconds
        return True

    def delete(self, *keys) -> int:
        count = 0
        for key in keys:
            if key in self._sets:
                del self._sets[key]
                count += 1
            if key in self._zsets:
                del self._zsets[key]
                count += 1
            self._ttls.pop(key, None)
        return count


class FakePipeline:
    """Buffered pipeline for FakeRedis."""

    def __init__(self, redis: FakeRedis):
        self._redis = redis
        self._commands: list[tuple] = []

    def sadd(self, key: str, *members):
        self._commands.append(("sadd", key, members))
        return self

    def srem(self, key: str, *members):
        self._commands.append(("srem", key, members))
        return self

    def delete(self, *keys):
        self._commands.append(("delete", keys))
        return self

    def zadd(self, key: str, mapping: dict):
        self._commands.append(("zadd", key, mapping))
        return self

    def expire(self, key: str, seconds: int):
        self._commands.append(("expire", key, seconds))
        return self

    def execute(self) -> list:
        results = []
        for cmd in self._commands:
            op = cmd[0]
            if op == "sadd":
                results.append(self._redis.sadd(cmd[1], *cmd[2]))
            elif op == "srem":
                results.append(self._redis.srem(cmd[1], *cmd[2]))
            elif op == "delete":
                results.append(self._redis.delete(*cmd[1]))
            elif op == "zadd":
                results.append(self._redis.zadd(cmd[1], cmd[2]))
            elif op == "expire":
                results.append(self._redis.expire(cmd[1], cmd[2]))
        self._commands = []
        return results


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
def mock_graph_store():
    store = AsyncMock()
    store._query = AsyncMock(return_value=[])
    return store


class TestGraphIndexerEntityIndex:
    """Test entity inverted index operations."""

    @pytest.mark.asyncio
    async def test_build_entity_index(self, fake_redis):
        """AC1+AC2: Build entity inverted index and reverse mapping."""
        from runtime.memory.retrieval.graph_indexer import GraphIndexer

        entities = [_make_entity("Python"), _make_entity("FastAPI")]
        memory = _make_memory("mem-001", entities=entities)

        indexer = GraphIndexer(redis_client=fake_redis)
        count = await indexer.build_entity_index(memory)

        assert count == 2
        # Entity -> memory mapping
        assert "mem-001" in fake_redis.smembers("graphidx:entity:python:memories")
        assert "mem-001" in fake_redis.smembers("graphidx:entity:fastapi:memories")
        # Memory -> entity reverse mapping
        entities_set = fake_redis.smembers("graphidx:memory:mem-001:entities")
        assert "python" in entities_set
        assert "fastapi" in entities_set

    @pytest.mark.asyncio
    async def test_build_entity_index_empty_entities(self, fake_redis):
        """build_entity_index with no entities should return 0."""
        from runtime.memory.retrieval.graph_indexer import GraphIndexer

        memory = _make_memory("mem-001", entities=[])
        indexer = GraphIndexer(redis_client=fake_redis)
        count = await indexer.build_entity_index(memory)

        assert count == 0

    @pytest.mark.asyncio
    async def test_build_entity_index_multiple_memories(self, fake_redis):
        """Multiple memories sharing entities should all be indexed."""
        from runtime.memory.retrieval.graph_indexer import GraphIndexer

        mem1 = _make_memory("mem-001", entities=[_make_entity("Python")])
        mem2 = _make_memory("mem-002", entities=[_make_entity("Python"), _make_entity("Milvus")])

        indexer = GraphIndexer(redis_client=fake_redis)
        await indexer.build_entity_index(mem1)
        await indexer.build_entity_index(mem2)

        python_mems = fake_redis.smembers("graphidx:entity:python:memories")
        assert "mem-001" in python_mems
        assert "mem-002" in python_mems
        assert "mem-002" in fake_redis.smembers("graphidx:entity:milvus:memories")

    @pytest.mark.asyncio
    async def test_remove_entity_index(self, fake_redis):
        """remove_entity_index should clean up all references."""
        from runtime.memory.retrieval.graph_indexer import GraphIndexer

        entities = [_make_entity("Python"), _make_entity("FastAPI")]
        memory = _make_memory("mem-001", entities=entities)

        indexer = GraphIndexer(redis_client=fake_redis)
        await indexer.build_entity_index(memory)

        removed = await indexer.remove_entity_index("mem-001")
        assert removed == 2
        assert "mem-001" not in fake_redis.smembers("graphidx:entity:python:memories")
        assert "mem-001" not in fake_redis.smembers("graphidx:entity:fastapi:memories")
        assert fake_redis.smembers("graphidx:memory:mem-001:entities") == set()

    @pytest.mark.asyncio
    async def test_remove_entity_index_nonexistent(self, fake_redis):
        """remove_entity_index for unknown memory should return 0."""
        from runtime.memory.retrieval.graph_indexer import GraphIndexer

        indexer = GraphIndexer(redis_client=fake_redis)
        removed = await indexer.remove_entity_index("mem-unknown")
        assert removed == 0

    @pytest.mark.asyncio
    async def test_lookup_by_entity(self, fake_redis):
        """AC5: lookup_by_entity should find all associated memories."""
        from runtime.memory.retrieval.graph_indexer import GraphIndexer

        mem1 = _make_memory("mem-001", entities=[_make_entity("Python")])
        mem2 = _make_memory("mem-002", entities=[_make_entity("Python")])

        indexer = GraphIndexer(redis_client=fake_redis)
        await indexer.build_entity_index(mem1)
        await indexer.build_entity_index(mem2)

        result = await indexer.lookup_by_entity("Python")
        assert set(result) == {"mem-001", "mem-002"}

    @pytest.mark.asyncio
    async def test_lookup_by_entity_case_insensitive(self, fake_redis):
        """lookup_by_entity should be case-insensitive."""
        from runtime.memory.retrieval.graph_indexer import GraphIndexer

        memory = _make_memory("mem-001", entities=[_make_entity("Python")])
        indexer = GraphIndexer(redis_client=fake_redis)
        await indexer.build_entity_index(memory)

        result = await indexer.lookup_by_entity("PYTHON")
        assert "mem-001" in result


class TestGraphIndexerNeighborCache:
    """Test neighbor cache operations."""

    @pytest.mark.asyncio
    async def test_build_neighbor_cache(self, fake_redis, mock_graph_store):
        """AC3: Build neighbor cache with TTL."""
        from runtime.memory.retrieval.graph_indexer import GraphIndexer

        mock_graph_store._query = AsyncMock(return_value=[
            {"neighbor_id": "mem-002", "score": 0.95},
            {"neighbor_id": "mem-003", "score": 0.82},
        ])

        indexer = GraphIndexer(redis_client=fake_redis, graph_store=mock_graph_store)
        count = await indexer.build_neighbor_cache("mem-001")

        assert count == 2
        cached = fake_redis.zrevrange("graphidx:neighbors:mem-001", 0, -1, withscores=True)
        assert len(cached) == 2
        assert "graphidx:neighbors:mem-001" in fake_redis._ttls

    @pytest.mark.asyncio
    async def test_build_neighbor_cache_no_graph(self, fake_redis):
        """build_neighbor_cache without graph_store should return 0."""
        from runtime.memory.retrieval.graph_indexer import GraphIndexer

        indexer = GraphIndexer(redis_client=fake_redis, graph_store=None)
        count = await indexer.build_neighbor_cache("mem-001")
        assert count == 0

    @pytest.mark.asyncio
    async def test_build_neighbor_cache_empty_results(self, fake_redis, mock_graph_store):
        """build_neighbor_cache with empty graph results should return 0."""
        from runtime.memory.retrieval.graph_indexer import GraphIndexer

        mock_graph_store._query = AsyncMock(return_value=[])
        indexer = GraphIndexer(redis_client=fake_redis, graph_store=mock_graph_store)
        count = await indexer.build_neighbor_cache("mem-001")
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_neighbors_fast_cached(self, fake_redis):
        """AC4: Fast lookup should return cached neighbors sorted by score."""
        from runtime.memory.retrieval.graph_indexer import GraphIndexer

        fake_redis.zadd("graphidx:neighbors:mem-001", {
            "mem-002": 0.95,
            "mem-003": 0.82,
            "mem-004": 0.65,
        })

        indexer = GraphIndexer(redis_client=fake_redis)
        result = await indexer.get_neighbors_fast(["mem-001"], top_k=10)

        assert len(result) == 3
        assert result[0] == ("mem-002", 0.95)
        assert result[1] == ("mem-003", 0.82)
        assert result[2] == ("mem-004", 0.65)

    @pytest.mark.asyncio
    async def test_get_neighbors_excludes_input_ids(self, fake_redis):
        """get_neighbors_fast should exclude input memory IDs from results."""
        from runtime.memory.retrieval.graph_indexer import GraphIndexer

        fake_redis.zadd("graphidx:neighbors:mem-001", {
            "mem-002": 0.95,
            "mem-003": 0.82,
        })

        indexer = GraphIndexer(redis_client=fake_redis)
        result = await indexer.get_neighbors_fast(["mem-001", "mem-002"], top_k=10)

        ids = [r[0] for r in result]
        assert "mem-002" not in ids
        assert "mem-003" in ids

    @pytest.mark.asyncio
    async def test_get_neighbors_merges_multiple_sources(self, fake_redis):
        """get_neighbors_fast should merge from multiple caches using max score."""
        from runtime.memory.retrieval.graph_indexer import GraphIndexer

        fake_redis.zadd("graphidx:neighbors:mem-001", {
            "mem-003": 0.9,
            "mem-004": 0.7,
        })
        fake_redis.zadd("graphidx:neighbors:mem-002", {
            "mem-003": 0.8,
            "mem-005": 0.6,
        })

        indexer = GraphIndexer(redis_client=fake_redis)
        result = await indexer.get_neighbors_fast(["mem-001", "mem-002"], top_k=10)

        result_dict = dict(result)
        assert result_dict["mem-003"] == 0.9  # max of 0.9 and 0.8
        assert "mem-004" in result_dict
        assert "mem-005" in result_dict

    @pytest.mark.asyncio
    async def test_invalidate_neighbor_cache(self, fake_redis):
        """invalidate_neighbor_cache should delete the cache entry."""
        from runtime.memory.retrieval.graph_indexer import GraphIndexer

        fake_redis.zadd("graphidx:neighbors:mem-001", {"mem-002": 0.95})

        indexer = GraphIndexer(redis_client=fake_redis)
        result = await indexer.invalidate_neighbor_cache("mem-001")

        assert result is True
        assert fake_redis.zrevrange("graphidx:neighbors:mem-001", 0, -1) == []


class TestGraphIndexerBatch:
    """Test batch operations."""

    @pytest.mark.asyncio
    async def test_rebuild_all_entity_indexes(self, fake_redis):
        """AC6: Batch rebuild should process all memories."""
        from runtime.memory.retrieval.graph_indexer import GraphIndexer

        memories = [
            _make_memory("mem-001", entities=[_make_entity("Python")]),
            _make_memory("mem-002", entities=[_make_entity("Python"), _make_entity("FastAPI")]),
            _make_memory("mem-003", entities=[]),
        ]

        indexer = GraphIndexer(redis_client=fake_redis)
        total = await indexer.rebuild_all_entity_indexes(memories)

        assert total == 3  # 1 + 2 + 0
        python_mems = fake_redis.smembers("graphidx:entity:python:memories")
        assert "mem-001" in python_mems
        assert "mem-002" in python_mems
