"""Feedback endpoints for programmer memory."""

from fastapi import APIRouter, status

from controllers.common.base import api_endpoint, not_implemented
from controllers.memory.schemas import MemoryFeedbackCreateRequest, MemoryUsageCreateRequest

router = APIRouter(prefix="/memories", tags=["Programmer Memory"])


@router.post("/usages", status_code=status.HTTP_202_ACCEPTED)
@api_endpoint(success_status=status.HTTP_202_ACCEPTED)
async def record_memory_usage(_payload: MemoryUsageCreateRequest):
    """Record which memories were actually used during one session."""

    not_implemented("record memory usage")


@router.post("/feedback", status_code=status.HTTP_202_ACCEPTED)
@api_endpoint(success_status=status.HTTP_202_ACCEPTED)
async def record_memory_feedback(_payload: MemoryFeedbackCreateRequest):
    """Record quality, correction, and ranking feedback for memory use."""

    not_implemented("record memory feedback")
