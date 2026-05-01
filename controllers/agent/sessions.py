from fastapi import APIRouter

from controllers.agent.schemas import AgentSessionCreateRequest, AgentSessionUpdateRequest
from controllers.common.base import api_endpoint
from service.agent.contracts import AgentSessionCreateCommand, AgentSessionUpdateCommand
from service.agent.session_service import AgentSessionService

router = APIRouter(tags=["agent"])


@router.post("/agents/v1/sessions")
@api_endpoint(success_status=201)
async def create_session(payload: AgentSessionCreateRequest):
    return await AgentSessionService.create_session(
        AgentSessionCreateCommand(
            agent_id=payload.agent_id,
            mode=payload.mode,
            surface=payload.surface,
            title=payload.title,
            description=payload.description,
        )
    )


@router.patch("/agents/v1/sessions/{session_id}")
@api_endpoint()
async def update_session(session_id: int, payload: AgentSessionUpdateRequest):
    return await AgentSessionService.update_title(
        session_id,
        AgentSessionUpdateCommand(title=payload.title),
    )


@router.delete("/agents/v1/sessions/{session_id}")
@api_endpoint()
async def delete_session(session_id: int):
    return await AgentSessionService.delete_session(session_id)
