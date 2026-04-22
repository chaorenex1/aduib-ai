from typing import Any

from fastapi import APIRouter

from controllers.common.base import api_endpoint
from controllers.params import AgentCreatePayload
from runtime.entities.anthropic_entities import AnthropicMessageRequest
from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.entities.response_entities import ResponseRequest
from service.agent_service import AgentService

router = APIRouter(tags=["agent"])


@router.post("/agents")
@api_endpoint()
async def create_agent(payload: AgentCreatePayload):
    agent = AgentService.create_agent(payload)
    return agent


@router.post("/agents/v1/chat/completions")
@api_endpoint()
async def agent_chat_completions(req: ChatCompletionRequest) -> Any:
    """OpenAI Chat format — 直调路径."""
    return await AgentService.arun(req)


@router.post("/agents/v1/messages")
@api_endpoint()
async def agent_messages(req: AnthropicMessageRequest) -> Any:
    """Anthropic Messages format — 直调路径."""
    return await AgentService.arun(req)


@router.post("/agents/v1/responses")
@api_endpoint()
async def agent_responses(req: ResponseRequest) -> Any:
    """OpenAI Responses format — 直调路径."""
    return await AgentService.arun(req)
