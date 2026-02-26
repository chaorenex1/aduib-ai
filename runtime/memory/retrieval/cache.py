"""Multi-level retrieval cache for accelerating memory retrieval."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)


class RetrievalCache:
    """Multi-level retrieval cache backed by Redis.

    L1: Query Cache - caches search result metadata for identical queries (TTL: 5min)
    L2: Embedding Cache - caches embedding vectors by text hash (TTL: 1h)
    L3: Hot Memory Cache - caches frequently accessed memory data (TTL: 30min)
    """

    def __init__(
        self,
        redis_client: Any,
        key_prefix: str = "rcache",
        query_ttl: int = 300,
        embedding_ttl: int = 3600,
        memory_ttl: int = 1800,
    ) -> None:
        self._redis = redis_client
        self._prefix = key_prefix
        self._query_ttl = query_ttl
        self._embedding_ttl = embedding_ttl
        self._memory_ttl = memory_ttl

    def _query_cache_key(self, query_key: str) -> str:
        return f"{self._prefix}:query:{query_key}"

    def _embedding_cache_key(self, text: str) -> str:
        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
        return f"{self._prefix}:emb:{text_hash}"

    def _memory_cache_key(self, memory_id: str) -> str:
        return f"{self._prefix}:mem:{memory_id}"

    # ------------------------------------------------------------------
    # Query Key Builder
    # ------------------------------------------------------------------

    @staticmethod
    def build_query_key(
        query: str,
        filters: Optional[dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """Build a deterministic hash key for query cache.

        Same inputs always produce the same key.
        """
        parts = [query]
        if filters:
            parts.append(json.dumps(filters, sort_keys=True, ensure_ascii=False))
        if user_id:
            parts.append(user_id)
        combined = "|".join(parts)
        return hashlib.md5(combined.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # L1: Query Cache
    # ------------------------------------------------------------------

    async def get_query_results(self, query_key: str) -> Optional[list[dict]]:
        """Get cached query results by key.

        Returns:
            List of result dicts, or None on cache miss.
        """
        cache_key = self._query_cache_key(query_key)

        def _get() -> Optional[str]:
            return self._redis.get(cache_key)

        raw = await asyncio.to_thread(_get)
        if raw is None:
            return None

        decoded = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        return json.loads(decoded)

    async def set_query_results(self, query_key: str, results: list[dict]) -> None:
        """Cache query results with TTL."""
        cache_key = self._query_cache_key(query_key)
        payload = json.dumps(results, ensure_ascii=False, default=str)

        def _set() -> None:
            self._redis.setex(cache_key, self._query_ttl, payload)

        await asyncio.to_thread(_set)

    async def invalidate_query(self, query_key: str) -> bool:
        """Invalidate a specific query cache entry."""
        cache_key = self._query_cache_key(query_key)

        def _delete() -> bool:
            return bool(self._redis.delete(cache_key))

        return await asyncio.to_thread(_delete)

    # ------------------------------------------------------------------
    # L2: Embedding Cache
    # ------------------------------------------------------------------

    async def get_embedding(self, text: str) -> Optional[list[float]]:
        """Get cached embedding for text.

        Returns:
            Embedding vector, or None on cache miss.
        """
        cache_key = self._embedding_cache_key(text)

        def _get() -> Optional[str]:
            return self._redis.get(cache_key)

        raw = await asyncio.to_thread(_get)
        if raw is None:
            return None

        decoded = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        return json.loads(decoded)

    async def set_embedding(self, text: str, embedding: list[float]) -> None:
        """Cache embedding vector with TTL."""
        cache_key = self._embedding_cache_key(text)
        payload = json.dumps(embedding)

        def _set() -> None:
            self._redis.setex(cache_key, self._embedding_ttl, payload)

        await asyncio.to_thread(_set)

    async def get_or_compute_embedding(
        self,
        text: str,
        embedder: Callable[[str], Coroutine[Any, Any, list[float]]],
    ) -> list[float]:
        """Get cached embedding or compute and cache it.

        Args:
            text: Text to embed.
            embedder: Async callable that computes the embedding.

        Returns:
            Embedding vector.
        """
        cached = await self.get_embedding(text)
        if cached is not None:
            return cached

        embedding = await embedder(text)
        await self.set_embedding(text, embedding)
        return embedding

    # ------------------------------------------------------------------
    # L3: Hot Memory Cache
    # ------------------------------------------------------------------

    async def get_memory(self, memory_id: str) -> Optional[dict]:
        """Get cached memory data by ID.

        Returns:
            Memory data dict, or None on cache miss.
        """
        cache_key = self._memory_cache_key(memory_id)

        def _get() -> Optional[str]:
            return self._redis.get(cache_key)

        raw = await asyncio.to_thread(_get)
        if raw is None:
            return None

        decoded = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        return json.loads(decoded)

    async def set_memory(self, memory_id: str, data: dict) -> None:
        """Cache memory data with TTL."""
        cache_key = self._memory_cache_key(memory_id)
        payload = json.dumps(data, ensure_ascii=False, default=str)

        def _set() -> None:
            self._redis.setex(cache_key, self._memory_ttl, payload)

        await asyncio.to_thread(_set)

    async def invalidate_memory(self, memory_id: str) -> bool:
        """Invalidate a specific memory cache entry."""
        cache_key = self._memory_cache_key(memory_id)

        def _delete() -> bool:
            return bool(self._redis.delete(cache_key))

        return await asyncio.to_thread(_delete)
