from typing import Any

from fastapi import APIRouter

from ..params import CompletionRequest
from ...service.completion_service import CompletionService

router = APIRouter(tags=['completion'])



@router.post('/completion')
def completion(chat:CompletionRequest) -> Any:
    """
    Completion endpoint
    """
    return CompletionService.generate_completion(chat)