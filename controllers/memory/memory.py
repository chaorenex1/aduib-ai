from fastapi import APIRouter

from controllers.common.base import BaseResponse, catch_exceptions
from controllers.params import MemoryCreateRequest, MemoryRetrieveRequest, MemoryRetrieveResponse
from service.memory_service import MemoryService

# Initialize router
router = APIRouter(prefix="/memory", tags=["Memory"])


@router.post("/store")
@catch_exceptions
async def store_memory(payload: MemoryCreateRequest) -> BaseResponse:
    """Store a memory entry."""
    memory_id = await MemoryService.store_memory(payload)
    return BaseResponse.ok({"memory_id": memory_id})


@router.get("/retrieve")
@catch_exceptions
async def retrieve_memory(payload: MemoryRetrieveRequest) -> list[MemoryRetrieveResponse]:
    """Retrieve memory entries matching a query."""
    memories = await MemoryService.retrieve_memory(payload)
    return memories
