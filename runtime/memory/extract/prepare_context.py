from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from component.storage.base_storage import storage_manager
from configs import config
from runtime.memory.committed_tree import CommittedMemoryTree
from service.memory.base.contracts import (
    ArchivedSourceRef,
    MemoryWritePipelineContext,
    PreparedExtractContext,
)

USER_PREFETCH_PATH_TEMPLATES = (
    "users/{user_id}/memories/preference",
    "users/{user_id}/memories/event",
    "users/{user_id}/memories/entity",
    "users/{user_id}/memories/task",
    "users/{user_id}/memories/verification",
    "users/{user_id}/memories/review",
    "users/{user_id}/memories/ops",
    "users/{user_id}/project",
)
AGENT_PREFETCH_PATH_TEMPLATES = (
    "agent/{agent_id}/memories/solution",
    "agent/{agent_id}/memories/pattern",
    "agent/{agent_id}/memories/tool",
    "agent/{agent_id}/memories/skill",
)


def prepare_extract_context(context: MemoryWritePipelineContext) -> dict:
    normalized = _normalize_source_material(context)
    user_id = normalized.get("user_id") or context.user_id
    agent_id = normalized.get("agent_id") or context.agent_id
    project_id = normalized.get("project_id") or context.project_id
    prefetched_context = _build_prefetched_context(
        text_blocks=normalized["text_blocks"],
        user_id=user_id,
        agent_id=agent_id,
    )
    schema_bundle = _load_schema_bundle()

    prepared = PreparedExtractContext(
        task_id=context.task_id,
        phase=context.phase,
        source_kind=normalized["source_kind"],
        source_hash=normalized["source_hash"],
        source_ref=context.source_ref,
        archive_ref=context.archive_ref,
        user_id=user_id,
        agent_id=agent_id,
        project_id=project_id,
        language=normalized.get("language"),
        messages=normalized["messages"],
        text_blocks=normalized["text_blocks"],
        prefetched_context=prefetched_context,
        stats={
            "message_count": len(normalized["messages"]),
            "text_block_count": len(normalized["text_blocks"]),
            "prefetched_directory_count": len(prefetched_context["directory_views"]),
            "prefetched_file_count": len(prefetched_context["file_reads"]),
            "prefetched_search_count": len(prefetched_context["search_results"]),
        },
        schema_bundle=schema_bundle,
        conversation_snapshot=normalized.get("conversation_snapshot"),
        session_snapshot=normalized.get("session_snapshot"),
        archived_snapshot=normalized.get("archived_snapshot"),
    )
    return prepared.model_dump(mode="python", exclude_none=True)


def load_pg_jsonl_conversation_snapshot(
    archive_ref: ArchivedSourceRef | None,
    *,
    conversation_id: str,
) -> tuple[dict[str, Any], str]:
    if archive_ref is None:
        raise ValueError("archive_ref is required for conversation source")

    raw_content = storage_manager.read_text(archive_ref.path)
    actual_sha256 = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
    if archive_ref.content_sha256 and archive_ref.content_sha256 != actual_sha256:
        raise ValueError("archive_ref.content_sha256 does not match current archived content")

    messages: list[dict[str, Any]] = []
    for index, line in enumerate(raw_content.splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            message = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"conversation jsonl contains invalid json at line {index}") from exc
        if not isinstance(message, dict):
            raise ValueError(f"conversation jsonl contains non-object row at line {index}")
        if message.get("conversation_id") != conversation_id:
            raise ValueError(f"conversation jsonl contains mismatched conversation_id at line {index}")
        messages.append(message)

    return (
        {
            "storage": "frozen_jsonl",
            "archive_ref": archive_ref.model_dump(mode="python", exclude_none=True),
            "message_count": len(messages),
            "messages": messages,
        },
        actual_sha256,
    )


def _normalize_source_material(context: MemoryWritePipelineContext) -> dict[str, Any]:
    source_ref = context.source_ref.model_dump(mode="python", exclude_none=True)
    if source_ref.get("type") == "conversation":
        conversation_snapshot, source_hash = load_pg_jsonl_conversation_snapshot(
            context.archive_ref,
            conversation_id=str(source_ref.get("conversation_id") or "").strip(),
        )
        messages = [_normalize_message(message) for message in conversation_snapshot["messages"]]
        text_blocks = _collect_text_blocks(messages)
        return {
            "source_kind": "conversation",
            "source_hash": source_hash,
            "messages": messages,
            "text_blocks": text_blocks,
            "language": "unknown",
            "conversation_snapshot": conversation_snapshot,
            "user_id": context.user_id,
            "agent_id": context.agent_id,
            "project_id": context.project_id,
        }

    archived_snapshot, source_hash = _load_archive_snapshot(context.archive_ref)
    trigger_type = str(context.trigger_type)
    if trigger_type == "memory_api":
        payload = archived_snapshot.get("payload") or {}
        content = str(payload.get("content") or "").strip()
        messages = [{"role": "user", "content": content, "source_kind": "memory_api"}] if content else []
        text_blocks = [content] if content else []
        scope = archived_snapshot.get("scope") or {}
        return {
            "source_kind": "memory_api",
            "source_hash": source_hash,
            "messages": messages,
            "text_blocks": text_blocks,
            "language": "unknown",
            "archived_snapshot": archived_snapshot,
            "user_id": scope.get("user_id") or context.user_id,
            "agent_id": scope.get("agent_id") or context.agent_id,
            "project_id": scope.get("project_id") or context.project_id,
        }

    if trigger_type == "session_commit":
        session_snapshot = archived_snapshot.get("session_snapshot") or {}
        raw_messages = session_snapshot.get("messages") or []
        messages = [_normalize_message(message) for message in raw_messages if isinstance(message, dict)]
        text_blocks = _collect_text_blocks(messages)
        scope = archived_snapshot.get("scope") or {}
        return {
            "source_kind": "session_commit",
            "source_hash": source_hash,
            "messages": messages,
            "text_blocks": text_blocks,
            "language": "unknown",
            "session_snapshot": session_snapshot,
            "archived_snapshot": archived_snapshot,
            "user_id": scope.get("user_id") or context.user_id,
            "agent_id": scope.get("agent_id") or context.agent_id,
            "project_id": scope.get("project_id") or context.project_id,
        }

    raise ValueError(f"unsupported memory write source kind: {source_ref.get('type') or trigger_type}")


def _load_archive_snapshot(archive_ref: ArchivedSourceRef | None) -> tuple[dict[str, Any], str]:
    if archive_ref is None:
        raise ValueError("archive_ref is required for archived memory write sources")

    raw_content = storage_manager.read_text(archive_ref.path)
    actual_sha256 = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
    if archive_ref.content_sha256 and archive_ref.content_sha256 != actual_sha256:
        raise ValueError("archive_ref.content_sha256 does not match current archived content")
    snapshot = json.loads(raw_content)
    if not isinstance(snapshot, dict):
        raise ValueError("archived source snapshot must be a JSON object")
    return snapshot, actual_sha256


def _normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {"role": str(message.get("role") or "unknown")}
    if isinstance(message.get("content"), str):
        normalized["content"] = message["content"]
    if isinstance(message.get("content_parts"), list):
        normalized["content_parts"] = message["content_parts"]
    if message.get("created_at") is not None:
        normalized["created_at"] = message["created_at"]
    return normalized


def _collect_text_blocks(messages: list[dict[str, Any]]) -> list[str]:
    text_blocks: list[str] = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            text_blocks.append(content.strip())
        for part in message.get("content_parts") or []:
            if isinstance(part, dict) and part.get("type") == "text":
                text = str(part.get("text") or "").strip()
                if text:
                    text_blocks.append(text)
    return text_blocks


def _build_prefetched_context(*, text_blocks: list[str], user_id: str | None, agent_id: str | None) -> dict[str, Any]:
    candidate_paths: list[str] = []
    if user_id:
        candidate_paths.extend(path.format(user_id=user_id) for path in USER_PREFETCH_PATH_TEMPLATES)
    if agent_id:
        candidate_paths.extend(path.format(agent_id=agent_id) for path in AGENT_PREFETCH_PATH_TEMPLATES)

    directory_views = [
        CommittedMemoryTree.list_entries(
            path=path,
            recursive=False,
            include_files=True,
            include_dirs=True,
            max_results=50,
        )
        for path in candidate_paths
    ]

    file_reads: list[dict[str, Any]] = []
    already_read_paths: list[str] = []
    for path in candidate_paths:
        for filename in ("overview.md", "summary.md"):
            file_path = f"{path}/{filename}"
            scoped_path = _to_scoped_storage_path(file_path)
            if not storage_manager.exists(scoped_path):
                continue
            file_reads.append(
                CommittedMemoryTree.read_file(
                    path=file_path,
                    max_chars=8_000,
                    include_metadata=True,
                )
            )
            already_read_paths.append(file_path)

    search_results: list[dict[str, Any]] = []
    query = _build_search_query(text_blocks)
    if query:
        if user_id:
            search_results.append(
                CommittedMemoryTree.search_content(
                    query=query,
                    path=f"users/{user_id}/memories",
                    max_results=10,
                )
            )
        if agent_id:
            search_results.append(
                CommittedMemoryTree.search_content(
                    query=query,
                    path=f"agent/{agent_id}/memories",
                    max_results=10,
                )
            )

    return {
        "directory_views": directory_views,
        "file_reads": file_reads,
        "search_results": search_results,
        "already_read_paths": sorted(set(already_read_paths)),
    }


def _load_schema_bundle() -> list[dict[str, Any]]:
    schema_dir = Path(__file__).resolve().parents[1] / "schema"
    bundle: list[dict[str, Any]] = []
    for path in sorted(schema_dir.glob("*.yaml")):
        try:
            display_path = path.relative_to(Path.cwd())
        except ValueError:
            display_path = path
        bundle.append({"memory_type": path.stem, "path": str(display_path).replace("\\", "/")})
    return bundle


def _build_search_query(text_blocks: list[str]) -> str:
    parts = [block.strip() for block in text_blocks if isinstance(block, str) and block.strip()]
    if not parts:
        return ""
    return " ".join(parts)[:240]


def _to_scoped_storage_path(relative_path: str) -> str:
    return "/".join(part for part in [config.MEMORY_TREE_ROOT_DIR, relative_path] if part)
