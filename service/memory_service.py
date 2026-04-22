from controllers.memory.schemas import MemoryCreateRequest, MemoryRetrieveRequest, MemoryRetrieveResponse
from runtime.memory.types import MemoryRetrieve, MemoryRetrieveResult, MemoryRetrieveType


class MemoryService:
    """memory service for storing and retrieving memory entries."""

    @staticmethod
    async def store_memory(payload: MemoryCreateRequest) -> str:
        """Store a memory entry and return its ID."""
        if not payload.content and not payload.file:
            raise ValueError("Either content or file must be provided for memory storage.")
        from runtime.memory.types import Memory

        memory = Memory(
            agent_id=payload.agent_id,
            project_id=payload.project_id,
            user_id=payload.user_id,
            source=payload.memory_source,
            summary_enabled=payload.summary_enabled,
        )
        if payload.content:
            memory.content = payload.content
            from runtime.memory.manager import MemoryManager

            memory_manager = MemoryManager(user_id=payload.user_id)
            memory_id = await memory_manager.store(memory)
            return memory_id
        elif payload.file:
            memory.content = str(await payload.file.read())
            from runtime.memory.manager import MemoryManager

            memory_manager = MemoryManager(user_id=payload.user_id)
            memory_id = await memory_manager.store(memory)
            return memory_id
        else:
            raise ValueError("Invalid memory storage request: no content or file provided.")

    @staticmethod
    async def retrieve_memory(payload: MemoryRetrieveRequest) -> list[MemoryRetrieveResponse]:
        """Retrieve memory entries matching a query."""
        retrieve_request = MemoryRetrieve(
            query=payload.query,
            user_id=payload.user_id,
            agent_id=payload.agent_id,
            project_id=payload.project_id,
            retrieve_type=MemoryRetrieveType(payload.retrieve_type),
            top_k=payload.top_k,
            score_threshold=payload.score_threshold,
            filters=payload.filters,
        )
        from runtime.memory.manager import MemoryManager

        memory_manager = MemoryManager(user_id=payload.user_id)
        results: list[MemoryRetrieveResult] = await memory_manager.retrieve_memories(retrieve_request)
        return [
            MemoryRetrieveResponse.from_memory(
                content=result.content, memory_id=result.memory_id, score=result.score, metadata=result.metadata
            )
            for result in results
        ]
