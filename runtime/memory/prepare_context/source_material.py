from __future__ import annotations

from typing import Any

from runtime.memory.base.contracts import ArchivedSourceRef
from runtime.memory.base.enums import MemoryTriggerType
from runtime.memory.prepare_context.common import (
    collect_text_blocks,
    load_archive_snapshot,
    normalize_message,
)
from runtime.memory.prepare_context.types import NormalizedSourceMaterial


class SourceMaterialNormalizer:

    def __init__(self,
                 trigger_type: MemoryTriggerType,
                 archive_ref: ArchivedSourceRef,
                 ):
        self.trigger_type = trigger_type
        self.archive_ref = archive_ref

    def normalize(self) -> NormalizedSourceMaterial:

        archived_snapshot, source_hash = load_archive_snapshot(self.archive_ref)
        trigger_type = str(self.trigger_type)
        if trigger_type == "memory_api":
            return self._normalize_memory_api_source(archived_snapshot=archived_snapshot, source_hash=source_hash)

        if trigger_type == "session_commit":
            return self._normalize_session_commit_source(archived_snapshot=archived_snapshot, source_hash=source_hash)

        raise ValueError(f"unsupported memory write source kind: {trigger_type}")

    def _normalize_memory_api_source(
        self,
        *,
        archived_snapshot: dict[str, Any],
        source_hash: str,
    ) -> NormalizedSourceMaterial:
        source_ref = archived_snapshot.get("source_ref") or {}
        if str(source_ref.get("type") or "").strip() == "project_memory_import":
            return self._normalize_project_memory_import_source(
                archived_snapshot=archived_snapshot,
                source_hash=source_hash,
            )
        payload = archived_snapshot.get("payload") or {}
        content = str(payload.get("content") or "").strip()
        messages = [{"role": "user", "content": content, "source_kind": "memory_api"}] if content else []
        return self._build_material(
            source_kind="memory_api",
            source_hash=source_hash,
            messages=messages,
            text_blocks=[content] if content else [],
            archived_snapshot=archived_snapshot,
            scope=archived_snapshot.get("scope"),
        )

    def _normalize_project_memory_import_source(
        self,
        *,
        archived_snapshot: dict[str, Any],
        source_hash: str,
    ) -> NormalizedSourceMaterial:
        payload = archived_snapshot.get("payload") or {}
        raw_items = payload.get("items") or []
        messages: list[dict[str, Any]] = []
        text_blocks: list[str] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            parts = item.get("content_parts") or []
            texts = [
                str(part.get("text") or "").strip()
                for part in parts
                if isinstance(part, dict) and str(part.get("type") or "").strip() == "text"
            ]
            item_text = "\n".join(text for text in texts if text).strip()
            title = str(item.get("title") or "").strip()
            if title or item_text:
                messages.append(
                    {
                        "role": "user",
                        "content": "\n\n".join(part for part in [title, item_text] if part).strip(),
                        "source_kind": "project_memory_import",
                    }
                )
            if title:
                text_blocks.append(title)
            if item_text:
                text_blocks.append(item_text)

        return self._build_material(
            source_kind="project_memory_import",
            source_hash=source_hash,
            messages=messages,
            text_blocks=text_blocks,
            archived_snapshot=archived_snapshot,
            scope=archived_snapshot.get("scope"),
        )

    def _normalize_session_commit_source(
        self,
        *,
        archived_snapshot: dict[str, Any],
        source_hash: str,
    ) -> NormalizedSourceMaterial:
        session_snapshot = archived_snapshot.get("session_snapshot") or {}
        raw_messages = session_snapshot.get("messages") or []
        messages = [normalize_message(message) for message in raw_messages if isinstance(message, dict)]
        return self._build_material(
            source_kind="session_commit",
            source_hash=source_hash,
            messages=messages,
            session_snapshot=session_snapshot,
            archived_snapshot=archived_snapshot,
            scope=archived_snapshot.get("scope"),
        )

    def _build_material(
        self,
        *,
        source_kind: str,
        source_hash: str,
        messages: list[dict[str, Any]],
        text_blocks: list[str] | None = None,
        scope: dict[str, Any] | None = None,
        conversation_snapshot: dict[str, Any] | None = None,
        session_snapshot: dict[str, Any] | None = None,
        archived_snapshot: dict[str, Any] | None = None,
    ) -> NormalizedSourceMaterial:
        resolved_scope = self._resolve_scope(scope)
        return NormalizedSourceMaterial(
            source_kind=source_kind,
            source_hash=source_hash,
            messages=messages,
            text_blocks=text_blocks if text_blocks is not None else collect_text_blocks(messages),
            language="unknown",
            conversation_snapshot=conversation_snapshot,
            session_snapshot=session_snapshot,
            archived_snapshot=archived_snapshot,
            user_id=resolved_scope["user_id"],
            agent_id=resolved_scope["agent_id"],
            project_id=resolved_scope["project_id"],
        )

    def _resolve_scope(self, scope: dict[str, Any] | None) -> dict[str, str | None]:
        snapshot_scope = scope if isinstance(scope, dict) else {}
        return {
            "user_id": snapshot_scope.get("user_id") or self.context.user_id,
            "agent_id": snapshot_scope.get("agent_id") or self.context.agent_id,
            "project_id": snapshot_scope.get("project_id") or self.context.project_id,
        }
