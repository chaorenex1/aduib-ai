from typing import Any

from fastapi import APIRouter

from controllers.common.base import api_endpoint
from runtime.entities.anthropic_entities import AnthropicMessageRequest
from runtime.entities.llm_entities import ChatCompletionRequest, CompletionRequest
from runtime.entities.response_entities import ResponseRequest
from service import ClaudeCompletionService
from service.completion_service import CompletionService
from service.response_service import ResponseService

router = APIRouter(tags=["completion"])


@router.post("/completions")
@api_endpoint()
async def create_completion(req: CompletionRequest) -> Any:
    """
    Completion endpoint
    """
    return await CompletionService.create_completion(req)


@router.post("/chat/completions")
@api_endpoint()
async def create_chat_completion(req: ChatCompletionRequest) -> Any:
    """
    Completion endpoint
    """
    return await CompletionService.create_completion(req)


@router.post("/messages")
@api_endpoint()
async def messages(req: AnthropicMessageRequest) -> Any:
    """
    Anthropic Messages API endpoint
    """
    return await ClaudeCompletionService.create_completion(req)


@router.post("/responses")
@api_endpoint()
async def responses(req: ResponseRequest) -> Any:
    """
    OpenAI Response API endpoint
    """
    return await ResponseService.create_response(req)
