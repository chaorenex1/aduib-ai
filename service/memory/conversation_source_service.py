from __future__ import annotations

import json
from typing import Any

from component.storage.base_storage import storage_manager

from .base.base import MemoryServiceBase
from .base.contracts import (
    ConversationAppendResult,
    ConversationMessageRecord,
    ConversationSourceAppendCommand,
    ConversationSourceCreateCommand,
    ConversationSourceGetQuery,
    ConversationSourceView,
)
from .base.errors import (
    ConversationSourceConflictError,
    ConversationSourceCorruptedError,
    ConversationSourceError,
    ConversationSourceNotFoundError,
    ConversationSourceValidationError,
)
from .base.paths import build_conversation_id, build_conversation_source_path, parse_conversation_id
from .repository import ConversationRepository


class ConversationSourceService(MemoryServiceBase):
    @classmethod
    def create_conversation(cls, command: ConversationSourceCreateCommand) -> ConversationSourceView:
        conversation_id = build_conversation_id(
            external_source=command.external_source,
            external_session_id=command.external_session_id,
        )
        path = build_conversation_source_path(
            user_id=command.user_id,
            external_source=command.external_source,
            external_session_id=command.external_session_id,
        )
        existing = ConversationRepository.get_conversation(
            user_id=command.user_id,
            conversation_id=conversation_id,
        )
        if existing is not None:
            raise ConversationSourceConflictError(
                "conversation source already exists",
                details={"conversation_id": conversation_id},
            )
        if storage_manager.exists(path):
            raise ConversationSourceConflictError(
                "conversation message store already exists",
                details={"conversation_id": conversation_id, "message_store_uri": path},
            )

        records = [
            cls._build_record(
                conversation_id=conversation_id,
                message=message,
            )
            for message in command.messages
        ]
        metadata = command.metadata.model_dump(mode="python", exclude_none=True) if command.metadata else {}
        cls._write_records(path=path, records=records)
        aggregates = cls._compute_aggregates(records)
        return ConversationRepository.create_conversation(
            conversation_id=conversation_id,
            external_source=command.external_source,
            external_session_id=command.external_session_id,
            user_id=command.user_id,
            agent_id=command.agent_id,
            project_id=command.project_id,
            title=command.title,
            metadata=metadata,
            message_store_uri=path,
            message_store_path=path,
            content_sha256=aggregates["content_sha256"],
            size_bytes=aggregates["size_bytes"],
            message_count=aggregates["message_count"],
            modalities=aggregates["modalities"],
            first_message_at=aggregates["first_message_at"],
            last_message_at=aggregates["last_message_at"],
        )

    @classmethod
    def append_message(cls, command: ConversationSourceAppendCommand) -> ConversationAppendResult:
        metadata_view = ConversationRepository.get_conversation(
            user_id=command.user_id,
            conversation_id=command.conversation_id,
        )
        if metadata_view is None:
            raise ConversationSourceNotFoundError(
                "conversation source not found",
                details={"conversation_id": command.conversation_id},
            )

        cls._parse_canonical_conversation_id(command.conversation_id)
        cls._validate_scope_compatibility(command=command, metadata_view=metadata_view)
        path = metadata_view.message_ref.uri
        records = cls._load_records(path=path, expected_conversation_id=command.conversation_id)

        appended_record = cls._build_record(
            conversation_id=command.conversation_id,
            message=command.message,
        )
        records.append(appended_record)
        cls._write_records(path=path, records=records)
        aggregates = cls._compute_aggregates(records)
        view = ConversationRepository.update_conversation_after_append(
            user_id=command.user_id,
            conversation_id=command.conversation_id,
            content_sha256=aggregates["content_sha256"],
            size_bytes=aggregates["size_bytes"],
            message_count=aggregates["message_count"],
            modalities=aggregates["modalities"],
            last_message_at=aggregates["last_message_at"],
        )
        return ConversationAppendResult(
            conversation_id=view.conversation_id,
            appended=True,
            message_count=view.message_count,
            version=view.version,
            updated_at=view.updated_at,
        )

    @classmethod
    def get_conversation(cls, query: ConversationSourceGetQuery) -> ConversationSourceView:
        cls._parse_canonical_conversation_id(query.conversation_id)
        view = ConversationRepository.get_conversation(
            user_id=query.user_id,
            conversation_id=query.conversation_id,
        )
        if view is None:
            raise ConversationSourceNotFoundError(
                "conversation source not found",
                details={"conversation_id": query.conversation_id},
            )
        return view

    @staticmethod
    def _parse_canonical_conversation_id(conversation_id: str) -> tuple[str, str]:
        try:
            return parse_conversation_id(conversation_id)
        except ValueError as exc:
            raise ConversationSourceValidationError(str(exc), details={"conversation_id": conversation_id}) from exc

    @classmethod
    def _load_records(cls, *, path: str, expected_conversation_id: str) -> list[dict[str, Any]]:
        if not storage_manager.exists(path):
            raise ConversationSourceNotFoundError(
                "conversation source not found",
                details={"conversation_id": expected_conversation_id, "path": path},
            )

        try:
            raw_text = storage_manager.read_text(path)
        except Exception as exc:
            raise ConversationSourceError("failed to read conversation source", details={"path": path}) from exc

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        if not lines:
            raise ConversationSourceCorruptedError("conversation source is empty", details={"path": path})

        records: list[dict[str, Any]] = []
        for index, line in enumerate(lines, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ConversationSourceCorruptedError(
                    "conversation source contains invalid json",
                    details={"path": path, "line": index},
                ) from exc
            if not isinstance(record, dict):
                raise ConversationSourceCorruptedError(
                    "conversation source contains non-object records",
                    details={"path": path, "line": index},
                )
            if record.get("conversation_id") != expected_conversation_id:
                raise ConversationSourceCorruptedError(
                    "conversation source contains mixed conversation ids",
                    details={"path": path, "line": index},
                )
            records.append(record)
        return records

    @classmethod
    def _write_records(cls, *, path: str, records: list[dict[str, Any]]) -> None:
        content = cls.dump_jsonl(records)
        try:
            storage_manager.write_text_atomic(path, content)
        except Exception as exc:
            raise ConversationSourceError("failed to persist conversation source", details={"path": path}) from exc

    @classmethod
    def _compute_aggregates(cls, records: list[dict[str, Any]]) -> dict[str, Any]:
        if not records:
            raise ConversationSourceCorruptedError("conversation source is empty")

        content = cls.dump_jsonl(records)
        modalities = sorted(
            {
                str(part.get("type")).strip()
                for record in records
                for part in record.get("content_parts", [])
                if isinstance(part, dict) and str(part.get("type", "")).strip()
            }
        )
        created_values = [cls.parse_optional_datetime(record.get("created_at")) for record in records]
        created_values = [value for value in created_values if value is not None]
        return {
            "content_sha256": cls.sha256_text(content),
            "size_bytes": len(content.encode("utf-8")),
            "message_count": len(records),
            "modalities": modalities,
            "first_message_at": min(created_values) if created_values else None,
            "last_message_at": max(created_values) if created_values else None,
        }

    @classmethod
    def _validate_scope_compatibility(
        cls,
        *,
        command: ConversationSourceAppendCommand,
        metadata_view: ConversationSourceView,
    ) -> None:
        if metadata_view.user_id != command.user_id:
            raise ConversationSourceConflictError(
                "conversation source belongs to another user scope",
                details={"conversation_id": command.conversation_id},
            )
        if (
            command.agent_id is not None
            and metadata_view.agent_id is not None
            and command.agent_id != metadata_view.agent_id
        ):
            raise ConversationSourceConflictError(
                "conversation source agent scope does not match",
                details={"conversation_id": command.conversation_id},
            )
        if (
            command.project_id is not None
            and metadata_view.project_id is not None
            and command.project_id != metadata_view.project_id
        ):
            raise ConversationSourceConflictError(
                "conversation source project scope does not match",
                details={"conversation_id": command.conversation_id},
            )

    @classmethod
    def _build_record(
        cls,
        *,
        conversation_id: str,
        message: ConversationMessageRecord,
    ) -> dict[str, Any]:
        created_at = message.created_at or cls.utcnow().isoformat().replace("+00:00", "Z")
        return {
            "conversation_id": conversation_id,
            "role": message.role,
            "content_parts": [part.model_dump(mode="python", exclude_none=True) for part in message.content_parts],
            "created_at": created_at,
        }
