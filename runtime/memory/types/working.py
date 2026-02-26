from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from runtime.memory.types.base import Memory, MemoryType

logger = logging.getLogger(__name__)


class WorkingMemory:
    """Short-lived working memory stored in Redis with TTL-based eviction."""

    def __init__(self, redis_client: Any, session_id: str, ttl_seconds: int = 3600, max_entries: int = 50) -> None:
        self.redis = redis_client
        self.session_id = session_id
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.key = f"memory:working:{session_id}"

    def _index_key(self, memory_id: str) -> str:
        return f"{self.key}:{memory_id}"

    @staticmethod
    def _decode(value: Any) -> Any:
        if isinstance(value, (bytes, bytearray)):
            return value.decode("utf-8")
        return value

    @staticmethod
    def _loads(value: Any) -> dict[str, Any]:
        decoded = WorkingMemory._decode(value)
        return json.loads(decoded) if isinstance(decoded, str) else decoded

    async def add(self, memory: Memory) -> str:
        """Add a working memory item."""

        now = datetime.now()
        memory.type = MemoryType.WORKING
        memory.metadata.session_id = self.session_id
        memory.updated_at = now
        memory.accessed_at = now
        memory.ttl = now + timedelta(seconds=self.ttl_seconds)

        payload = json.dumps(memory.to_dict(), default=str, ensure_ascii=False)
        memory_id = memory.id
        index_key = self._index_key(memory_id)

        def _write() -> None:
            pipe = self.redis.pipeline()
            pipe.set(index_key, payload, ex=self.ttl_seconds)
            pipe.rpush(self.key, memory_id)
            pipe.expire(self.key, self.ttl_seconds)
            pipe.ltrim(self.key, -self.max_entries, -1)
            pipe.execute()

        await asyncio.to_thread(_write)
        return memory_id

    async def get(self, memory_id: str) -> Optional[Memory]:
        """Get a single working memory item."""

        raw = await asyncio.to_thread(self.redis.get, self._index_key(memory_id))
        if raw is None:
            return None

        data = self._loads(raw)
        memory = Memory.from_dict(data)
        now = datetime.now()
        memory.accessed_at = now
        memory.ttl = now + timedelta(seconds=self.ttl_seconds)

        payload = json.dumps(memory.to_dict(), default=str, ensure_ascii=False)
        await asyncio.to_thread(self.redis.set, self._index_key(memory_id), payload, ex=self.ttl_seconds)
        await asyncio.to_thread(self.redis.expire, self.key, self.ttl_seconds)
        return memory

    async def list_memories(self) -> list[Memory]:
        """List all working memories for the session."""

        def _fetch() -> tuple[list[str], list[Any]]:
            ids = [self._decode(value) for value in self.redis.lrange(self.key, 0, -1)]
            if not ids:
                return [], []
            pipe = self.redis.pipeline()
            for memory_id in ids:
                pipe.get(self._index_key(memory_id))
            return ids, pipe.execute()

        ids, raw_values = await asyncio.to_thread(_fetch)

        memories: list[Memory] = []
        for memory_id, raw in zip(ids, raw_values):
            if raw is None:
                continue
            try:
                data = self._loads(raw)
                memory = Memory.from_dict(data)
                memories.append(memory)
            except Exception:
                logger.warning("Failed to deserialize working memory %s", memory_id, exc_info=True)
        return memories

    async def clear(self) -> int:
        """Clear all working memories for the session."""

        def _clear() -> int:
            ids = [self._decode(value) for value in self.redis.lrange(self.key, 0, -1)]
            keys = [self._index_key(memory_id) for memory_id in ids]
            deleted = 0
            if keys:
                deleted += int(self.redis.delete(*keys) or 0)
            deleted += int(self.redis.delete(self.key) or 0)
            return deleted

        return await asyncio.to_thread(_clear)

    async def count(self) -> int:
        """Count working memory entries."""

        length = await asyncio.to_thread(self.redis.llen, self.key)
        return int(length or 0)

    async def remove(self, memory_id: str) -> bool:
        """Remove a single working memory entry."""

        def _remove() -> bool:
            deleted = int(self.redis.delete(self._index_key(memory_id)) or 0)
            removed = int(self.redis.lrem(self.key, 0, memory_id) or 0)
            return (deleted + removed) > 0

        return await asyncio.to_thread(_remove)

    @classmethod
    def from_short_term_memory(cls, redis_client: Any, session_id: str, max_turns: int = 10) -> "WorkingMemory":
        """Factory for backward compatibility with ShortTermRedisMemory."""

        return cls(redis_client=redis_client, session_id=session_id, max_entries=max_turns)
