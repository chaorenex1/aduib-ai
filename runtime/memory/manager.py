from __future__ import annotations

from runtime.memory.retrieval_manager import MemoryRetrievalMixin
from runtime.memory.types import Memory


class LegacyMemoryWriteDisabledError(RuntimeError):
    """Raised when a caller tries to use the removed legacy memory write pipeline."""


class MemoryManager(MemoryRetrievalMixin):
    """Legacy retrieval facade.

    `runtime.memory.manager` is still kept for retrieval call sites, but the old
    write/delete pipeline has been retired and must not be used anymore.
    """

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id

    @staticmethod
    def _normalize_topic(name: str) -> str:
        """Normalize topic names for retrieval-side comparisons."""
        return name.strip().lower().replace(" ", "")

    async def store(self, _memory: Memory) -> str:
        raise LegacyMemoryWriteDisabledError(
            "Legacy runtime.memory.manager.store() has been disabled. Migrate to the new memory write pipeline."
        )

    def delete_memories_by_agent(self, _user_id: str) -> None:
        raise LegacyMemoryWriteDisabledError(
            "Legacy runtime.memory.manager.delete_memories_by_agent() has been disabled."
        )
