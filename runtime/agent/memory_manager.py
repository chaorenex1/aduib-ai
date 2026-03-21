import logging

from models import Agent
from runtime.agent.memory.agent_memory import AgentMemory
from runtime.memory.types import MemoryRetrieveResult

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages agent memory operations"""

    def __init__(self, agent: Agent):
        self.agent = agent
        self.memory_key = ""
        self._agent_memories: dict[str, AgentMemory] = {}

    def get_or_create_memory(self, session_id: int) -> AgentMemory:
        self.memory_key = f"{self.agent.id}_{session_id}"
        if self.memory_key not in self._agent_memories:
            self._agent_memories[self.memory_key] = AgentMemory(
                agent=self.agent,
                session_id=str(session_id),
            )
        return self._agent_memories[self.memory_key]

    async def get_short_term_memory(self, compact_session: bool = False) -> list[str] | str:
        context = await self._agent_memories[self.memory_key].retrieve_context("", False, compact_session)
        return context.get("short_term", [])

    async def clear_short_term_memory(self):
        await self._agent_memories[self.memory_key].clear_short_term_memory()

    async def add_memory(self, message: str, long_term_memory: bool = False, compact_session: bool = False) -> str:
        return await self._agent_memories[self.memory_key].add_memory(message, long_term_memory, compact_session)

    async def get_long_term_memory(self, query: str) -> list[MemoryRetrieveResult]:
        context = await self._agent_memories[self.memory_key].retrieve_context(query, True)
        return context.get("long_term", [])

    async def retrieve_context(
        self, user_message: str, long_term_memory: bool = True, compact_session: bool = False
    ) -> dict:
        return await self._agent_memories[self.memory_key].retrieve_context(
            user_message, long_term_memory, compact_session
        )

    async def cleanup_memory(self) -> None:
        agent_memory: AgentMemory = self._agent_memories.pop(self.memory_key, None)
        if agent_memory:
            await agent_memory.clear_memory()
        logger.info("Cleaned up memory for session: %s", self.memory_key)

    async def get_full_response_text(self) -> str:
        memory = await self.get_short_term_memory()
        if isinstance(memory, list):
            return "\n".join(memory)
        elif isinstance(memory, str):
            return memory
        else:
            return ""
