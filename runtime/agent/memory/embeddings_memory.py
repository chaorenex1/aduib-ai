import logging
from typing import Any, Optional

from runtime.agent.memory.memory_base import MemoryBase
from runtime.memory.manager import LegacyMemoryWriteDisabledError
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

    async def add_memory(self, _message: str) -> None:
        # Legacy long-term writes used runtime.memory.manager.store(); keep the old
        # path commented out so new business code cannot keep writing through it.
        # from runtime.memory.types import Memory, MemorySource
        # memory = Memory(
        #     content=message,
        #     user_id=self.user_id,
        #     agent_id=self.agent_id or "",
        #     source=MemorySource.AGENT_TASK,
        # )
        # memory_id = await self._manager.store(memory)
        raise LegacyMemoryWriteDisabledError(
            "Long-term embeddings memory writes are disabled until migrated to the new memory pipeline."
        )

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
        except Exception as exc:
            logger.exception("Failed to retrieve memories for user=%s", self.user_id)
            raise RuntimeError("Long-term memory retrieval failed") from exc

    async def get_short_term_memory(self, _compact_session=False) -> list[dict[str, Any]]:
        # Short-term memory is managed by RedisMemory, not this class.
        return []

    async def delete_memory(self) -> None:
        # Legacy long-term deletes used runtime.memory.manager.delete_memories_by_agent();
        # keep the old path commented out together with legacy writes.
        # self._manager.delete_memories_by_agent(self.user_id)
        raise LegacyMemoryWriteDisabledError(
            "Long-term embeddings memory deletes are disabled until migrated to the new memory pipeline."
        )
