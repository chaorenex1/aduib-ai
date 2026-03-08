from controllers.params import MemoryCreateRequest


class MemoryService:
    """memory service for storing and retrieving memory entries."""

    @staticmethod
    async def store_memory(payload: MemoryCreateRequest) -> str:
        """Store a memory entry and return its ID."""
        if not payload.content and not payload.file:
            raise ValueError("Either content or file must be provided for memory storage.")
        from runtime.memory import Memory
        memory = Memory(
            agent_id=payload.agent_id,
            project_id=payload.project_id,
            user_id=payload.user_id,
            source=payload.memory_source,
            summary_enabled=payload.summary_enabled,
        )
        if payload.content:
            memory.content=payload.content
            memory.content_type="text"
            from runtime.memory.manager import MemoryManager
            memory_id = memory_manager.store_memory(memory)
            return memory_id
        elif payload.file:
            memory.file=await payload.file.read()
            memory.content_type="file"
            from runtime.memory.manager import MemoryManager
            memory_id = memory_manager.store_memory(memory)
            return memory_id
        else:
            raise ValueError("Invalid memory storage request: no content or file provided.")

    @staticmethod
    def retrieve_memory(memory_id: str) -> Any:
        """Retrieve a memory entry by its ID."""
        from runtime.memory.manager import MemoryManager
        memory_manager = MemoryManager()
        return memory_manager.retrieve_memory(memory_id)