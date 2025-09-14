from typing import Any

from fastapi import APIRouter, Request

from controllers.common.base import catch_exceptions
from runtime.entities.llm_entities import CompletionRequest, ChatCompletionRequest
from service.completion_service import CompletionService

router = APIRouter(tags=['completion'])

@router.post('/completions')
@catch_exceptions
def completion(req:CompletionRequest,raw_request: Request) -> Any:
    """
    Completion endpoint
    """
    return CompletionService.create_completion(req, raw_request)


@router.post('/chat/completions')
@catch_exceptions
def completion(req:ChatCompletionRequest,raw_request: Request) -> Any:
    """
    Completion endpoint
    """
    return CompletionService.create_completion(req, raw_request)