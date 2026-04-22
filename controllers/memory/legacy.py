"""Legacy memory compatibility endpoints.

These action-style routes are kept for backward compatibility and should not
receive new features. New memory APIs must use the `/memories/*` route family.
"""

from fastapi import APIRouter, status

from controllers.common.base import api_endpoint
from controllers.memory.schemas import MemoryCreateRequest, MemoryRetrieveRequest, MemoryRetrieveResponse
from service.memory import MemoryService
from service.memory.mappers import (
    memory_create_request_to_command,
    memory_retrieve_request_to_query,
    retrieved_memories_to_response,
)

# Legacy compatibility router.
router = APIRouter(prefix="/memory", tags=["Memory"])


@router.post("/store", status_code=status.HTTP_202_ACCEPTED)
@api_endpoint(success_status=status.HTTP_202_ACCEPTED)
async def store_memory(payload: MemoryCreateRequest):
    """Accept a memory write request and enqueue the async pipeline."""
    command = await memory_create_request_to_command(payload)
    return await MemoryService.store_memory(command)


@router.get("/retrieve")
@api_endpoint()
async def retrieve_memory(payload: MemoryRetrieveRequest) -> list[MemoryRetrieveResponse]:
    """Retrieve memory entries matching a query."""
    query = memory_retrieve_request_to_query(payload)
    memories = await MemoryService.retrieve_memory(query)
    return retrieved_memories_to_response(memories)
