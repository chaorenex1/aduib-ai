from __future__ import annotations

import re

from configs import config


def normalize_path_segment(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "unknown"
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", raw)
    return normalized.strip("-") or "unknown"


def build_memory_api_conversation_archive_path(*, user_id: str, conversation_id: str, task_id: str) -> str:
    external_source, external_session_id = parse_conversation_id(conversation_id)
    conversation_key = build_conversation_key(
        external_source=external_source,
        external_session_id=external_session_id,
    )
    return "/".join(
        [
            config.MEMORY_TREE_ROOT_DIR,
            "users",
            user_id,
            "sources",
            "conversations",
            f"{conversation_key}__{normalize_path_segment(task_id)}__his.jsonl",
        ]
    )


def build_session_commit_archive_path(*, user_id: str, session_key: str, task_id: str) -> str:
    safe_session_key = normalize_path_segment(session_key)
    return "/".join(
        [
            config.MEMORY_TREE_ROOT_DIR,
            "users",
            user_id,
            "sources",
            "session_commit",
            f"{safe_session_key}__{task_id}.json",
        ]
    )


def build_conversation_id(*, external_source: str, external_session_id: str) -> str:
    source = str(external_source or "").strip()
    session_id = str(external_session_id or "").strip()
    if not source or not session_id:
        raise ValueError("conversation id requires external_source and external_session_id")
    return f"{source}:{session_id}"


def parse_conversation_id(conversation_id: str) -> tuple[str, str]:
    value = str(conversation_id or "").strip()
    if ":" not in value:
        raise ValueError("conversation_id must match <external_source>:<external_session_id>")
    external_source, external_session_id = value.split(":", 1)
    external_source = external_source.strip()
    external_session_id = external_session_id.strip()
    if not external_source or not external_session_id:
        raise ValueError("conversation_id must match <external_source>:<external_session_id>")
    canonical = build_conversation_id(external_source=external_source, external_session_id=external_session_id)
    if canonical != value:
        raise ValueError("conversation_id must be canonical")
    return external_source, external_session_id


def build_conversation_key(*, external_source: str, external_session_id: str) -> str:
    return "__".join(
        [
            normalize_path_segment(external_source),
            normalize_path_segment(external_session_id),
        ]
    )


def build_conversation_source_path(*, user_id: str, external_source: str, external_session_id: str) -> str:
    conversation_key = build_conversation_key(
        external_source=external_source,
        external_session_id=external_session_id,
    )
    return "/".join(
        [
            config.MEMORY_TREE_ROOT_DIR,
            "users",
            user_id,
            "sources",
            "conversations",
            f"{conversation_key}.jsonl",
        ]
    )
