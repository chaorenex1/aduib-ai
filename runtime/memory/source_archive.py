from __future__ import annotations

import hashlib
import json

from component.storage.base_storage import storage_manager
from service.memory import SessionMessageRepository
from service.memory.base.contracts import ArchivedSourceRef, MemoryTaskCreateCommand, MemoryWriteCommand
from service.memory.base.enums import MemoryTriggerType
from service.memory.base.errors import MemoryArchiveError, MemoryValidationError
from service.memory.base.paths import build_memory_api_archive_path, build_session_commit_archive_path


class MemorySourceArchiveRuntime:
    @staticmethod
    async def archive_memory_api(
        payload: MemoryWriteCommand,
        *,
        task_id: str,
        trace_id: str,
    ) -> ArchivedSourceRef:
        content = await MemorySourceArchiveRuntime._extract_payload_text(payload)
        snapshot = {
            "trigger_type": MemoryTriggerType.MEMORY_API.value,
            "task_id": task_id,
            "trace_id": trace_id,
            "scope": {
                "user_id": payload.user_id,
                "agent_id": payload.agent_id,
                "project_id": payload.project_id,
            },
            "payload": {
                "content": content,
                "memory_source": payload.memory_source,
                "summary_enabled": payload.summary_enabled,
                "file_name": payload.file_name,
            },
        }
        archive_text = json.dumps(snapshot, ensure_ascii=False, indent=2)
        archive_path = build_memory_api_archive_path(user_id=payload.user_id, task_id=task_id)
        return MemorySourceArchiveRuntime._write_archive(archive_path=archive_path, archive_text=archive_text)

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
        try:
            storage_manager.write_text_atomic(archive_path, archive_text)
        except Exception as exc:
            raise MemoryArchiveError(f"failed to archive memory source: {archive_path}") from exc
        return ArchivedSourceRef(
            path=archive_path,
            type="application/json",
            storage="default",
            content_sha256=hashlib.sha256(archive_text.encode("utf-8")).hexdigest(),
            size_bytes=len(archive_text.encode("utf-8")),
        )

    @staticmethod
    def _resolve_session_key(payload: MemoryTaskCreateCommand) -> str:
        return payload.source_ref.external_session_id or payload.source_ref.id

    @staticmethod
    def _resolve_agent_session_id(payload: MemoryTaskCreateCommand) -> int:
        candidates = [payload.source_ref.external_session_id, payload.source_ref.id]
        for candidate in candidates:
            if candidate is None:
                continue
            text = str(candidate).strip()
            if text.isdigit():
                return int(text)
            if text.startswith("session-") and text[8:].isdigit():
                return int(text[8:])
        raise MemoryValidationError("session_commit requires numeric source_ref.id or external_session_id")

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
