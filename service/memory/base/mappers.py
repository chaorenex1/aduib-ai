from __future__ import annotations

from controllers.memory.schemas import (
    ConversationAppendMessageRequest,
    ConversationCreateRequest,
    ConversationGetQuery,
    ConversationSourceResponse,
    ProjectImportRequest,
    TaskCreateRequest,
)

from .contracts import (
    ConversationMessageRecord,
    ConversationSourceAppendCommand,
    ConversationSourceCreateCommand,
    ConversationSourceGetQuery,
    ConversationSourceMetadata,
    ConversationSourceView,
    MemorySourceRef,
    MemoryTaskCreateCommand,
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


def task_create_request_to_command(payload: TaskCreateRequest) -> MemoryTaskCreateCommand:
    return MemoryTaskCreateCommand(
        trigger_type=MemoryTriggerType(payload.trigger_type),
        user_id=payload.user_id,
        agent_id=payload.agent_id,
        project_id=payload.project_id,
        source_ref=MemorySourceRef(**payload.source_ref.model_dump(mode="python", exclude_none=True)),
    )


def project_import_request_to_task_command(
    *,
    project_id: str,
    payload: ProjectImportRequest,
) -> MemoryTaskCreateCommand:
    if payload.project_id != project_id:
        raise ValueError("payload project_id does not match route project_id")

    return MemoryTaskCreateCommand(
        trigger_type=MemoryTriggerType.MEMORY_API,
        user_id=payload.user_id,
        agent_id=None,
        project_id=project_id,
        source_ref=MemorySourceRef(
            type="project_memory_import",
            project_id=project_id,
            project_payload={
                "items": [item.model_dump(mode="python", exclude_none=True) for item in payload.items],
                "metadata": payload.metadata.model_dump(mode="python", exclude_none=True) if payload.metadata else None,
            },
        ),
    )
