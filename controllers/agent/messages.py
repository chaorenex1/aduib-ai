from fastapi import APIRouter

from controllers.agent.schemas import AgentMessagesRequest, AgentMessageTurnRequest
from controllers.common.base import api_endpoint
from service.agent.contracts import AgentMessagesCommand, AgentMessageTurnCommand
from service.agent.message_service import AgentMessageService

router = APIRouter(tags=["agent"])


@router.post("/agents/v1/messages")
@api_endpoint()
async def agent_messages(payload: AgentMessagesRequest):
    return await AgentMessageService.handle_messages(
        AgentMessagesCommand(
            agent_id=payload.agent_id,
            session_id=payload.session_id,
            mode=payload.mode,
            surface=payload.surface,
            request=payload.request,
        )
    )


@router.post("/agents/v1/message")
@api_endpoint()
async def agent_message(payload: AgentMessageTurnRequest):
    return await AgentMessageService.handle_message(
        AgentMessageTurnCommand(
            agent_id=payload.agent_id,
            session_id=payload.session_id,
            mode=payload.mode,
            surface=payload.surface,
            model=payload.model,
            user_text=payload.user_text,
            tool_results=payload.tool_results,
            approval_decision=payload.approval_decision,
            system=payload.system,
            max_tokens=payload.max_tokens,
            temperature=payload.temperature,
            top_p=payload.top_p,
            top_k=payload.top_k,
            stream=payload.stream,
            stop_sequences=payload.stop_sequences,
            thinking=payload.thinking,
            output_config=payload.output_config,
            metadata=payload.metadata,
        )
    )
