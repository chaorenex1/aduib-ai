"""Conversation source endpoints for programmer memory."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from controllers.common.base import api_endpoint
from controllers.memory.schemas import ConversationAppendMessageRequest, ConversationCreateRequest, ConversationGetQuery
from service.memory import (
    ConversationSourceService,
    conversation_append_request_to_command,
    conversation_create_request_to_command,
    conversation_get_query_to_query,
)

router = APIRouter(prefix="/memories/conversations", tags=["Programmer Memory"])


@router.post("", status_code=status.HTTP_201_CREATED)
@api_endpoint(success_status=status.HTTP_201_CREATED)
async def create_conversation(payload: ConversationCreateRequest):
    """Create or upload a remote conversation source."""
    command = conversation_create_request_to_command(payload)
    return ConversationSourceService.create_conversation(command)


@router.post("/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
@api_endpoint(success_status=status.HTTP_201_CREATED)
async def append_conversation_message(
    conversation_id: str,
    payload: ConversationAppendMessageRequest,
):
    """Append one message into an existing conversation source."""
    command = conversation_append_request_to_command(conversation_id=conversation_id, payload=payload)
    return ConversationSourceService.append_message(command)


@router.get("/{conversation_id}")
@api_endpoint()
async def get_conversation(
    conversation_id: str,
    query: Annotated[ConversationGetQuery, Depends()],
):
    """Fetch one remote conversation source."""
    request = conversation_get_query_to_query(conversation_id=conversation_id, payload=query)
    return ConversationSourceService.get_conversation(request)
