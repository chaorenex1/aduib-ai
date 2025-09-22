from typing import Any

from fastapi import APIRouter

from controllers.common.base import BaseResponse, catch_exceptions
from controllers.params import AgentCreatePayload
from runtime.entities.llm_entities import ChatCompletionRequest
from service.agent_service import AgentService

router = APIRouter(tags=["web_memo"])

@router.post("/agents")
@catch_exceptions
async def create_agent(payload:AgentCreatePayload):
    agent = AgentService.create_agent(payload)
    return BaseResponse.ok(agent)


@router.get("/agents/{agent_id}/v1/models")
@catch_exceptions
async def get_agent_models(agent_id: int):
    models = AgentService.get_agent_models(agent_id)
    return models



@router.post("/agents/{agent_id}/v1/chat/completions")
@catch_exceptions
async def completion(agent_id: int,req: ChatCompletionRequest) -> Any:
    """
    Completion endpoint
    """
    return await AgentService.create_completion(agent_id, req)