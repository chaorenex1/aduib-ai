from typing import Any

from models import Agent
from runtime.agent.memory.embeddings_memory import LongTermEmbeddingsMemory
from runtime.agent.memory.redis_memory import ShortTermRedisMemory


class AgentMemory:
    """AgentMemory is used to store the context of the agent."""

    def __init__(self, agent: Agent, session_id: str):
        self.agent_id = agent.id
        self.user_id = str(agent.user_id or agent.id)
        self.session_id = session_id
        # 从 agent 参数中获取 turns，默认为 20
        self.turns = agent.agent_parameters.get("turns", 20)
        self.short_term_memory = ShortTermRedisMemory(self.session_id)
        self.long_term_memory = LongTermEmbeddingsMemory(
            user_id=self.user_id,
            agent_id=str(self.agent_id),
            top_k=agent.agent_parameters.get("top_k", 5),
            score_threshold=agent.agent_parameters.get("score_threshold", 0.8),
        )

    async def add_memory(self, message: str, long_term_memory: bool = False, compact_session: bool = False) -> str:
        """Add memory to the agent's memory. If the number of turns exceeds the limit, add to long term memory."""
        if not long_term_memory:
            await self.short_term_memory.add_memory(message, compact_session)
        else:
            await self.long_term_memory.add_memory(message)

    async def retrieve_context(
        self, query: str, long_term_memory: bool = True, compact_session: bool = False
    ) -> dict[str, Any]:
        """Retrieve context from memory."""
        context: dict[str, Any] = {
            "short_term": await self.short_term_memory.get_short_term_memory(compact_session=compact_session),
            "long_term": [],
        }
        if long_term_memory:
            context["long_term"] = await self.long_term_memory.get_long_term_memory(query=query)
        return context

    async def clear_memory(self) -> None:
        """Clear memory."""
        await self.short_term_memory.delete_memory()
        await self.long_term_memory.delete_memory()

    async def clear_short_term_memory(self):
        """Clear interaction memory."""
        await self.short_term_memory.delete_memory()
