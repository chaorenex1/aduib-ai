from typing import Any

from fastapi import APIRouter, Request

from libs.deps import CurrentApiKeyDep
from runtime.entities.llm_entities import CompletionRequest, ChatCompletionRequest
from service.completion_service import CompletionService

router = APIRouter(tags=['completion'])

@router.post('/completions')
def completion(req:CompletionRequest,raw_request: Request,current_key:CurrentApiKeyDep) -> Any:
    """
    Completion endpoint
    """
    return CompletionService.create_completion(req, raw_request)


@router.post('/chat/completions')
def completion(req:ChatCompletionRequest,raw_request: Request,current_key:CurrentApiKeyDep) -> Any:
    """
    Completion endpoint
    """
    return CompletionService.create_completion(req, raw_request)