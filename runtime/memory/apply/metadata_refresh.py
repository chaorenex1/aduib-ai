from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any

from component.storage.base_storage import storage_manager
from configs import config
from runtime.memory.committed_tree import CommittedMemoryTree
from service.memory.base.contracts import MemoryWritePipelineContext

from .patch import compute_content_sha256, parse_markdown_document


def refresh_metadata(context: MemoryWritePipelineContext) -> dict:
    staged = context.phase_results.get("build_staged_write_set") or {}
    metadata_scopes = sorted({item["scope_path"] for item in staged.get("metadata_mutations") or []})
    projection = {
        "scope_paths": metadata_scopes,
        "memory_index": [],
        "memory_directory_index": [],
        "memory_timeline_index": [],
        "memory_dedupe_index": [],
        "memory_retrieval_hint": [],
    }
    for scope_path in metadata_scopes:
        projection = _extend_scope_projection(projection=projection, scope_path=scope_path, task_id=context.task_id)
    _persist_metadata_projection(task_id=context.task_id, projection=projection)
    return {
        "task_id": context.task_id,
        "phase": "refresh_metadata",
        "metadata_scopes": metadata_scopes,
        "record_counts": {key: len(value) for key, value in projection.items()},
    }


def _extend_scope_projection(
    *, projection: dict[str, list[dict]], scope_path: str, task_id: str
) -> dict[str, list[dict]]:
    tree = CommittedMemoryTree.build_tree(path=scope_path, include_dirs=True, include_content=True, max_depth=None)
    files = [item for item in tree.get("tree") or [] if item["type"] == "file"]
    directories = [item for item in tree.get("tree") or [] if item["type"] == "dir"]
    for file_item in files:
        path = file_item["path"]
        if path.endswith("overview.md") or path.endswith("summary.md"):
            continue
        metadata, body = parse_markdown_document(file_item.get("content") or "")
        projection["memory_index"].append(
            _build_memory_index_record(path=path, metadata=metadata, body=body, task_id=task_id)
        )
        projection["memory_dedupe_index"].append(
            _build_dedupe_record(path=path, metadata=metadata, body=body, task_id=task_id)
        )
        projection["memory_retrieval_hint"].append(
            _build_retrieval_hint_record(path=path, metadata=metadata, body=body, task_id=task_id)
        )
        timeline_record = _build_timeline_record(path=path, metadata=metadata, task_id=task_id)
        if timeline_record:
            projection["memory_timeline_index"].append(timeline_record)
    all_directories = {scope_path, *[item["path"] for item in directories]}
    for directory_path in sorted(all_directories):
        projection["memory_directory_index"].append(
            _build_directory_index_record(directory_path=directory_path, task_id=task_id)
        )
    return projection


def _build_memory_index_record(*, path: str, metadata: dict[str, Any], body: str, task_id: str) -> dict[str, Any]:
    scope_type, user_id, agent_id = _resolve_scope(path)
    memory_class = _resolve_memory_class(path)
    return {
        "memory_id": metadata.get("memory_id") or f"mem_{sha256(path.encode('utf-8')).hexdigest()[:16]}",
        "memory_class": memory_class,
        "kind": metadata.get("kind") or memory_class,
        "user_id": user_id,
        "agent_id": agent_id,
        "project_id": metadata.get("project_id"),
        "scope_type": scope_type,
        "scope_path": _scope_path_for_file(path),
        "directory_path": path.rsplit("/", 1)[0],
        "file_path": path,
        "title": metadata.get("title") or path.rsplit("/", 1)[-1],
        "topic": metadata.get("topic") or metadata.get("tool_name") or metadata.get("subject"),
        "source_type": _extract_source_type(metadata),
        "visibility": metadata.get("visibility"),
        "status": metadata.get("status"),
        "tags": metadata.get("tags") or [],
        "file_sha256": compute_content_sha256(storage_manager.read_text(_to_scoped_path(path))),
        "content_bytes": len(storage_manager.read_text(_to_scoped_path(path)).encode("utf-8")),
        "projection_payload": metadata,
        "memory_created_at": metadata.get("created_at"),
        "memory_updated_at": metadata.get("updated_at"),
        "indexed_at": datetime.now().isoformat(),
        "refreshed_by_task_id": task_id,
    }


def _build_directory_index_record(*, directory_path: str, task_id: str) -> dict[str, Any]:
    scoped_path = _to_scoped_path(directory_path)
    entries = storage_manager.list_dir(scoped_path, recursive=False)
    memory_files = [
        entry
        for entry in entries
        if entry.is_file and not entry.path.endswith("overview.md") and not entry.path.endswith("summary.md")
    ]
    overview_path = f"{directory_path}/overview.md"
    summary_path = f"{directory_path}/summary.md"
    scope_type, user_id, agent_id = _resolve_scope(directory_path)
    return {
        "user_id": user_id,
        "agent_id": agent_id,
        "project_id": None,
        "scope_type": scope_type,
        "scope_path": _scope_path_for_directory(directory_path),
        "directory_path": directory_path,
        "parent_directory_path": directory_path.rsplit("/", 1)[0] if "/" in directory_path else None,
        "memory_class": _resolve_memory_class(directory_path),
        "directory_kind": directory_path.split("/", 3)[-1],
        "title": directory_path.rsplit("/", 1)[-1].replace("-", " ").title(),
        "overview_path": overview_path if storage_manager.exists(_to_scoped_path(overview_path)) else None,
        "summary_path": summary_path if storage_manager.exists(_to_scoped_path(summary_path)) else None,
        "memory_entry_count": len(memory_files),
        "child_directory_count": len([entry for entry in entries if entry.is_dir]),
        "latest_memory_updated_at": None,
        "projection_payload": {"entry_names": [entry.path.rsplit("/", 1)[-1] for entry in entries]},
        "refreshed_at": datetime.now().isoformat(),
        "refreshed_by_task_id": task_id,
    }


def _build_timeline_record(*, path: str, metadata: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    kind = str(metadata.get("kind") or "").strip()
    time_field = None
    for candidate in (
        "event_time",
        "task_time",
        "verification_time",
        "review_time",
        "deploy_time",
        "incident_time",
        "rollback_time",
    ):
        if metadata.get(candidate):
            time_field = candidate
            break
    if not time_field:
        return None
    scope_type, user_id, agent_id = _resolve_scope(path)
    return {
        "memory_id": metadata.get("memory_id") or f"mem_{sha256(path.encode('utf-8')).hexdigest()[:16]}",
        "user_id": user_id,
        "agent_id": agent_id,
        "project_id": metadata.get("project_id"),
        "memory_class": _resolve_memory_class(path),
        "kind": kind,
        "timeline_kind": kind,
        "file_path": path,
        "title": metadata.get("title") or path.rsplit("/", 1)[-1],
        "sort_at": metadata.get(time_field),
        "happened_at": metadata.get(time_field),
        "result_status": metadata.get("status"),
        "projection_payload": metadata,
        "indexed_at": datetime.now().isoformat(),
        "refreshed_by_task_id": task_id,
    }


def _build_dedupe_record(*, path: str, metadata: dict[str, Any], body: str, task_id: str) -> dict[str, Any]:
    scope_type, user_id, agent_id = _resolve_scope(path)
    title = str(metadata.get("title") or path.rsplit("/", 1)[-1]).strip().lower()
    return {
        "memory_id": metadata.get("memory_id") or f"mem_{sha256(path.encode('utf-8')).hexdigest()[:16]}",
        "user_id": user_id,
        "agent_id": agent_id,
        "project_id": metadata.get("project_id"),
        "memory_class": _resolve_memory_class(path),
        "kind": metadata.get("kind") or _resolve_memory_class(path),
        "file_path": path,
        "dedupe_scope_path": _scope_path_for_file(path),
        "title_norm": title,
        "semantic_key": (metadata.get("topic") or metadata.get("tool_name") or title),
        "content_sha256": compute_content_sha256(body),
        "fingerprint_version": "v1",
        "fingerprint_payload": {"title": title, "body_len": len(body)},
        "indexed_at": datetime.now().isoformat(),
        "refreshed_by_task_id": task_id,
    }


def _build_retrieval_hint_record(*, path: str, metadata: dict[str, Any], body: str, task_id: str) -> dict[str, Any]:
    scope_type, user_id, agent_id = _resolve_scope(path)
    title = str(metadata.get("title") or path.rsplit("/", 1)[-1]).strip()
    primary_topic = metadata.get("topic") or metadata.get("tool_name") or metadata.get("subject") or title
    return {
        "memory_id": metadata.get("memory_id") or f"mem_{sha256(path.encode('utf-8')).hexdigest()[:16]}",
        "user_id": user_id,
        "agent_id": agent_id,
        "project_id": metadata.get("project_id"),
        "memory_class": _resolve_memory_class(path),
        "kind": metadata.get("kind") or _resolve_memory_class(path),
        "file_path": path,
        "title": title,
        "primary_topic": primary_topic,
        "body_summary": body[:200],
        "tags": metadata.get("tags") or [],
        "aliases": [],
        "entity_refs": [],
        "keywords": [keyword for keyword in {title, primary_topic} if keyword],
        "query_hints": [primary_topic] if primary_topic else [],
        "importance_score": None,
        "freshness_at": metadata.get("updated_at"),
        "indexed_at": datetime.now().isoformat(),
        "refreshed_by_task_id": task_id,
    }


def _resolve_scope(path: str) -> tuple[str, str | None, str | None]:
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "users":
        return "user", parts[1], None
    if len(parts) >= 2 and parts[0] == "agent":
        return "agent", None, parts[1]
    return "unknown", None, None


def _resolve_memory_class(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 4 and parts[0] == "users" and parts[2] == "memories":
        return parts[3]
    if len(parts) >= 4 and parts[0] == "agent" and parts[2] == "memories":
        return parts[3]
    return "unknown"


def _scope_path_for_file(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 4 and parts[0] == "users" and parts[2] == "memories":
        return "/".join(parts[:4])
    if len(parts) >= 4 and parts[0] == "agent" and parts[2] == "memories":
        return "/".join(parts[:4])
    return path.rsplit("/", 1)[0]


def _scope_path_for_directory(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 4 and parts[0] == "users" and parts[2] == "memories":
        return "/".join(parts[:4])
    if len(parts) >= 4 and parts[0] == "agent" and parts[2] == "memories":
        return "/".join(parts[:4])
    if len(parts) >= 3 and parts[0] == "users" and parts[2] == "project":
        return "/".join(parts[:3])
    return path


def _extract_source_type(metadata: dict[str, Any]) -> str | None:
    source = metadata.get("source")
    if isinstance(source, dict):
        return source.get("type")
    return None


def _to_scoped_path(relative_path: str) -> str:
    return "/".join(part for part in [config.MEMORY_TREE_ROOT_DIR, relative_path] if part)


def _persist_metadata_projection(*, task_id: str, projection: dict) -> None:
    from service.memory.repository import MemoryMetadataRepository

    MemoryMetadataRepository.persist_projection(task_id=task_id, projection=projection)
