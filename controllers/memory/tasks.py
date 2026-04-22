"""Async task endpoints for programmer memory."""

from fastapi import APIRouter, status

from controllers.common.base import api_endpoint
from controllers.memory.schemas import MemoryWriteReplayRequest, TaskCreateRequest
from service.memory import MemoryWriteIngestService, MemoryWriteTaskService
from service.memory.base.mappers import task_create_request_to_command

router = APIRouter(prefix="/memories/tasks", tags=["Programmer Memory"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
@api_endpoint(success_status=status.HTTP_202_ACCEPTED)
async def create_memory_task(payload: TaskCreateRequest):
    """Create one async memory processing task."""
    command = task_create_request_to_command(payload)
    return await MemoryWriteIngestService.accept_task_request(command)


@router.get("/{task_id}")
@api_endpoint()
async def get_memory_task(task_id: str):
    """Query one task status."""
    return MemoryWriteTaskService.get_task(task_id)


@router.get("/{task_id}/result")
@api_endpoint()
async def get_memory_task_result(task_id: str):
    """Query the final result of one task."""
    return MemoryWriteTaskService.get_task_result(task_id)


@router.post("/{task_id}/replay", status_code=status.HTTP_202_ACCEPTED)
@api_endpoint(success_status=status.HTTP_202_ACCEPTED)
async def replay_memory_task(task_id: str, payload: MemoryWriteReplayRequest):
    """Replay queue publish for one failed task."""
    return MemoryWriteTaskService.replay(task_id, actor=payload.actor)
