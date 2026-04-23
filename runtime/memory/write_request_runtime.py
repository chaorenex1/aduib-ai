from __future__ import annotations

from runtime.tasks.celery_app import celery_app
from service.memory import ConversationRepository, MemoryWriteTaskService
from service.memory.base.builders import (
    build_memory_api_idempotency_key,
    build_queue_payload,
    build_task_request_idempotency_key,
    new_task_id,
    new_trace_id,
)
from service.memory.base.contracts import (
    ConversationMessageRef,
    MemorySourceRef,
    MemoryTaskCreateCommand,
    MemoryWriteAccepted,
    MemoryWriteCommand,
    MemoryWriteTaskView,
)
from service.memory.base.enums import MemoryQueueStatus, MemoryTaskStatus, MemoryTriggerType
from service.memory.base.errors import MemoryValidationError, MemoryWritePublishError, MemoryWriteTaskReplayError

from .source_archive import MemorySourceArchiveRuntime

REQUEST_STATE_TRANSITIONS = {
    ("accept", MemoryTaskStatus.ACCEPTED, MemoryQueueStatus.PUBLISH_PENDING): (
        MemoryTaskStatus.ACCEPTED,
        MemoryQueueStatus.QUEUED,
    ),
    ("publish_failed", MemoryTaskStatus.ACCEPTED, MemoryQueueStatus.PUBLISH_PENDING): (
        MemoryTaskStatus.PUBLISH_FAILED,
        MemoryQueueStatus.PUBLISH_FAILED,
    ),
    ("replay", MemoryTaskStatus.PUBLISH_FAILED, MemoryQueueStatus.PUBLISH_FAILED): (
        MemoryTaskStatus.ACCEPTED,
        MemoryQueueStatus.PUBLISH_PENDING,
    ),
}


class MemoryWriteRequestRuntime:
    @classmethod
    async def accept_memory_write(cls, payload: MemoryWriteCommand) -> MemoryWriteAccepted:
        if not payload.content and not payload.file_content:
            raise MemoryValidationError("Either content or file must be provided for memory storage.")

        task_id = new_task_id()
        trace_id = new_trace_id()
        archive_ref = await MemorySourceArchiveRuntime.archive_memory_api(payload, task_id=task_id, trace_id=trace_id)
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
        queued_task = cls._publish_task(task)
        return cls._accepted_response(queued_task)

    @classmethod
    async def accept_task_request(cls, payload: MemoryTaskCreateCommand) -> MemoryWriteAccepted:
        task_id = new_task_id()
        trace_id = new_trace_id()
        archive_ref = None
        source_ref = payload.source_ref
        if payload.trigger_type == MemoryTriggerType.SESSION_COMMIT:
            archive_ref = await MemorySourceArchiveRuntime.archive_session_commit(
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
        queued_task = cls._publish_task(task)
        return cls._accepted_response(queued_task)

    @classmethod
    def replay_task(cls, task_id: str, actor: str | None = None) -> MemoryWriteTaskView:
        task = MemoryWriteTaskService.get_task(task_id)
        cls._assert_transition("replay", task)
        replay_ready_task = MemoryWriteTaskService.prepare_replay(task_id, actor=actor)
        return cls._publish_task(replay_ready_task)

    @classmethod
    def _publish_task(cls, task: MemoryWriteTaskView) -> MemoryWriteTaskView:
        cls._assert_transition("accept", task)
        try:
            async_result = celery_app.send_task(
                MemoryWriteTaskService.get_queue_task_name(),
                kwargs={"task_id": task.task_id},
            )
        except Exception as exc:
            failed_task = MemoryWriteTaskService.mark_publish_failed(task.task_id, str(exc))
            cls._assert_transition("publish_failed", failed_task)
            raise MemoryWritePublishError(str(exc), task_id=task.task_id) from exc

        queue_payload = build_queue_payload(celery_message_id=async_result.id)
        queued_task = MemoryWriteTaskService.mark_queued(task.task_id, queue_payload=queue_payload)
        cls._assert_transition("accept", queued_task)
        return queued_task

    @staticmethod
    def _accepted_response(task: MemoryWriteTaskView) -> MemoryWriteAccepted:
        return MemoryWriteAccepted(
            task_id=task.task_id,
            trace_id=task.trace_id,
            trigger_type=task.trigger_type,
            user_id=task.user_id,
            agent_id=task.agent_id,
            project_id=task.project_id,
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

    @staticmethod
    def _assert_transition(action: str, task: MemoryWriteTaskView) -> None:
        key = (action, task.status, task.queue_status)
        if key in REQUEST_STATE_TRANSITIONS:
            return
        if action == "accept" and task.queue_status == MemoryQueueStatus.QUEUED:
            return
        if action == "replay":
            raise MemoryWriteTaskReplayError("only publish_failed tasks can be replayed")
        raise MemoryWriteTaskReplayError(
            f"memory write request transition blocked: action={action}, "
            f"status={task.status}, queue_status={task.queue_status}"
        )
