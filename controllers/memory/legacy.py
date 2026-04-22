"""Legacy memory compatibility endpoints.

These action-style routes are kept for backward compatibility and should not
receive new features. New memory APIs must use the `/memories/*` route family.
"""

from fastapi import APIRouter

from controllers.common.base import api_endpoint
from controllers.memory.schemas import MemoryCreateRequest, MemoryRetrieveRequest, MemoryRetrieveResponse
from service.memory_service import MemoryService

# Legacy compatibility router.
router = APIRouter(prefix="/memory", tags=["Memory"])


@router.post("/store")
@api_endpoint()
async def store_memory(payload: MemoryCreateRequest):
    """Store a memory entry."""
    memory_id = await MemoryService.store_memory(payload)
    return {"memory_id": memory_id}


@router.get("/retrieve")
@api_endpoint()
async def retrieve_memory(payload: MemoryRetrieveRequest) -> list[MemoryRetrieveResponse]:
    """Retrieve memory entries matching a query."""
    memories = await MemoryService.retrieve_memory(payload)
    return memories
