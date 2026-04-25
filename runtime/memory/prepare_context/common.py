from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from component.storage.base_storage import storage_manager
from configs import config
from runtime.memory.base.contracts import ArchivedSourceRef
from runtime.memory.prepare_context.types import DirectoryEntryRecord, PreparedPrefetchContext

SUMMARY_FILENAMES = ("overview.md", "summary.md")
SEARCH_QUERY_MAX_CHARS = 240
SUMMARY_FILE_MAX_CHARS = 8_000
PATH_SEARCH_MAX_RESULTS = 10
CANDIDATE_FILE_MAX_CHARS = 2_000
MAX_CANDIDATE_READS = 5

CANDIDATE_DISCOVERY_ACTION_SCHEMA = {
    "action": "search_candidate_paths | read_candidate_files | finalize | stop_noop",
    "reasoning": "short reason",
    "search_query": {
        "query": "short path/title search query",
        "path_scopes": ["users/<user_id>/memories", "agent/<agent_id>/memories"],
        "reason": "why these terms identify candidate memories",
    },
    "candidate_paths": ["users/<user_id>/memories/<memory_type>/<file>.md"],
}

USER_PREFETCH_PATH_TEMPLATES = (
    "users/{user_id}/memories/preference",
    "users/{user_id}/memories/event",
    "users/{user_id}/memories/entity",
    "users/{user_id}/memories/task",
    "users/{user_id}/memories/verification",
    "users/{user_id}/memories/review",
    "users/{user_id}/memories/ops",
)
AGENT_PREFETCH_PATH_TEMPLATES = (
    "agent/{agent_id}/memories/solution",
    "agent/{agent_id}/memories/pattern",
    "agent/{agent_id}/memories/tool",
    "agent/{agent_id}/memories/skill",
)


def load_pg_jsonl_conversation_snapshot(
    archive_ref: ArchivedSourceRef | None,
    *,
    conversation_id: str,
) -> tuple[dict[str, Any], str]:
    raw_content, actual_sha256 = read_archived_source_text(
        archive_ref,
        missing_error="archive_ref is required for conversation source",
    )

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


def load_archive_snapshot(archive_ref: ArchivedSourceRef | None) -> tuple[dict[str, Any], str]:
    raw_content, actual_sha256 = read_archived_source_text(
        archive_ref,
        missing_error="archive_ref is required for archived memory write sources",
    )
    snapshot = json.loads(raw_content)
    if not isinstance(snapshot, dict):
        raise ValueError("archived source snapshot must be a JSON object")
    return snapshot, actual_sha256


def normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {"role": str(message.get("role") or "unknown")}
    if isinstance(message.get("content"), str):
        normalized["content"] = message["content"]
    if isinstance(message.get("content_parts"), list):
        normalized["content_parts"] = message["content_parts"]
    if message.get("created_at") is not None:
        normalized["created_at"] = message["created_at"]
    return normalized


def collect_text_blocks(messages: list[dict[str, Any]]) -> list[str]:
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


def load_schema_bundle() -> list[dict[str, Any]]:
    schema_dir = Path(__file__).resolve().parents[1] / "schema"
    bundle: list[dict[str, Any]] = []
    for path in sorted(schema_dir.glob("*.yaml")):
        try:
            display_path = path.relative_to(Path.cwd())
        except ValueError:
            display_path = path
        bundle.append({"memory_type": path.stem, "path": str(display_path).replace("\\", "/")})
    return bundle


def build_search_query(text_blocks: list[str]) -> str:
    parts = [block.strip() for block in text_blocks if isinstance(block, str) and block.strip()]
    if not parts:
        return ""
    return " ".join(parts)[:SEARCH_QUERY_MAX_CHARS]


def load_json_payload(raw_text: str) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return {}
    candidates = [text]
    start_index = text.find("{")
    end_index = text.rfind("}")
    if start_index != -1 and end_index != -1 and end_index > start_index:
        candidates.append(text[start_index : end_index + 1])
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("candidate discovery output is not a JSON object")


def read_archived_source_text(
    archive_ref: ArchivedSourceRef | None,
    *,
    missing_error: str,
) -> tuple[str, str]:
    if archive_ref is None:
        raise ValueError(missing_error)

    raw_content = storage_manager.read_text(archive_ref.path)
    actual_sha256 = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
    if archive_ref.content_sha256 and archive_ref.content_sha256 != actual_sha256:
        raise ValueError("archive_ref.content_sha256 does not match current archived content")
    return raw_content, actual_sha256


def to_scoped_storage_path(relative_path: str) -> str:
    return "/".join(part for part in [config.MEMORY_TREE_ROOT_DIR, relative_path] if part)


def directory_entry_from_raw(raw_entry: dict[str, Any]) -> DirectoryEntryRecord:
    return DirectoryEntryRecord(
        path=str(raw_entry.get("path") or ""),
        type="file" if str(raw_entry.get("type") or "") == "file" else "dir",
        size=raw_entry.get("size"),
    )


def describe_summary_file(file_path: str) -> tuple[str, str, str | None, Literal["l0", "l1"] | None]:
    branch_path = file_path.rsplit("/", 1)[0]
    scope_type, memory_type = classify_branch_scope(branch_path)
    if file_path.endswith("overview.md"):
        summary_level: Literal["l0", "l1"] | None = "l0"
    elif file_path.endswith("summary.md"):
        summary_level = "l1"
    else:
        summary_level = None
    return branch_path, scope_type, memory_type, summary_level


def candidate_search_roots(*, user_id: str | None, agent_id: str | None) -> list[str]:
    roots: list[str] = []
    if user_id:
        roots.append(f"users/{user_id}/memories")
    if agent_id:
        roots.append(f"agent/{agent_id}/memories")
    return roots


def is_candidate_memory_path(file_path: str) -> bool:
    normalized = str(file_path or "").strip().strip("/")
    if not normalized or normalized.endswith("/overview.md") or normalized.endswith("/summary.md"):
        return False
    parts = [part for part in normalized.split("/") if part]
    return (len(parts) >= 5 and parts[0] == "users" and parts[2] == "memories") or (
        len(parts) >= 5 and parts[0] == "agent" and parts[2] == "memories"
    )


def classify_branch_scope(branch_path: str) -> tuple[str, str | None]:
    parts = [part for part in str(branch_path or "").split("/") if part]
    if len(parts) >= 4 and parts[0] == "users" and parts[2] == "memories":
        return "user_memory", parts[3]
    if len(parts) >= 4 and parts[0] == "agent" and parts[2] == "memories":
        return "agent_memory", parts[3]
    if len(parts) >= 3 and parts[0] == "users" and parts[2] == "project":
        return "project", "project"
    return "unknown", None


def summarize_candidate_content(content: str, *, max_chars: int = 400) -> str:
    text = str(content or "").strip()
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    collected: list[str] = []
    in_front_matter = False
    for index, line in enumerate(lines):
        if index == 0 and line == "---":
            in_front_matter = True
            continue
        if in_front_matter:
            if line == "---":
                in_front_matter = False
            continue
        collected.append(line)
    body = " ".join(collected) if collected else " ".join(lines)
    return body[:max_chars]


def dump_prefetched_context(prefetched_context: PreparedPrefetchContext) -> dict[str, Any]:
    return prefetched_context.model_dump(mode="python", exclude_none=True, by_alias=True)


def unique_preserving_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_items: list[str] = []
    for item in items:
        normalized_item = str(item or "").strip()
        if not normalized_item or normalized_item in seen:
            continue
        seen.add(normalized_item)
        unique_items.append(normalized_item)
    return unique_items
