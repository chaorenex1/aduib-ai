"""Conversation source endpoints for programmer memory."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from controllers.common.base import api_endpoint
from controllers.memory.schemas import ConversationAppendMessageRequest, ConversationCreateRequest, ConversationGetQuery
from libs.deps import CurrentUserDep
from service.memory import ConversationSourceService
from service.memory.base.mappers import (
    conversation_append_request_to_command,
    conversation_create_request_to_command,
    conversation_get_query_to_query,
    conversation_view_to_response,
)

router = APIRouter(prefix="/memories/conversations", tags=["Programmer Memory"])


@router.post("", status_code=status.HTTP_201_CREATED)
@api_endpoint(success_status=status.HTTP_201_CREATED)
async def create_conversation(payload: ConversationCreateRequest, current_user: CurrentUserDep):
    """Create or upload a remote conversation source."""
    command = conversation_create_request_to_command(user_id=str(current_user["user_id"]), payload=payload)
    return conversation_view_to_response(ConversationSourceService.create_conversation(command))


@router.post("/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
@api_endpoint(success_status=status.HTTP_201_CREATED)
async def append_conversation_message(
    conversation_id: str,
    payload: ConversationAppendMessageRequest,
    current_user: CurrentUserDep,
):
    """Append one message into an existing conversation source."""
    command = conversation_append_request_to_command(
        user_id=str(current_user["user_id"]),
        conversation_id=conversation_id,
        payload=payload,
    )
    return ConversationSourceService.append_message(command)


@router.get("/{conversation_id}")
@api_endpoint()
async def get_conversation(
    conversation_id: str,
    query: Annotated[ConversationGetQuery, Depends()],
    current_user: CurrentUserDep,
):
    """Fetch one remote conversation source."""
    request = conversation_get_query_to_query(
        user_id=str(current_user["user_id"]),
        conversation_id=conversation_id,
        payload=query,
    )
    return conversation_view_to_response(ConversationSourceService.get_conversation(request))
