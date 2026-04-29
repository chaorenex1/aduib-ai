from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_

from models import MemoryIndex, MemoryNavigationIndex, get_db
from service.error.base import RepositoryBase


class MemoryMetadataRepository(RepositoryBase):
    @staticmethod
    def persist_projection(*, task_id: str, projection: dict) -> None:
        _ = task_id
        with get_db() as session:
            scope_paths = sorted(set(projection.get("scope_paths") or []))
            memory_index_records = projection.get("memory_index") or []

            for scope_path in scope_paths:
                session.query(MemoryIndex).filter(_scope_path_filter(MemoryIndex.file_path, scope_path)).delete(
                    synchronize_session=False
                )

            if memory_index_records:
                session.add_all(MemoryIndex(**item) for item in memory_index_records)

            session.commit()

    @staticmethod
    def replace_navigation_index_records(*, scope_paths: list[str], records: list[dict]) -> None:
        with get_db() as session:
            for scope_path in sorted(set(scope_paths)):
                session.query(MemoryNavigationIndex).filter(
                    _scope_path_filter(MemoryNavigationIndex.file_path, scope_path)
                ).delete(synchronize_session=False)

            if records:
                session.add_all(MemoryNavigationIndex(**item) for item in records)

            session.commit()

    @staticmethod
    def delete_navigation_index_by_scope(scope_paths: list[str]) -> None:
        with get_db() as session:
            for scope_path in sorted(set(scope_paths)):
                session.query(MemoryNavigationIndex).filter(
                    _scope_path_filter(MemoryNavigationIndex.file_path, scope_path)
                ).delete(synchronize_session=False)
            session.commit()

    @staticmethod
    def list_memory_index(
        *,
        user_id: str,
        project_id: str | None,
        memory_type: str | None,
        path_prefix: str | None,
        updated_after: str | None,
        cursor: str | None,
        limit: int,
    ) -> list[dict]:
        with get_db() as session:
            query = session.query(MemoryIndex).filter(MemoryIndex.user_id == user_id)
            if project_id is not None:
                query = query.filter(MemoryIndex.project_id == project_id)
            if memory_type:
                query = query.filter(MemoryIndex.memory_type == memory_type)
            if path_prefix:
                escaped = _escape_like(str(path_prefix))
                query = query.filter(MemoryIndex.file_path.like(f"{escaped}%", escape="\\"))
            if updated_after:
                query = query.filter(_memory_sort_expr() >= _parse_datetime(updated_after))
            if cursor:
                cursor_dt, cursor_memory_id = _parse_cursor(cursor)
                query = query.filter(
                    or_(
                        _memory_sort_expr() < cursor_dt,
                        and_(_memory_sort_expr() == cursor_dt, MemoryIndex.memory_id < cursor_memory_id),
                    )
                )
            items = query.order_by(_memory_sort_expr().desc(), MemoryIndex.memory_id.desc()).limit(limit).all()
            return [MemoryMetadataRepository._memory_index_to_dict(item) for item in items]

    @staticmethod
    def get_memory_by_id(memory_id: str, *, user_id: str, project_id: str | None) -> dict | None:
        with get_db() as session:
            query = session.query(MemoryIndex).filter(
                MemoryIndex.memory_id == memory_id,
                MemoryIndex.user_id == user_id,
            )
            if project_id is not None:
                query = query.filter(MemoryIndex.project_id == project_id)
            item = query.first()
            return MemoryMetadataRepository._memory_index_to_dict(item) if item else None

    @staticmethod
    def get_memory_by_path(path: str, *, user_id: str, project_id: str | None) -> dict | None:
        with get_db() as session:
            query = session.query(MemoryIndex).filter(MemoryIndex.file_path == path, MemoryIndex.user_id == user_id)
            if project_id is not None:
                query = query.filter(MemoryIndex.project_id == project_id)
            item = query.first()
            return MemoryMetadataRepository._memory_index_to_dict(item) if item else None

    @staticmethod
    def list_l0_navigation_rows(user_id: str, include_types: list[str] | None = None) -> list[dict]:
        with get_db() as session:
            query = session.query(MemoryNavigationIndex).filter(
                MemoryNavigationIndex.user_id == user_id,
                MemoryNavigationIndex.memory_level == "l0",
            )
            if include_types:
                query = query.filter(MemoryNavigationIndex.memory_type.in_(include_types))
            items = query.order_by(MemoryNavigationIndex.memory_updated_at.desc().nullslast()).all()
            return [MemoryMetadataRepository._navigation_index_to_dict(item) for item in items]

    @staticmethod
    def list_l0_l1_navigation_rows(user_id: str, include_types: list[str] | None = None) -> list[dict]:
        with get_db() as session:
            query = session.query(MemoryNavigationIndex).filter(
                MemoryNavigationIndex.user_id == user_id,
                MemoryNavigationIndex.memory_level.in_(("l0", "l1")),
            )
            if include_types:
                query = query.filter(MemoryNavigationIndex.memory_type.in_(include_types))
            items = query.order_by(
                MemoryNavigationIndex.memory_level.asc(),
                MemoryNavigationIndex.memory_updated_at.desc().nullslast(),
                MemoryNavigationIndex.file_path.asc(),
            ).all()
            return [MemoryMetadataRepository._navigation_index_to_dict(item) for item in items]

    @staticmethod
    def list_l1_navigation_rows_by_branch_paths(
        *,
        user_id: str,
        branch_paths: list[str],
        include_types: list[str] | None = None,
    ) -> list[dict]:
        if not branch_paths:
            return []
        with get_db() as session:
            query = session.query(MemoryNavigationIndex).filter(
                MemoryNavigationIndex.user_id == user_id,
                MemoryNavigationIndex.memory_level == "l1",
                MemoryNavigationIndex.branch_path.in_(branch_paths),
            )
            if include_types:
                query = query.filter(MemoryNavigationIndex.memory_type.in_(include_types))
            items = query.order_by(MemoryNavigationIndex.branch_path.asc(), MemoryNavigationIndex.file_path.asc()).all()
            return [MemoryMetadataRepository._navigation_index_to_dict(item) for item in items]

    @staticmethod
    def list_l2_rows_by_branch_paths(
        user_id: str,
        branch_paths: list[str],
        include_types: list[str] | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        normalized_branch_paths = [item for item in {str(path).strip().strip("/") for path in branch_paths} if item]
        if not normalized_branch_paths:
            return []
        with get_db() as session:
            filters = [
                _scope_path_filter(MemoryIndex.file_path, branch_path) for branch_path in normalized_branch_paths
            ]
            query = session.query(MemoryIndex).filter(
                MemoryIndex.user_id == user_id,
                MemoryIndex.memory_level == "l2",
                or_(*filters),
            )
            if include_types:
                query = query.filter(MemoryIndex.memory_type.in_(include_types))
            query = query.order_by(
                MemoryIndex.directory_path.asc(),
                _memory_sort_expr().desc(),
                MemoryIndex.file_path.asc(),
            )
            if limit is not None:
                query = query.limit(limit)
            items = query.all()
            return [MemoryMetadataRepository._memory_index_to_dict(item) for item in items]

    @staticmethod
    def list_navigation_rows_for_scope(scope_paths: list[str]) -> list[dict]:
        normalized = [item for item in {str(path).strip().strip("/") for path in scope_paths} if item]
        if not normalized:
            return []
        with get_db() as session:
            filters = [_scope_path_filter(MemoryNavigationIndex.file_path, scope_path) for scope_path in normalized]
            query = session.query(MemoryNavigationIndex).filter(or_(*filters))
            items = query.order_by(MemoryNavigationIndex.user_id.asc(), MemoryNavigationIndex.file_path.asc()).all()
            return [MemoryMetadataRepository._navigation_index_to_dict(item) for item in items]

    @staticmethod
    def _memory_index_to_dict(item: MemoryIndex) -> dict:
        return {
            "memory_id": item.memory_id,
            "memory_type": item.memory_type,
            "memory_level": item.memory_level,
            "user_id": item.user_id,
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

    @staticmethod
    def _navigation_index_to_dict(item: MemoryNavigationIndex) -> dict:
        return {
            "memory_id": item.memory_id,
            "user_id": item.user_id,
            "project_id": item.project_id,
            "memory_type": item.memory_type,
            "memory_level": item.memory_level,
            "branch_path": item.branch_path,
            "file_path": item.file_path,
            "abstract_text": item.abstract_text,
            "tags": item.tags or [],
            "memory_updated_at": item.memory_updated_at.isoformat() if item.memory_updated_at else None,
            "vector_doc_id": item.vector_doc_id,
            "indexed_at": item.indexed_at.isoformat() if item.indexed_at else None,
            "refreshed_by_task_id": item.refreshed_by_task_id,
        }


def _scope_path_filter(column, scope_path: str):
    normalized = str(scope_path or "").strip().strip("/")
    if not normalized:
        return True
    escaped = _escape_like(normalized)
    return or_(column == normalized, column.like(f"{escaped}/%", escape="\\"))


def _escape_like(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _memory_sort_expr():
    return func.coalesce(MemoryIndex.memory_updated_at, MemoryIndex.indexed_at)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(str(value))


def _parse_cursor(cursor: str) -> tuple[datetime, str]:
    timestamp, memory_id = str(cursor).split("::", 1)
    return _parse_datetime(timestamp), memory_id
