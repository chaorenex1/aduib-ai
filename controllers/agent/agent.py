from typing import Any

from fastapi import APIRouter

from controllers.common.base import BaseResponse, catch_exceptions
from controllers.params import AgentCreatePayload
from runtime.entities.anthropic_entities import AnthropicMessageRequest
from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.entities.response_entities import ResponseRequest
from service.agent_service import AgentService

router = APIRouter(tags=["agent"])


@router.post("/agents")
@catch_exceptions
async def create_agent(payload: AgentCreatePayload):
    agent = AgentService.create_agent(payload)
    return BaseResponse.ok(agent)


@router.post("/agents/v1/chat/completions")
@catch_exceptions
async def agent_chat_completions(req: ChatCompletionRequest) -> Any:
    """OpenAI Chat format — 直调路径."""
    return await AgentService.arun(req)


@router.post("/agents/v1/messages")
@catch_exceptions
async def agent_messages(req: AnthropicMessageRequest) -> Any:
    """Anthropic Messages format — 直调路径."""
    return await AgentService.arun(req)


@router.post("/agents/v1/responses")
@catch_exceptions
async def agent_responses(req: ResponseRequest) -> Any:
    """OpenAI Responses format — 直调路径."""
    return await AgentService.arun(req)
