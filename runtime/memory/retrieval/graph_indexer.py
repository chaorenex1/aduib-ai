"""Graph index precomputation for accelerating graph-based memory retrieval."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from runtime.memory.types.base import Memory

logger = logging.getLogger(__name__)


class GraphIndexer:
    """Pre-computes graph indexes for fast graph-based memory retrieval.

    Maintains two Redis-backed index structures:
    1. Entity inverted index: entity_name -> set of memory_ids (O(1) lookup)
    2. Neighbor cache: memory_id -> sorted set of (neighbor_id, score)
    """

    def __init__(
        self,
        redis_client: Any,
        graph_store: Any | None = None,
        key_prefix: str = "graphidx",
    ) -> None:
        self._redis = redis_client
        self._graph = graph_store
        self._prefix = key_prefix

    def _entity_key(self, entity_name: str) -> str:
        return f"{self._prefix}:entity:{entity_name}:memories"

    def _memory_entities_key(self, memory_id: str) -> str:
        return f"{self._prefix}:memory:{memory_id}:entities"

    def _neighbors_key(self, memory_id: str) -> str:
        return f"{self._prefix}:neighbors:{memory_id}"

    @staticmethod
    def _sanitize(value: str) -> str:
        return str(value).replace("'", "\\'").replace('"', '\\"')

    # ------------------------------------------------------------------
    # Entity Inverted Index
    # ------------------------------------------------------------------

    async def build_entity_index(self, memory: Memory) -> int:
        """Build entity inverted index entries for a memory.

        For each entity in the memory, adds the memory_id to the entity's
        inverted index set and records the entity in the memory's reverse map.

        Returns:
            Number of entities indexed.
        """
        entities = memory.entities
        if not entities:
            return 0

        entity_names = [e.name.lower() for e in entities]

        def _build() -> int:
            pipe = self._redis.pipeline()
            for name in entity_names:
                pipe.sadd(self._entity_key(name), memory.id)
                pipe.sadd(self._memory_entities_key(memory.id), name)
            pipe.execute()
            return len(entity_names)

        return await asyncio.to_thread(_build)

    async def remove_entity_index(self, memory_id: str) -> int:
        """Remove all entity index entries for a memory.

        Looks up which entities are associated with this memory,
        removes the memory from each entity's inverted index,
        then cleans up the reverse mapping.

        Returns:
            Number of entity references removed.
        """
        def _remove() -> int:
            entities_key = self._memory_entities_key(memory_id)
            entity_names = self._redis.smembers(entities_key)
            if not entity_names:
                return 0

            count = len(entity_names)
            pipe = self._redis.pipeline()
            for name in entity_names:
                decoded = name.decode("utf-8") if isinstance(name, bytes) else name
                pipe.srem(self._entity_key(decoded), memory_id)
            pipe.delete(entities_key)
            pipe.execute()
            return count

        return await asyncio.to_thread(_remove)

    async def lookup_by_entity(self, entity_name: str, limit: int = 50) -> list[str]:
        """Look up memory IDs by entity name (O(1) via inverted index).

        Returns:
            List of memory IDs associated with the entity.
        """
        key = self._entity_key(entity_name.lower())

        def _fetch() -> list[str]:
            members = self._redis.smembers(key)
            result = []
            for m in members:
                decoded = m.decode("utf-8") if isinstance(m, bytes) else m
                result.append(decoded)
                if len(result) >= limit:
                    break
            return result

        return await asyncio.to_thread(_fetch)

    # ------------------------------------------------------------------
    # Neighbor Cache
    # ------------------------------------------------------------------

    async def build_neighbor_cache(
        self, memory_id: str, ttl: int = 86400
    ) -> int:
        """Build neighbor cache via 1-2 hop graph traversal.

        Queries the graph store for memories connected within 2 hops,
        scores them by hop distance and path count, and caches in
        a Redis sorted set with TTL.

        Args:
            memory_id: The memory to build neighbors for.
            ttl: Cache TTL in seconds (default 24h).

        Returns:
            Number of neighbors cached.
        """
        if self._graph is None:
            return 0

        safe_id = self._sanitize(memory_id)
        cypher = (
            f"MATCH (m:Memory {{id: '{safe_id}'}})"
            f"-[r*1..2]-(neighbor:Memory) "
            f"WHERE neighbor.id <> '{safe_id}' "
            f"WITH neighbor, "
            f"min(length(r)) as hops, "
            f"count(*) as paths "
            f"RETURN neighbor.id as neighbor_id, "
            f"(1.0 / hops) * paths * 0.1 as score "
            f"ORDER BY score DESC LIMIT 50"
        )

        try:
            neighbors = await self._graph._query(cypher)
        except Exception as e:
            logger.warning("Graph neighbor query failed for %s: %s", memory_id, e)
            return 0

        if not neighbors:
            return 0

        cache_key = self._neighbors_key(memory_id)

        def _cache() -> int:
            mapping = {n["neighbor_id"]: n["score"] for n in neighbors}
            self._redis.zadd(cache_key, mapping)
            self._redis.expire(cache_key, ttl)
            return len(mapping)

        return await asyncio.to_thread(_cache)

    async def invalidate_neighbor_cache(self, memory_id: str) -> bool:
        """Invalidate neighbor cache for a memory.

        Returns:
            True if the cache was deleted.
        """
        cache_key = self._neighbors_key(memory_id)

        def _delete() -> bool:
            return bool(self._redis.delete(cache_key))

        return await asyncio.to_thread(_delete)

    async def get_neighbors_fast(
        self,
        memory_ids: list[str],
        top_k: int = 20,
    ) -> list[tuple[str, float]]:
        """Fast cached neighbor lookup across multiple memories.

        For each memory_id, retrieves cached neighbors from Redis.
        Merges results using max-score deduplication, excludes input
        memory IDs from results.

        If a cache miss occurs, triggers an async background rebuild.

        Returns:
            Sorted list of (neighbor_id, score) tuples, descending by score.
        """
        input_set = set(memory_ids)
        all_neighbors: dict[str, float] = {}

        for memory_id in memory_ids:
            cache_key = self._neighbors_key(memory_id)

            def _fetch(key: str = cache_key) -> list[tuple[str, float]]:
                return self._redis.zrevrange(key, 0, top_k - 1, withscores=True)

            cached = await asyncio.to_thread(_fetch)

            if cached:
                for item in cached:
                    neighbor_id = item[0]
                    if isinstance(neighbor_id, bytes):
                        neighbor_id = neighbor_id.decode("utf-8")
                    score = item[1]
                    if neighbor_id not in input_set:
                        current = all_neighbors.get(neighbor_id, 0)
                        all_neighbors[neighbor_id] = max(current, score)
            else:
                # Trigger async cache rebuild (fire-and-forget)
                try:
                    asyncio.create_task(self.build_neighbor_cache(memory_id))
                except RuntimeError:
                    pass  # No running event loop

        sorted_neighbors = sorted(all_neighbors.items(), key=lambda x: -x[1])
        return sorted_neighbors[:top_k]

    # ------------------------------------------------------------------
    # Batch Operations
    # ------------------------------------------------------------------

    async def rebuild_all_entity_indexes(self, memories: list[Memory]) -> int:
        """Batch rebuild entity indexes for a list of memories.

        Returns:
            Total number of entity references indexed.
        """
        total = 0
        for memory in memories:
            count = await self.build_entity_index(memory)
            total += count
        return total
