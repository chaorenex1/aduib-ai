import logging
from typing import Any, Optional

from runtime.agent.memory.memory_base import MemoryBase
from runtime.memory.types import MemoryRetrieveResult, MemoryRetrieveType

logger = logging.getLogger(__name__)


class LongTermEmbeddingsMemory(MemoryBase):
    def __init__(
        self,
        user_id: str,
        agent_id: Optional[str] = None,
        top_k: int = 5,
        score_threshold: float = 0.8,
    ):
        self.user_id = user_id
        self.agent_id = agent_id
        self.top_k = top_k
        self.score_threshold = score_threshold

        from runtime.memory.manager import MemoryManager

        self._manager = MemoryManager(
            user_id=user_id,
        )

    async def add_memory(self, message: str) -> None:
        from runtime.memory.types import Memory, MemorySource

        memory = Memory(
            content=message,
            user_id=self.user_id,
            agent_id=self.agent_id or "",
            source=MemorySource.AGENT_TASK,
        )
        try:
            memory_id = await self._manager.store(memory)
            logger.info("Memory stored: id=%s, user=%s", memory_id, self.user_id)
        except Exception:
            logger.exception("Failed to store memory for user=%s", self.user_id)

    async def get_long_term_memory(self, query: str) -> list[MemoryRetrieveResult]:
        from runtime.memory.types import MemoryRetrieve

        retrieve = MemoryRetrieve(
            query=query,
            user_id=self.user_id,
            agent_id=self.agent_id,
            top_k=self.top_k,
            score_threshold=self.score_threshold,
            retrieve_type=MemoryRetrieveType.LLM,
        )
        try:
            return await self._manager.retrieve_memories(retrieve)
        except Exception:
            logger.exception("Failed to retrieve memories for user=%s", self.user_id)
            return []

    async def get_short_term_memory(self, compact_session=False) -> list[dict[str, Any]]:
        # Short-term memory is managed by RedisMemory, not this class.
        return []

    async def delete_memory(self) -> None:
        self._manager.delete_memories_by_agent(self.user_id)
