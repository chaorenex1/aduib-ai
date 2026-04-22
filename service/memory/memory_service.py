from runtime.memory.types import MemoryRetrieve, MemoryRetrieveResult, MemoryRetrieveType

from .base.contracts import MemoryRetrievedMemory, MemoryRetrieveQuery, MemoryWriteCommand


class MemoryService:
    """Memory service for storing and retrieving memory entries."""

    @staticmethod
    async def store_memory(payload: MemoryWriteCommand) -> dict:
        """Accept a memory write request and enqueue the async pipeline."""
        from .write_ingest_service import MemoryWriteIngestService

        return await MemoryWriteIngestService.accept_memory_write(payload)

    @staticmethod
    async def retrieve_memory(payload: MemoryRetrieveQuery) -> list[MemoryRetrievedMemory]:
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
            MemoryRetrievedMemory(
                content=result.content,
                memory_id=result.memory_id,
                score=result.score,
                metadata=result.metadata,
            )
            for result in results
        ]
