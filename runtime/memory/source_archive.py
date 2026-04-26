from __future__ import annotations

import hashlib
import json

from component.storage.base_storage import storage_manager
from runtime.memory.base.contracts import (
    ArchivedSourceRef,
    MemoryTaskCreateCommand,
    MemoryWriteCommand,
    MemoryWriteTaskView,
)
from service.memory import SessionMessageRepository
from service.memory.base.enums import MemoryTriggerType
from service.memory.base.errors import MemoryArchiveError, MemoryValidationError
from service.memory.base.paths import (
    build_memory_api_conversation_archive_path,
    build_project_memory_import_archive_path,
    build_session_commit_archive_path,
)


class MemorySourceArchiveRuntime:

    @staticmethod
    def freeze_memory_api_conversation_source(
        task: MemoryWriteTaskView,
    ) -> ArchivedSourceRef:
        if str(task.source_ref.type or "").strip() == "project_memory_import":
            return MemorySourceArchiveRuntime.freeze_project_memory_import_source(task)

        from service.memory import ConversationRepository

        conversation = ConversationRepository.get_conversation(
            user_id=str(task.user_id or "").strip(),
            conversation_id=task.source_ref.conversation_id,
        )
        if conversation is None:
            raise MemoryValidationError("conversation source_ref not found for user")
        conversation_agent_id = getattr(conversation, "agent_id", None)
        conversation_project_id = getattr(conversation, "project_id", None)
        if task.agent_id is not None and conversation_agent_id is not None and task.agent_id != conversation_agent_id:
            raise MemoryValidationError("conversation source_ref agent_id does not match current scope")
        if (
            task.project_id is not None
            and conversation_project_id is not None
            and task.project_id != conversation_project_id
        ):
            raise MemoryValidationError("conversation source_ref project_id does not match current scope")

        live_uri = str(conversation.message_ref.uri or "").strip()
        if not live_uri:
            raise MemoryValidationError("conversation source does not have a readable jsonl uri")

        try:
            archive_text = storage_manager.read_text(live_uri)
        except Exception as exc:
            raise MemoryArchiveError(f"failed to read conversation source: {live_uri}") from exc

        archive_path = build_memory_api_conversation_archive_path(
            user_id=str(task.user_id or "").strip(),
            conversation_id=conversation.conversation_id,
            task_id=task.task_id,
        )
        return MemorySourceArchiveRuntime._write_archive_bytes(
            archive_path=archive_path,
            archive_text=archive_text,
            archive_type="application/x-ndjson",
        )

    @staticmethod
    def freeze_project_memory_import_source(
        task: MemoryWriteTaskView,
    ) -> ArchivedSourceRef:
        project_id = str(task.project_id or task.source_ref.project_id or "").strip()
        if not project_id:
            raise MemoryValidationError("project_memory_import requires project_id")
        payload = task.source_ref.project_payload or {}
        if not isinstance(payload, dict):
            raise MemoryValidationError("project_memory_import requires object project_payload")
        snapshot = {
            "trigger_type": MemoryTriggerType.MEMORY_API.value,
            "task_id": task.task_id,
            "trace_id": task.trace_id,
            "scope": {
                "user_id": task.user_id,
                "agent_id": task.agent_id,
                "project_id": project_id,
            },
            "source_ref": task.source_ref.model_dump(mode="python", exclude_none=True),
            "payload": payload,
        }
        archive_text = json.dumps(snapshot, ensure_ascii=False, indent=2)
        archive_path = build_project_memory_import_archive_path(
            user_id=str(task.user_id or "").strip(),
            project_id=project_id,
            task_id=task.task_id,
        )
        return MemorySourceArchiveRuntime._write_archive(
            archive_path=archive_path,
            archive_text=archive_text,
        )

    @staticmethod
    def delete_archive(archive_ref: ArchivedSourceRef | None) -> None:
        if archive_ref is None:
            return
        try:
            if storage_manager.exists(archive_ref.path):
                storage_manager.delete(archive_ref.path)
        except Exception as exc:
            raise MemoryArchiveError(f"failed to delete memory source archive: {archive_ref.path}") from exc

    @staticmethod
    async def archive_session_commit(
        payload: MemoryTaskCreateCommand,
        *,
        task_id: str,
        trace_id: str,
    ) -> ArchivedSourceRef:
        session_key = MemorySourceArchiveRuntime._resolve_session_key(payload)
        agent_session_id = MemorySourceArchiveRuntime._resolve_agent_session_id(payload)
        messages = MemorySourceArchiveRuntime._load_session_messages(
            agent_session_id=agent_session_id,
            user_id=payload.user_id,
            agent_id=payload.agent_id,
        )
        if not messages:
            raise MemoryValidationError(f"no conversation messages found for session_commit source: {session_key}")

        snapshot = {
            "trigger_type": MemoryTriggerType.SESSION_COMMIT.value,
            "task_id": task_id,
            "trace_id": trace_id,
            "scope": {
                "user_id": payload.user_id,
                "agent_id": payload.agent_id,
                "project_id": payload.project_id,
            },
            "source_ref": payload.source_ref.model_dump(mode="python", exclude_none=True),
            "session_snapshot": {
                "session_key": session_key,
                "agent_session_id": agent_session_id,
                "message_count": len(messages),
                "messages": messages,
            },
        }
        archive_text = json.dumps(snapshot, ensure_ascii=False, indent=2)
        archive_path = build_session_commit_archive_path(
            user_id=payload.user_id,
            session_key=session_key,
            task_id=task_id,
        )
        return MemorySourceArchiveRuntime._write_archive(archive_path=archive_path, archive_text=archive_text)

    @staticmethod
    def _write_archive(*, archive_path: str, archive_text: str) -> ArchivedSourceRef:
        return MemorySourceArchiveRuntime._write_archive_bytes(
            archive_path=archive_path,
            archive_text=archive_text,
            archive_type="application/json",
        )

    @staticmethod
    def _write_archive_bytes(*, archive_path: str, archive_text: str, archive_type: str) -> ArchivedSourceRef:
        try:
            storage_manager.write_text_atomic(archive_path, archive_text)
        except Exception as exc:
            raise MemoryArchiveError(f"failed to archive memory source: {archive_path}") from exc
        return ArchivedSourceRef(
            path=archive_path,
            type=archive_type,
            storage="default",
            content_sha256=hashlib.sha256(archive_text.encode("utf-8")).hexdigest(),
            size_bytes=len(archive_text.encode("utf-8")),
        )

    @staticmethod
    def _resolve_session_key(payload: MemoryTaskCreateCommand) -> str:
        return payload.source_ref.external_session_id or payload.source_ref.conversation_id

    @staticmethod
    def _resolve_agent_session_id(payload: MemoryTaskCreateCommand) -> int:
        candidates = [payload.source_ref.external_session_id, payload.source_ref.conversation_id]
        for candidate in candidates:
            if candidate is None:
                continue
            text = str(candidate).strip()
            if text.isdigit():
                return int(text)
            if text.startswith("session-") and text[8:].isdigit():
                return int(text[8:])
        raise MemoryValidationError("session_commit requires numeric source_ref.conversation_id or external_session_id")

    @staticmethod
    def _load_session_messages(
        *,
        agent_session_id: int,
        user_id: str,
        agent_id: str | None,
    ) -> list[dict[str, object]]:
        return SessionMessageRepository.list_session_messages(
            agent_session_id=agent_session_id,
            user_id=user_id,
            agent_id=agent_id,
        )

    @staticmethod
    async def _extract_payload_text(payload: MemoryWriteCommand) -> str:
        if payload.content:
            return payload.content
        if payload.file_content is None:
            raise MemoryValidationError("Either content or file must be provided for memory storage.")
        return payload.file_content
