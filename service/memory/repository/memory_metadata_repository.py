from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_

from models import MemoryIndex, get_db
from service.error.base import RepositoryBase


class MemoryMetadataRepository(RepositoryBase):
    @staticmethod
    def persist_projection(*, task_id: str, projection: dict) -> None:
        with get_db() as session:
            scope_paths = sorted(set(projection.get("scope_paths") or []))
            memory_index_records = projection.get("memory_index") or []

            for scope_path in scope_paths:
                session.query(MemoryIndex).filter(_scope_path_filter(scope_path)).delete(synchronize_session=False)

            if memory_index_records:
                session.add_all(MemoryIndex(**item) for item in memory_index_records)

            session.commit()

    @staticmethod
    def list_memory_index(
        *,
        user_id: str,
        agent_id: str | None,
        project_id: str | None,
        memory_type: str | None,
        path_prefix: str | None,
        updated_after: str | None,
        cursor: str | None,
        limit: int,
    ) -> list[dict]:
        with get_db() as session:
            query = session.query(MemoryIndex).filter(MemoryIndex.user_id == user_id)
            if agent_id is None:
                query = query.filter(MemoryIndex.agent_id.is_(None))
            else:
                query = query.filter(MemoryIndex.agent_id == agent_id)
            if project_id is not None:
                query = query.filter(MemoryIndex.project_id == project_id)
            if memory_type:
                query = query.filter(MemoryIndex.memory_type == memory_type)
            if path_prefix:
                query = query.filter(MemoryIndex.file_path.like(f"{path_prefix}%"))
            if updated_after:
                query = query.filter(_sort_expr() >= _parse_datetime(updated_after))
            if cursor:
                cursor_dt, cursor_memory_id = _parse_cursor(cursor)
                query = query.filter(
                    or_(
                        _sort_expr() < cursor_dt,
                        and_(_sort_expr() == cursor_dt, MemoryIndex.memory_id < cursor_memory_id),
                    )
                )
            items = query.order_by(_sort_expr().desc(), MemoryIndex.memory_id.desc()).limit(limit).all()
            return [MemoryMetadataRepository._memory_index_to_dict(item) for item in items]

    @staticmethod
    def get_memory_by_id(memory_id: str, *, user_id: str, agent_id: str | None, project_id: str | None) -> dict | None:
        with get_db() as session:
            query = session.query(MemoryIndex).filter(
                MemoryIndex.memory_id == memory_id,
                MemoryIndex.user_id == user_id,
            )
            if agent_id is None:
                query = query.filter(MemoryIndex.agent_id.is_(None))
            else:
                query = query.filter(MemoryIndex.agent_id == agent_id)
            if project_id is not None:
                query = query.filter(MemoryIndex.project_id == project_id)
            item = query.first()
            return MemoryMetadataRepository._memory_index_to_dict(item) if item else None

    @staticmethod
    def get_memory_by_path(path: str, *, user_id: str, agent_id: str | None, project_id: str | None) -> dict | None:
        with get_db() as session:
            query = session.query(MemoryIndex).filter(MemoryIndex.file_path == path, MemoryIndex.user_id == user_id)
            if agent_id is None:
                query = query.filter(MemoryIndex.agent_id.is_(None))
            else:
                query = query.filter(MemoryIndex.agent_id == agent_id)
            if project_id is not None:
                query = query.filter(MemoryIndex.project_id == project_id)
            item = query.first()
            return MemoryMetadataRepository._memory_index_to_dict(item) if item else None

    @staticmethod
    def _memory_index_to_dict(item: MemoryIndex) -> dict:
        return {
            "memory_id": item.memory_id,
            "memory_type": item.memory_type,
            "memory_level": item.memory_level,
            "user_id": item.user_id,
            "agent_id": item.agent_id,
            "project_id": item.project_id,
            "scope_type": item.scope_type,
            "directory_path": item.directory_path,
            "file_path": item.file_path,
            "filename": item.filename,
            "status": item.status,
            "tags": item.tags or [],
            "file_sha256": item.file_sha256,
            "content_bytes": item.content_bytes,
            "projection_payload": item.projection_payload or {},
            "memory_created_at": item.memory_created_at.isoformat() if item.memory_created_at else None,
            "memory_updated_at": item.memory_updated_at.isoformat() if item.memory_updated_at else None,
            "indexed_at": item.indexed_at.isoformat() if item.indexed_at else None,
            "refreshed_by_task_id": item.refreshed_by_task_id,
        }


def _scope_path_filter(scope_path: str):
    normalized = str(scope_path or "").strip().strip("/")
    if not normalized:
        return True
    return or_(MemoryIndex.file_path == normalized, MemoryIndex.file_path.like(f"{normalized}/%"))


def _sort_expr():
    return func.coalesce(MemoryIndex.memory_updated_at, MemoryIndex.indexed_at)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(str(value))


def _parse_cursor(cursor: str) -> tuple[datetime, str]:
    timestamp, memory_id = str(cursor).split("::", 1)
    return _parse_datetime(timestamp), memory_id
