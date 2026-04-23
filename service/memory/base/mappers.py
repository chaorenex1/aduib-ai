from __future__ import annotations

from controllers.memory.schemas import (
    ConversationAppendMessageRequest,
    ConversationCreateRequest,
    ConversationGetQuery,
    ConversationSourceResponse,
    MemoryCreateRequest,
    MemoryRetrieveRequest,
    MemoryRetrieveResponse,
    TaskCreateRequest,
)

from .contracts import (
    ConversationMessageRecord,
    ConversationSourceAppendCommand,
    ConversationSourceCreateCommand,
    ConversationSourceGetQuery,
    ConversationSourceMetadata,
    ConversationSourceView,
    MemoryRetrievedMemory,
    MemoryRetrieveQuery,
    MemorySourceRef,
    MemoryTaskCreateCommand,
    MemoryWriteCommand,
)
from .enums import MemoryTriggerType


def conversation_create_request_to_command(
    *,
    user_id: str,
    payload: ConversationCreateRequest,
) -> ConversationSourceCreateCommand:
    return ConversationSourceCreateCommand(
        user_id=user_id,
        agent_id=payload.agent_id,
        project_id=payload.project_id,
        external_source=payload.conversation.external_source,
        external_session_id=payload.conversation.external_session_id,
        title=payload.conversation.title,
        messages=[
            ConversationMessageRecord(**message.model_dump(mode="python", exclude_none=True))
            for message in payload.conversation.messages
        ],
        metadata=ConversationSourceMetadata(**payload.metadata.model_dump(mode="python", exclude_none=True))
        if payload.metadata
        else None,
    )


def conversation_append_request_to_command(
    *,
    user_id: str,
    conversation_id: str,
    payload: ConversationAppendMessageRequest,
) -> ConversationSourceAppendCommand:
    return ConversationSourceAppendCommand(
        user_id=user_id,
        agent_id=payload.agent_id,
        project_id=payload.project_id,
        conversation_id=conversation_id,
        message=ConversationMessageRecord(**payload.message.model_dump(mode="python", exclude_none=True)),
    )


def conversation_get_query_to_query(
    *,
    user_id: str,
    conversation_id: str,
    payload: ConversationGetQuery,
) -> ConversationSourceGetQuery:
    return ConversationSourceGetQuery(user_id=user_id, conversation_id=conversation_id)


def conversation_view_to_response(view: ConversationSourceView | dict[str, object]) -> ConversationSourceResponse:
    if isinstance(view, dict):
        view = ConversationSourceView.model_validate(view)
    return ConversationSourceResponse(
        conversation_id=view.conversation_id,
        type=view.type,
        title=view.title,
        user_id=view.user_id,
        agent_id=view.agent_id,
        project_id=view.project_id,
        external_source=view.external_source,
        external_session_id=view.external_session_id,
        message_count=view.message_count,
        modalities=list(view.modalities),
        version=view.version,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


async def memory_create_request_to_command(payload: MemoryCreateRequest) -> MemoryWriteCommand:
    file_content: str | None = None
    file_name: str | None = None
    if payload.file is not None:
        raw = await payload.file.read()
        file_name = getattr(payload.file, "filename", None)
        file_content = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")

    return MemoryWriteCommand(
        content=payload.content or None,
        file_content=file_content,
        file_name=file_name,
        project_id=payload.project_id,
        user_id=payload.user_id,
        agent_id=payload.agent_id,
        summary_enabled=payload.summary_enabled,
        memory_source=payload.memory_source,
    )


def task_create_request_to_command(payload: TaskCreateRequest) -> MemoryTaskCreateCommand:
    return MemoryTaskCreateCommand(
        trigger_type=MemoryTriggerType(payload.trigger_type),
        user_id=payload.user_id,
        agent_id=payload.agent_id,
        project_id=payload.project_id,
        source_ref=MemorySourceRef(**payload.source_ref.model_dump(mode="python", exclude_none=True)),
    )


def memory_retrieve_request_to_query(payload: MemoryRetrieveRequest) -> MemoryRetrieveQuery:
    return MemoryRetrieveQuery(
        query=payload.query,
        user_id=payload.user_id,
        agent_id=payload.agent_id,
        project_id=payload.project_id,
        retrieve_type=payload.retrieve_type,
        top_k=payload.top_k,
        score_threshold=payload.score_threshold,
        filters=payload.filters,
    )


def retrieved_memories_to_response(items: list[MemoryRetrievedMemory]) -> list[MemoryRetrieveResponse]:
    return [
        MemoryRetrieveResponse.from_memory(
            content=item.content,
            memory_id=item.memory_id,
            score=item.score,
            metadata=item.metadata,
        )
        for item in items
    ]
