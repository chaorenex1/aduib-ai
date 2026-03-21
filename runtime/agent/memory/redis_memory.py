import json
import logging

from component.cache.redis_cache import redis_client
from runtime.agent.memory.memory_base import MemoryBase

logger = logging.getLogger(__name__)


class ShortTermRedisMemory(MemoryBase):
    def __init__(self, session_id: str):
        self.client = redis_client
        self.session_id = session_id
        self._message_key = f"{self.session_id}_list"
        self._compact_key = f"{self.session_id}_compact"

    async def get_short_term_memory(self, compact_session=False) -> list[str] | str:
        if compact_session:
            return await self.get_compact_session()
        memory = self.client.get(self._message_key)
        if not memory:
            return []

        if isinstance(memory, bytes):
            memory = memory.decode("utf-8")

        try:
            data = json.loads(memory)
        except json.JSONDecodeError:
            logger.warning("Invalid short-term memory payload for session %s", session_id)
            return []
        return data if isinstance(data, list) else []

    async def get_compact_session(self) -> str:
        memory = self.client.get(self._compact_key)
        if not memory:
            return ""
        if isinstance(memory, bytes):
            memory = memory.decode("utf-8")
        if isinstance(memory, bytes):
            memory = memory.decode("utf-8")

        return memory

    async def get_long_term_memory(self, query: str) -> list[str]:
        return []

    async def add_memory(self, summary: str, compact_session=False) -> None:
        if compact_session:
            self.client.setex(self._compact_key, 24 * 3600, json.dumps(summary))
        else:
            message_list = await self.get_short_term_memory()
            message_list.append(summary)
            self.client.setex(self._message_key, 24 * 3600, json.dumps(message_list))

    async def delete_memory(self) -> None:
        self.client.delete(self.session_id)
        self.client.delete(self._message_key)
        self.client.delete(self._compact_key)

    async def clear_interaction(self):
        """Clear interaction memory."""
        self.client.delete(self._message_key)
        self.client.delete(self._compact_key)
