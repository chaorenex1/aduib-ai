from __future__ import annotations

from runtime.memory.apply.patch import parse_markdown_document
from runtime.memory.committed_tree import CommittedMemoryTree

from .base.contracts import MemoryContentResult, MemoryReadListResult, MemoryReadRecord
from .base.errors import MemoryReadNotFoundError
from .repository import MemoryMetadataRepository


class MemoryReadService:
    @staticmethod
    def list_memories(
        *,
        user_id: str,
        project_id: str | None,
        memory_type: str | None,
        path_prefix: str | None,
        updated_after: str | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        _validate_path_in_scope(path_prefix=path_prefix, user_id=user_id)
        records = MemoryMetadataRepository.list_memory_index(
            user_id=user_id,
            project_id=project_id,
            memory_type=memory_type,
            path_prefix=path_prefix,
            updated_after=updated_after,
            cursor=cursor,
            limit=limit + 1,
        )
        visible_records = records[:limit]
        next_cursor = _encode_cursor(visible_records[-1]) if len(records) > limit and visible_records else None
        return MemoryReadListResult(
            items=[MemoryReadRecord.model_validate(item) for item in visible_records],
            next_cursor=next_cursor,
        ).model_dump(mode="python", exclude_none=True)

    @staticmethod
    def get_memory(memory_id: str, *, user_id: str, project_id: str | None) -> dict:
        record = MemoryMetadataRepository.get_memory_by_id(
            memory_id,
            user_id=user_id,
            project_id=project_id,
        )
        if record is None:
            raise MemoryReadNotFoundError("memory not found")
        return MemoryReadRecord.model_validate(record).model_dump(mode="python", exclude_none=True)

    @staticmethod
    def get_memory_by_path(path: str, *, user_id: str, project_id: str | None) -> dict:
        _validate_path_in_scope(path_prefix=path, user_id=user_id)
        record = MemoryMetadataRepository.get_memory_by_path(
            path,
            user_id=user_id,
            project_id=project_id,
        )
        if record is None:
            raise MemoryReadNotFoundError("memory path not found")
        return MemoryReadRecord.model_validate(record).model_dump(mode="python", exclude_none=True)

    @staticmethod
    def get_memory_content(memory_id: str, *, user_id: str, project_id: str | None) -> dict:
        record = MemoryMetadataRepository.get_memory_by_id(
            memory_id,
            user_id=user_id,
            project_id=project_id,
        )
        if record is None:
            raise MemoryReadNotFoundError("memory not found")
        file_view = CommittedMemoryTree.read_file(path=record["file_path"], include_metadata=True)
        metadata, body = parse_markdown_document(file_view["content"])
        return MemoryContentResult(
            memory_id=record["memory_id"],
            file_path=record["file_path"],
            content=body,
            metadata=metadata,
        ).model_dump(mode="python", exclude_none=True)


def _validate_path_in_scope(*, path_prefix: str | None, user_id: str) -> None:
    if not path_prefix:
        return
    path = str(path_prefix or "").replace("\\", "/").strip("/")
    allowed_prefixes = [f"users/{user_id}/"]
    if not any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in allowed_prefixes):
        raise MemoryReadNotFoundError("memory path not found")


def _encode_cursor(record: dict) -> str | None:
    sort_value = record.get("memory_updated_at") or record.get("indexed_at")
    memory_id = record.get("memory_id")
    if not sort_value or not memory_id:
        return None
    return f"{sort_value}::{memory_id}"
