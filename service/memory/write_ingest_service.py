from __future__ import annotations

from .base.builders import (
    build_memory_api_idempotency_key,
    build_task_request_idempotency_key,
    new_task_id,
    new_trace_id,
)
from .base.contracts import (
    ConversationMessageRef,
    MemorySourceRef,
    MemoryTaskCreateCommand,
    MemoryWriteAccepted,
    MemoryWriteCommand,
)
from .base.enums import MemoryTriggerType
from .base.errors import MemoryValidationError, MemoryWritePublishError
from .conversation_repository import ConversationRepository
from .source_archive_service import MemorySourceArchiveService
from .write_task_service import MemoryWriteTaskService


class MemoryWriteIngestService:
    @classmethod
    async def accept_memory_write(cls, payload: MemoryWriteCommand) -> MemoryWriteAccepted:
        if not payload.content and not payload.file_content:
            raise MemoryValidationError("Either content or file must be provided for memory storage.")

        task_id = new_task_id()
        trace_id = new_trace_id()
        archive_ref = await MemorySourceArchiveService.archive_memory_api(payload, task_id=task_id, trace_id=trace_id)
        source_ref = MemorySourceRef(
            type=MemoryTriggerType.MEMORY_API.value,
            id=task_id,
            path=archive_ref.path,
        )
        task = MemoryWriteTaskService.create_task(
            task_id=task_id,
            trigger_type=MemoryTriggerType.MEMORY_API,
            user_id=payload.user_id,
            agent_id=payload.agent_id,
            project_id=payload.project_id,
            trace_id=trace_id,
            idempotency_key=build_memory_api_idempotency_key(payload),
            source_ref=source_ref,
            archive_ref=archive_ref,
        )
        try:
            queued_task = MemoryWriteTaskService.publish_task(task.task_id)
        except Exception as exc:
            raise MemoryWritePublishError(str(exc), task_id=task.task_id) from exc
        return cls._accepted_response(queued_task)

    @classmethod
    async def accept_task_request(cls, payload: MemoryTaskCreateCommand) -> MemoryWriteAccepted:
        task_id = new_task_id()
        trace_id = new_trace_id()
        archive_ref = None
        source_ref = payload.source_ref
        if payload.trigger_type == MemoryTriggerType.SESSION_COMMIT:
            archive_ref = await MemorySourceArchiveService.archive_session_commit(
                payload,
                task_id=task_id,
                trace_id=trace_id,
            )
        elif payload.source_ref.type == "conversation":
            source_ref = cls._normalize_conversation_source_ref(payload)
        task = MemoryWriteTaskService.create_task(
            task_id=task_id,
            trigger_type=payload.trigger_type,
            user_id=payload.user_id,
            agent_id=payload.agent_id,
            project_id=payload.project_id,
            trace_id=trace_id,
            idempotency_key=build_task_request_idempotency_key(payload),
            source_ref=source_ref,
            archive_ref=archive_ref,
        )
        try:
            queued_task = MemoryWriteTaskService.publish_task(task.task_id)
        except Exception as exc:
            raise MemoryWritePublishError(str(exc), task_id=task.task_id) from exc
        return cls._accepted_response(queued_task)

    @staticmethod
    def _accepted_response(task) -> MemoryWriteAccepted:
        return MemoryWriteAccepted(
            task_id=task.task_id,
            trace_id=task.trace_id,
            trigger_type=task.trigger_type,
            status=task.status,
            phase=task.phase,
            queue_status=task.queue_status,
            source_ref=task.source_ref,
            archive_ref=task.archive_ref,
        )

    @staticmethod
    def _normalize_conversation_source_ref(payload: MemoryTaskCreateCommand) -> MemorySourceRef:
        source_ref = payload.source_ref
        if source_ref.storage != "pg_jsonl":
            raise MemoryValidationError("conversation source_ref requires storage=pg_jsonl")
        if source_ref.version is None:
            raise MemoryValidationError("conversation source_ref requires version")
        if source_ref.message_ref is None:
            raise MemoryValidationError("conversation source_ref requires message_ref")

        conversation = ConversationRepository.get_conversation(
            user_id=payload.user_id,
            conversation_id=source_ref.id,
        )
        if conversation is None:
            raise MemoryValidationError("conversation source_ref not found for user")
        if source_ref.version != conversation.version:
            raise MemoryValidationError("conversation source_ref version does not match current metadata")
        if source_ref.external_source and source_ref.external_source != conversation.external_source:
            raise MemoryValidationError("conversation source_ref external_source does not match current metadata")
        if source_ref.external_session_id and source_ref.external_session_id != conversation.external_session_id:
            raise MemoryValidationError("conversation source_ref external_session_id does not match current metadata")

        provided_message_ref = ConversationMessageRef(**source_ref.message_ref)
        if provided_message_ref.uri != conversation.message_ref.uri:
            raise MemoryValidationError("conversation source_ref message_ref.uri does not match current metadata")
        if provided_message_ref.sha256 and provided_message_ref.sha256 != conversation.message_ref.sha256:
            raise MemoryValidationError("conversation source_ref message_ref.sha256 does not match current metadata")

        return MemorySourceRef(
            type="conversation",
            id=conversation.conversation_id,
            storage="pg_jsonl",
            version=conversation.version,
            external_source=conversation.external_source,
            external_session_id=conversation.external_session_id,
            message_ref=conversation.message_ref.model_dump(mode="python", exclude_none=True),
        )
