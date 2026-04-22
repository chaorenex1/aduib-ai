"""Formal memory object endpoints for programmer memory."""

from typing import Annotated

from fastapi import APIRouter, Depends

from controllers.common.base import api_endpoint, not_implemented
from controllers.memory.schemas import MemoryByPathQuery, MemoryListQuery

router = APIRouter(prefix="/memories", tags=["Programmer Memory"])


@router.get("")
@api_endpoint()
async def list_memories(_query: Annotated[MemoryListQuery, Depends()]):
    """List formal memory objects."""

    not_implemented("list memories")


@router.get("/by-path")
@api_endpoint()
async def get_memory_by_path(_query: Annotated[MemoryByPathQuery, Depends()]):
    """Read a memory or project/session material file by canonical path."""

    not_implemented("get memory by path")


@router.get("/{memory_id}/content")
@api_endpoint()
async def get_memory_content(memory_id: str):
    """Fetch one memory body content."""

    not_implemented(f"get memory content {memory_id}")


@router.get("/{memory_id}")
@api_endpoint()
async def get_memory(memory_id: str):
    """Fetch one memory metadata record."""

    not_implemented(f"get memory {memory_id}")
