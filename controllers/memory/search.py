"""Retrieval endpoints for programmer memory."""

from fastapi import APIRouter

from controllers.common.base import api_endpoint, not_implemented
from controllers.memory.schemas import MemorySearchRequest

router = APIRouter(prefix="/memories", tags=["Programmer Memory"])


@router.post("/search")
@api_endpoint()
async def search_memories(_payload: MemorySearchRequest):
    """Unified online retrieval entrypoint."""

    not_implemented("search memories")
