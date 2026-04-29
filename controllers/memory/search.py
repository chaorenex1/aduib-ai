"""Retrieval endpoints for programmer memory."""

from fastapi import APIRouter

from controllers.common.base import api_endpoint
from controllers.common.error import UnauthorizedError
from controllers.memory.schemas import (
    MemoryFindRequest,
    MemoryFindResponse,
    MemorySearchRequest,
    MemorySearchResponse,
)
from libs.context import get_current_user_id
from runtime.memory.find import MemoryFindRuntime
from runtime.memory.find_types import MemoryFindRequestDTO
from runtime.memory.search import MemorySearchRuntime
from runtime.memory.search_types import MemorySearchRequestDTO

router = APIRouter(prefix="/memories", tags=["Programmer Memory"])


@router.post("/find")
@api_endpoint()
async def find_memories(payload: MemoryFindRequest):
    """Run plain semantic memory retrieval for the current user."""

    user_id = _require_current_user_id()
    request = MemoryFindRequestDTO.model_validate(payload.model_dump())
    response = MemoryFindRuntime.find_for_current_user(user_id=user_id, payload=request)
    return MemoryFindResponse.model_validate(response.model_dump())


@router.post("/search")
@api_endpoint()
async def search_memories(payload: MemorySearchRequest):
    """Run session-aware memory retrieval for the current user."""

    user_id = _require_current_user_id()
    request = MemorySearchRequestDTO.model_validate(payload.model_dump())
    response = MemorySearchRuntime.search_for_current_user(user_id=user_id, payload=request)
    return MemorySearchResponse.model_validate(response.model_dump())


def _require_current_user_id() -> str:
    user_id = get_current_user_id()
    if user_id is None or not str(user_id).strip():
        raise UnauthorizedError("Missing current user context")
    return str(user_id).strip()
