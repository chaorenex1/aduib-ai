"""Formal memory object endpoints for programmer memory."""

from typing import Annotated

from fastapi import APIRouter, Depends

from controllers.common.base import api_endpoint
from controllers.memory.schemas import MemoryByPathQuery, MemoryListQuery, MemoryScope
from service.memory import MemoryReadService

router = APIRouter(prefix="/memories", tags=["Programmer Memory"])


@router.get("")
@api_endpoint()
async def list_memories(_query: Annotated[MemoryListQuery, Depends()]):
    """List formal memory objects."""
    return MemoryReadService.list_memories(
        user_id=_query.user_id,
        agent_id=_query.agent_id,
        project_id=_query.project_id,
        kind=_query.kind,
        path_prefix=_query.path_prefix,
        updated_after=_query.updated_after,
        cursor=_query.cursor,
        limit=_query.limit,
    )


@router.get("/by-path")
@api_endpoint()
async def get_memory_by_path(_query: Annotated[MemoryByPathQuery, Depends()]):
    """Read a memory or project/session material file by canonical path."""
    return MemoryReadService.get_memory_by_path(
        _query.path,
        user_id=_query.user_id,
        agent_id=_query.agent_id,
        project_id=_query.project_id,
    )


@router.get("/{memory_id}/content")
@api_endpoint()
async def get_memory_content(memory_id: str, _query: Annotated[MemoryScope, Depends()]):
    """Fetch one memory body content."""
    return MemoryReadService.get_memory_content(
        memory_id,
        user_id=_query.user_id,
        agent_id=_query.agent_id,
        project_id=_query.project_id,
    )


@router.get("/{memory_id}")
@api_endpoint()
async def get_memory(memory_id: str, _query: Annotated[MemoryScope, Depends()]):
    """Fetch one memory metadata record."""
    return MemoryReadService.get_memory(
        memory_id,
        user_id=_query.user_id,
        agent_id=_query.agent_id,
        project_id=_query.project_id,
    )
