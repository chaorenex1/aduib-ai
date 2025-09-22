import threading

from runtime.agent.agent_type import Message
from runtime.agent.memory.embeddings_memory import LongTermEmbeddingsMemory
from runtime.agent.memory.redis_memory import ShortTermRedisMemory


class AgentMemory:
    """AgentMemory is used to store the context of the agent."""
    def __init__(self,agent_id:int,session_id: str, turns: int = 10):
        self.agent_id = agent_id
        self.session_id = session_id
        self.turns = turns
        self.short_term_memory = ShortTermRedisMemory(self.session_id, self.turns)
        self.long_term_memory = LongTermEmbeddingsMemory(str(self.agent_id))
        _locks = {}  # 类级别的锁字典
        _locks_lock = threading.Lock()  # 保护锁字典的锁

        # 获取或创建基于 session_id 的锁
        with AgentMemory._locks_lock:
            if session_id not in AgentMemory._locks:
                AgentMemory._locks[session_id] = threading.RLock()
            self._lock = AgentMemory._locks[session_id]


    def add_interaction(self, message: Message) -> None:
        """Add interaction to memory."""
        with self._lock:
            memory = self.short_term_memory.add_memory(message)
            if memory:
                memorys = self.short_term_memory.get_memory("")
                memorys_ = [Message(**m) for m in memorys]
                for m in memorys_:
                    if m.assistant_message:
                        self.long_term_memory.add_memory(m)
                self.short_term_memory.delete_memory()


    def retrieve_context(self, query: str) -> dict:
        """Retrieve context from memory."""
        with self._lock:
            short_term_context = self.short_term_memory.get_memory(query)
            long_term_context = self.long_term_memory.get_memory(query)
            return {
                "short_term": short_term_context,
                "long_term": long_term_context
            }
