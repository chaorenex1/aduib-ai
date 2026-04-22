"""Conversation source endpoints for programmer memory."""

from fastapi import APIRouter, status

from controllers.common.base import api_endpoint, not_implemented
from controllers.memory.schemas import ConversationAppendMessageRequest, ConversationCreateRequest

router = APIRouter(prefix="/memories/conversations", tags=["Programmer Memory"])


@router.post("", status_code=status.HTTP_201_CREATED)
@api_endpoint(success_status=status.HTTP_201_CREATED)
async def create_conversation(_payload: ConversationCreateRequest):
    """Create or upload a remote conversation source."""

    not_implemented("create conversation")


@router.post("/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
@api_endpoint(success_status=status.HTTP_201_CREATED)
async def append_conversation_message(
    conversation_id: str,
    _payload: ConversationAppendMessageRequest,
):
    """Append one message into an existing conversation source."""

    not_implemented(f"append message to conversation {conversation_id}")


@router.get("/{conversation_id}")
@api_endpoint()
async def get_conversation(conversation_id: str):
    """Fetch one remote conversation source."""

    not_implemented(f"get conversation {conversation_id}")
