"""Tests for RetrievalCache - multi-level retrieval cache."""

import json
import pytest
from unittest.mock import AsyncMock


class FakeRedis:
    """In-memory Redis mock supporting string get/set/setex/delete."""

    def __init__(self):
        self._data: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    def get(self, key: str):
        return self._data.get(key)

    def set(self, key: str, value: str, ex: int | None = None):
        self._data[key] = value
        if ex is not None:
            self._ttls[key] = ex

    def setex(self, key: str, ttl: int, value: str):
        self._data[key] = value
        self._ttls[key] = ttl

    def delete(self, *keys) -> int:
        count = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                count += 1
            self._ttls.pop(key, None)
        return count

    def keys(self, pattern: str = "*") -> list[str]:
        if pattern == "*":
            return list(self._data.keys())
        prefix = pattern.rstrip("*")
        return [k for k in self._data if k.startswith(prefix)]


@pytest.fixture
def fake_redis():
    return FakeRedis()


class TestQueryCache:
    """Test L1 Query Cache operations."""

    @pytest.mark.asyncio
    async def test_query_cache_miss_returns_none(self, fake_redis):
        """AC1: Cache miss should return None."""
        from runtime.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache(redis_client=fake_redis)
        key = cache.build_query_key("test query")
        result = await cache.get_query_results(key)

        assert result is None

    @pytest.mark.asyncio
    async def test_query_cache_set_and_get(self, fake_redis):
        """AC1: Set and get query results."""
        from runtime.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache(redis_client=fake_redis)
        key = cache.build_query_key("how to use Python")

        results = [
            {"memory_id": "mem-001", "score": 0.95, "source": "vector"},
            {"memory_id": "mem-002", "score": 0.82, "source": "graph"},
        ]
        await cache.set_query_results(key, results)

        cached = await cache.get_query_results(key)
        assert cached is not None
        assert len(cached) == 2
        assert cached[0]["memory_id"] == "mem-001"

    @pytest.mark.asyncio
    async def test_query_cache_invalidate(self, fake_redis):
        """AC6: Invalidate query cache entry."""
        from runtime.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache(redis_client=fake_redis)
        key = cache.build_query_key("test query")
        await cache.set_query_results(key, [{"memory_id": "m1", "score": 0.9}])

        deleted = await cache.invalidate_query(key)
        assert deleted is True

        result = await cache.get_query_results(key)
        assert result is None

    @pytest.mark.asyncio
    async def test_query_cache_uses_configured_ttl(self, fake_redis):
        """AC1: Query cache should use configured TTL."""
        from runtime.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache(redis_client=fake_redis, query_ttl=120)
        key = cache.build_query_key("test")
        await cache.set_query_results(key, [])

        cache_key = f"rcache:query:{key}"
        assert fake_redis._ttls.get(cache_key) == 120


class TestBuildQueryKey:
    """Test query key generation."""

    def test_build_query_key_deterministic(self):
        """AC5: Same inputs should produce same key."""
        from runtime.memory.retrieval.cache import RetrievalCache

        key1 = RetrievalCache.build_query_key("test query")
        key2 = RetrievalCache.build_query_key("test query")
        assert key1 == key2

    def test_build_query_key_different_queries(self):
        """AC5: Different queries should produce different keys."""
        from runtime.memory.retrieval.cache import RetrievalCache

        key1 = RetrievalCache.build_query_key("query A")
        key2 = RetrievalCache.build_query_key("query B")
        assert key1 != key2

    def test_build_query_key_with_filters(self):
        """AC5: Filters should affect the key."""
        from runtime.memory.retrieval.cache import RetrievalCache

        key_no_filter = RetrievalCache.build_query_key("test")
        key_with_filter = RetrievalCache.build_query_key(
            "test", filters={"scope": "personal"}
        )
        assert key_no_filter != key_with_filter

    def test_build_query_key_with_user_id(self):
        """AC5: User ID should affect the key."""
        from runtime.memory.retrieval.cache import RetrievalCache

        key1 = RetrievalCache.build_query_key("test", user_id="user-1")
        key2 = RetrievalCache.build_query_key("test", user_id="user-2")
        assert key1 != key2


class TestEmbeddingCache:
    """Test L2 Embedding Cache operations."""

    @pytest.mark.asyncio
    async def test_embedding_cache_miss_returns_none(self, fake_redis):
        """AC2: Cache miss should return None."""
        from runtime.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache(redis_client=fake_redis)
        result = await cache.get_embedding("some text")
        assert result is None

    @pytest.mark.asyncio
    async def test_embedding_cache_set_and_get(self, fake_redis):
        """AC2: Set and get embedding."""
        from runtime.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache(redis_client=fake_redis)
        embedding = [0.1, 0.2, 0.3, 0.4]
        await cache.set_embedding("hello world", embedding)

        cached = await cache.get_embedding("hello world")
        assert cached == [0.1, 0.2, 0.3, 0.4]

    @pytest.mark.asyncio
    async def test_get_or_compute_embedding_cache_miss(self, fake_redis):
        """AC4: Cache miss should compute and cache."""
        from runtime.memory.retrieval.cache import RetrievalCache

        expected = [0.5] * 1536

        async def mock_embedder(text: str) -> list[float]:
            return expected

        cache = RetrievalCache(redis_client=fake_redis)
        result = await cache.get_or_compute_embedding("test text", mock_embedder)

        assert result == expected
        # Verify it was cached
        cached = await cache.get_embedding("test text")
        assert cached == expected

    @pytest.mark.asyncio
    async def test_get_or_compute_embedding_cache_hit(self, fake_redis):
        """AC4: Cache hit should not call embedder."""
        from runtime.memory.retrieval.cache import RetrievalCache

        pre_cached = [0.1] * 1536
        cache = RetrievalCache(redis_client=fake_redis)
        await cache.set_embedding("cached text", pre_cached)

        embedder = AsyncMock(return_value=[0.9] * 1536)
        result = await cache.get_or_compute_embedding("cached text", embedder)

        assert result == pre_cached
        embedder.assert_not_called()

    @pytest.mark.asyncio
    async def test_embedding_cache_uses_configured_ttl(self, fake_redis):
        """AC2: Embedding cache should use configured TTL."""
        from runtime.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache(redis_client=fake_redis, embedding_ttl=7200)
        await cache.set_embedding("test", [0.1])

        matching = [k for k in fake_redis._ttls if "emb:" in k]
        assert len(matching) == 1
        assert fake_redis._ttls[matching[0]] == 7200


class TestHotMemoryCache:
    """Test L3 Hot Memory Cache operations."""

    @pytest.mark.asyncio
    async def test_memory_cache_miss_returns_none(self, fake_redis):
        """AC3: Cache miss should return None."""
        from runtime.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache(redis_client=fake_redis)
        result = await cache.get_memory("mem-unknown")
        assert result is None

    @pytest.mark.asyncio
    async def test_memory_cache_set_and_get(self, fake_redis):
        """AC3: Set and get memory data."""
        from runtime.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache(redis_client=fake_redis)
        data = {"id": "mem-001", "content": "Python guide", "type": "semantic"}

        await cache.set_memory("mem-001", data)
        cached = await cache.get_memory("mem-001")

        assert cached is not None
        assert cached["id"] == "mem-001"
        assert cached["content"] == "Python guide"

    @pytest.mark.asyncio
    async def test_memory_cache_invalidate(self, fake_redis):
        """AC6: Invalidate memory cache entry."""
        from runtime.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache(redis_client=fake_redis)
        await cache.set_memory("mem-001", {"id": "mem-001"})

        deleted = await cache.invalidate_memory("mem-001")
        assert deleted is True

        result = await cache.get_memory("mem-001")
        assert result is None

    @pytest.mark.asyncio
    async def test_memory_cache_uses_configured_ttl(self, fake_redis):
        """AC3: Memory cache should use configured TTL."""
        from runtime.memory.retrieval.cache import RetrievalCache

        cache = RetrievalCache(redis_client=fake_redis, memory_ttl=600)
        await cache.set_memory("mem-001", {"id": "mem-001"})

        cache_key = "rcache:mem:mem-001"
        assert fake_redis._ttls.get(cache_key) == 600
