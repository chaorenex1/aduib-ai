"""Async task endpoints for programmer memory."""

from fastapi import APIRouter, status

from controllers.common.base import api_endpoint, not_implemented
from controllers.memory.schemas import TaskCreateRequest

router = APIRouter(prefix="/memories/tasks", tags=["Programmer Memory"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
@api_endpoint(success_status=status.HTTP_202_ACCEPTED)
async def create_memory_task(_payload: TaskCreateRequest):
    """Create one async memory processing task."""

    not_implemented("create memory task")


@router.get("/{task_id}")
@api_endpoint()
async def get_memory_task(task_id: str):
    """Query one task status."""

    not_implemented(f"get memory task {task_id}")


@router.get("/{task_id}/result")
@api_endpoint()
async def get_memory_task_result(task_id: str):
    """Query the final result of one task."""

    not_implemented(f"get memory task result {task_id}")
