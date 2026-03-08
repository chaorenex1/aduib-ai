from fastapi import APIRouter

from controllers.common.base import catch_exceptions, BaseResponse
from controllers.params import MemoryCreateRequest
from service.memory_service import MemoryService

# Initialize router
router = APIRouter(prefix="/memory", tags=["Memory"])

@router.post("/store")
@catch_exceptions
async def store_memory(payload: MemoryCreateRequest) -> BaseResponse:
    """Store a memory entry."""
    memory_id = await MemoryService.store_memory(payload)
    return BaseResponse.ok({"memory_id": memory_id})