import json

from component.cache.redis_cache import redis_client
from runtime.agent.agent_type import Message
from runtime.agent.memory.memory_base import MemoryBase


class ShortTermRedisMemory(MemoryBase):
    def __init__(self, session_id: str, max_turns: int = 20):
        self.max_turns = max_turns
        self.client = redis_client
        self.session_id = session_id

    def add_memory(self, message:Message) -> None | dict:
        entry = json.dumps(message)
        self.client.rpush(self.session_id, entry)
        if self.client.llen(self.session_id) > self.max_turns:
            return json.loads(self.client.lpop(self.session_id))
        else:
            return None

    def get_memory(self, query:str) -> list[dict]:
        entries = self.client.lrange(self.session_id, 0, -1)
        return [json.loads(entry) for entry in entries]

    def delete_memory(self) -> None:
        self.client.delete(self.session_id)
