from abc import ABC, abstractmethod

from runtime.agent.agent_type import Message


class MemoryBase(ABC):
    """
    Base class for memory. Memory is used to store information.
    """

    @abstractmethod
    def add_memory(self, message: Message) -> None:
        raise NotImplementedError("Add memory method not implemented.")

    @abstractmethod
    def get_memory(self, query: str) -> list[dict]:
        raise NotImplementedError("Get memory method not implemented.")

    @abstractmethod
    def delete_memory(self) -> None:
        raise NotImplementedError("Delete memory method not implemented.")
