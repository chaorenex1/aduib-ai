from __future__ import annotations

import re

from configs import config


def normalize_path_segment(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "unknown"
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", raw)
    return normalized.strip("-") or "unknown"


def build_memory_api_archive_path(*, user_id: str, task_id: str) -> str:
    return "/".join(
        [
            config.MEMORY_TREE_ROOT_DIR,
            "users",
            user_id,
            "sources",
            "memory_api",
            f"{task_id}.json",
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
