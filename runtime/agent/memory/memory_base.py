from abc import ABC, abstractmethod

from runtime.memory.types import MemoryRetrieveResult


class MemoryBase(ABC):
    """
    Compatibility interface for the surviving agent memory surfaces.
    """

    @abstractmethod
    async def add_memory(self, message: str) -> None:
        raise NotImplementedError("Add memory method not implemented.")

    @abstractmethod
    async def get_long_term_memory(self, query: str) -> list[MemoryRetrieveResult]:
        """Retained for legacy-compatible implementations that still expose the old hook."""
        raise NotImplementedError("Get memory method not implemented.")

    @abstractmethod
    async def get_short_term_memory(self, compact_session: bool = False) -> list[str] | str:
        raise NotImplementedError("Get memory method not implemented.")

    @abstractmethod
    async def delete_memory(self) -> None:
        raise NotImplementedError("Delete memory method not implemented.")
