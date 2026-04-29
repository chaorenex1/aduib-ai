from typing import Any

from models import Agent
from runtime.agent.memory.redis_memory import ShortTermRedisMemory


class LegacyAgentMemoryAccessDisabledError(RuntimeError):
    """Raised when a retired legacy agent memory path is accessed."""


class AgentMemory:
    """AgentMemory is used to store the context of the agent."""

    def __init__(self, agent: Agent, session_id: str):
        self.agent_id = agent.id
        self.user_id = str(agent.user_id or agent.id)
        self.session_id = session_id
        # 从 agent 参数中获取 turns，默认为 20
        self.turns = agent.agent_parameters.get("turns", 20)
        self.short_term_memory = ShortTermRedisMemory(self.session_id)
        # Legacy durable-memory access used a deleted helper; keep the old
        # constructor path commented out while the retired runtime memory
        # pipeline is being deleted.
        # self.long_term_memory = DeletedLegacyMemoryAdapter(
        #     user_id=self.user_id,
        #     agent_id=str(self.agent_id),
        #     top_k=agent.agent_parameters.get("top_k", 5),
        #     score_threshold=agent.agent_parameters.get("score_threshold", 0.8),
        # )

    async def add_memory(self, message: str, long_term_memory: bool = False, compact_session: bool = False) -> str:
        """Add session memory for the active agent context."""
        if not long_term_memory:
            await self.short_term_memory.add_memory(message, compact_session)
            return ""
        # Legacy durable-memory writes used the deleted runtime memory pipeline;
        # keep the old access path commented out so new business code cannot
        # revive it.
        # await self.long_term_memory.add_memory(message)
        raise LegacyAgentMemoryAccessDisabledError(
            "Retired legacy agent memory writes are disabled."
        )

    async def retrieve_context(
        self, query: str, long_term_memory: bool = True, compact_session: bool = False
    ) -> dict[str, Any]:
        """Retrieve context from memory."""
        context: dict[str, Any] = {
            "short_term": await self.short_term_memory.get_short_term_memory(compact_session=compact_session),
            "long_term": [],
        }
        if long_term_memory:
            # Legacy durable-memory retrieval used a deleted helper backed by
            # runtime.memory.manager; keep the old access path commented out
            # while the deleted runtime memory stack is being cleaned up.
            # context["long_term"] = await self.long_term_memory.get_long_term_memory(query=query)
            context["long_term"] = []
        return context

    async def clear_memory(self) -> None:
        """Clear memory."""
        # Legacy combined cleanup used to clear short-term state and then delete
        # retired durable-memory records through
        # runtime.memory.manager.delete_memories_by_agent().
        # Keep that path commented out so callers must choose an explicit
        # short-term-only cleanup instead of reaching the retired long-term flow.
        # await self.short_term_memory.delete_memory()
        # await self.long_term_memory.delete_memory()
        raise LegacyAgentMemoryAccessDisabledError(
            "AgentMemory.clear_memory() is disabled until retired legacy memory cleanup is migrated. "
            "Use clear_short_term_memory() for short-term-only cleanup."
        )

    async def clear_short_term_memory(self):
        """Clear interaction memory."""
        await self.short_term_memory.delete_memory()
