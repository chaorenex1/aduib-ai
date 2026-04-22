from __future__ import annotations

import datetime
from typing import Any

from models import MemoryConversation, get_db

from .contracts import ConversationMessageRef, ConversationSourceView


class ConversationRepository:
    @classmethod
    def get_conversation(
        cls,
        *,
        user_id: str,
        conversation_id: str,
    ) -> ConversationSourceView | None:
        with get_db() as session:
            row = (
                session.query(MemoryConversation)
                .filter(
                    MemoryConversation.user_id == user_id,
                    MemoryConversation.conversation_id == conversation_id,
                    MemoryConversation.deleted_at.is_(None),
                )
                .first()
            )
            return cls._to_view(row) if row else None

    @classmethod
    def create_conversation(
        cls,
        *,
        conversation_id: str,
        external_source: str,
        external_session_id: str,
        user_id: str,
        agent_id: str | None,
        project_id: str | None,
        title: str | None,
        metadata: dict[str, Any],
        message_store_uri: str,
        message_store_path: str | None,
        content_sha256: str,
        size_bytes: int,
        message_count: int,
        modalities: list[str],
        first_message_at: datetime.datetime | None,
        last_message_at: datetime.datetime | None,
    ) -> ConversationSourceView:
        now = datetime.datetime.now(datetime.UTC)
        with get_db() as session:
            row = MemoryConversation(
                conversation_id=conversation_id,
                external_source=external_source,
                external_session_id=external_session_id,
                user_id=user_id,
                agent_id=agent_id,
                project_id=project_id,
                title=title,
                metadata_json=metadata,
                message_store_type="jsonl",
                message_store_uri=message_store_uri,
                message_store_path=message_store_path,
                content_sha256=content_sha256,
                size_bytes=size_bytes,
                message_count=message_count,
                modalities=modalities,
                version=1,
                status="active",
                first_message_at=first_message_at,
                last_message_at=last_message_at,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return cls._to_view(row)

    @classmethod
    def update_conversation_after_append(
        cls,
        *,
        user_id: str,
        conversation_id: str,
        content_sha256: str,
        size_bytes: int,
        message_count: int,
        modalities: list[str],
        last_message_at: datetime.datetime | None,
    ) -> ConversationSourceView:
        with get_db() as session:
            row = (
                session.query(MemoryConversation)
                .filter(
                    MemoryConversation.user_id == user_id,
                    MemoryConversation.conversation_id == conversation_id,
                    MemoryConversation.deleted_at.is_(None),
                )
                .first()
            )
            if row is None:
                raise LookupError("conversation metadata not found")

            row.content_sha256 = content_sha256
            row.size_bytes = size_bytes
            row.message_count = message_count
            row.modalities = modalities
            row.last_message_at = last_message_at
            row.version = int(row.version or 1) + 1
            row.updated_at = datetime.datetime.now(datetime.UTC)
            session.commit()
            session.refresh(row)
            return cls._to_view(row)

    @staticmethod
    def _to_view(row: MemoryConversation) -> ConversationSourceView:
        return ConversationSourceView(
            conversation_id=row.conversation_id,
            type="conversation",
            title=row.title,
            user_id=row.user_id,
            agent_id=row.agent_id,
            project_id=row.project_id,
            external_source=row.external_source,
            external_session_id=row.external_session_id,
            message_ref=ConversationMessageRef(
                type=row.message_store_type,
                uri=row.message_store_uri,
                path=row.message_store_path,
                sha256=row.content_sha256,
            ),
            message_count=int(row.message_count or 0),
            modalities=list(row.modalities or []),
            version=int(row.version or 1),
            created_at=row.created_at.isoformat() if row.created_at else None,
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
        )
