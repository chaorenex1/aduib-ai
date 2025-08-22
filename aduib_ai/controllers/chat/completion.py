from typing import Any

from fastapi import APIRouter, Request

from service.completion_service import CompletionService
from ..params import CompletionRequest, ChatCompletionRequest

router = APIRouter(tags=['completion'])

@router.post('/completions')
def completion(req:CompletionRequest,raw_request: Request) -> Any:
    """
    Completion endpoint
    """
    return CompletionService.create_completion(req, raw_request)


@router.post('/chat/completions')
def completion(req:ChatCompletionRequest,raw_request: Request) -> Any:
    """
    Completion endpoint
    """
    return CompletionService.create_completion(req, raw_request)