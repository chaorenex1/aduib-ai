from typing import Any

from fastapi import APIRouter, Request

from controllers.common.base import catch_exceptions
from libs.deps import CurrentApiKeyDep
from runtime.entities.llm_entities import CompletionRequest, ChatCompletionRequest
from service.completion_service import CompletionService

router = APIRouter(tags=['completion'])

@router.post('/completions')
@catch_exceptions
def completion(req:CompletionRequest,raw_request: Request,current_key:CurrentApiKeyDep) -> Any:
    """
    Completion endpoint
    """
    return CompletionService.create_completion(req, raw_request)


@router.post('/chat/completions1')
@catch_exceptions
def completion(req:ChatCompletionRequest,raw_request: Request,current_key:CurrentApiKeyDep) -> Any:
    """
    Completion endpoint
    """
    return CompletionService.create_completion(req, raw_request)