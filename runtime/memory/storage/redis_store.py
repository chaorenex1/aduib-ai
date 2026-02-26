from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Optional

from runtime.memory.storage.adapter import StorageAdapter
from runtime.memory.types.base import Memory


class RedisStore(StorageAdapter[Memory]):
    """Redis-backed memory storage adapter."""

    def __init__(self, redis_client: Any, key_prefix: str = "memory") -> None:
        self.redis = redis_client
        self.key_prefix = key_prefix

    def _memory_key(self, memory_id: str) -> str:
        return f"{self.key_prefix}:{memory_id}"

    def _session_key(self, session_id: str) -> str:
        return f"{self.key_prefix}:session:{session_id}"

    @staticmethod
    def _decode(value: Any) -> Any:
        if isinstance(value, (bytes, bytearray)):
            return value.decode("utf-8")
        return value

    def _loads(self, value: Any) -> dict[str, Any]:
        decoded = self._decode(value)
        return json.loads(decoded) if isinstance(decoded, str) else decoded

    @staticmethod
    def _ttl_seconds(ttl: Optional[datetime]) -> Optional[int]:
        if ttl is None:
            return None
        seconds = int((ttl - datetime.now()).total_seconds())
        return max(1, seconds)

    async def save(self, memory: Memory) -> str:
        payload = json.dumps(memory.to_dict(), default=str, ensure_ascii=False)
        memory_id = memory.id
        memory_key = self._memory_key(memory_id)
        session_id = memory.metadata.session_id
        ttl_seconds = self._ttl_seconds(memory.ttl)
        score = memory.created_at.timestamp()

        def _write() -> None:
            pipe = self.redis.pipeline()
            if ttl_seconds is None:
                pipe.set(memory_key, payload)
            else:
                pipe.set(memory_key, payload, ex=ttl_seconds)
            if session_id:
                pipe.zadd(self._session_key(session_id), {memory_id: score})
            pipe.execute()

        await asyncio.to_thread(_write)
        return memory_id

    async def get(self, memory_id: str) -> Optional[Memory]:
        memory_key = self._memory_key(memory_id)
        raw = await asyncio.to_thread(self.redis.get, memory_key)
        if raw is None:
            return None
        data = self._loads(raw)
        return Memory.from_dict(data)

    async def update(self, memory_id: str, updates: dict) -> Optional[Memory]:
        memory_key = self._memory_key(memory_id)
        raw = await asyncio.to_thread(self.redis.get, memory_key)
        if raw is None:
            return None
        data = self._loads(raw)
        data.update(updates)
        memory = Memory.from_dict(data)
        payload = json.dumps(memory.to_dict(), default=str, ensure_ascii=False)
        ttl_seconds = self._ttl_seconds(memory.ttl)

        def _write() -> None:
            if ttl_seconds is None:
                self.redis.set(memory_key, payload)
            else:
                self.redis.set(memory_key, payload, ex=ttl_seconds)

        await asyncio.to_thread(_write)
        return memory

    async def delete(self, memory_id: str) -> bool:
        memory_key = self._memory_key(memory_id)
        raw = await asyncio.to_thread(self.redis.get, memory_key)
        if raw is None:
            return False
        data = self._loads(raw)
        session_id = data.get("metadata", {}).get("session_id")

        def _delete() -> int:
            pipe = self.redis.pipeline()
            pipe.delete(memory_key)
            if session_id:
                pipe.zrem(self._session_key(session_id), memory_id)
            results = pipe.execute()
            return sum(int(result or 0) for result in results)

        removed = await asyncio.to_thread(_delete)
        return removed > 0

    async def exists(self, memory_id: str) -> bool:
        memory_key = self._memory_key(memory_id)
        exists = await asyncio.to_thread(self.redis.exists, memory_key)
        return bool(exists)

    async def list_by_session(self, session_id: str) -> list[Memory]:
        session_key = self._session_key(session_id)

        def _fetch() -> tuple[list[str], list[Any]]:
            ids = [self._decode(value) for value in self.redis.zrange(session_key, 0, -1)]
            if not ids:
                return [], []
            pipe = self.redis.pipeline()
            for memory_id in ids:
                pipe.get(self._memory_key(memory_id))
            raw_values = pipe.execute()
            return ids, raw_values

        ids, raw_values = await asyncio.to_thread(_fetch)
        memories: list[Memory] = []
        for memory_id, raw in zip(ids, raw_values):
            if raw is None:
                continue
            data = self._loads(raw)
            memories.append(Memory.from_dict(data))
        return memories
