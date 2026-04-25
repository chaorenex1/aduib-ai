from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from .contracts import MemoryTaskCreateCommand, MemoryWriteCommand
from .enums import MemoryTriggerType

MEMORY_WRITE_TASK_NAME = "runtime.tasks.memory_write.execute"


def new_task_id() -> str:
    return f"mwt_{uuid4().hex[:20]}"


def new_trace_id() -> str:
    return uuid4().hex


def build_memory_api_idempotency_key(payload: MemoryWriteCommand) -> str:
    base = {
        "trigger_type": MemoryTriggerType.MEMORY_API.value,
        "user_id": payload.user_id,
        "agent_id": payload.agent_id,
        "project_id": payload.project_id,
        "memory_source": payload.memory_source,
        "summary_enabled": payload.summary_enabled,
        "content": payload.content or "",
        "file_name": payload.file_name,
    }
    return hashlib.sha256(json.dumps(base, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def build_task_request_idempotency_key(payload: MemoryTaskCreateCommand) -> str:
    return hashlib.sha256(
        json.dumps(payload.model_dump(mode="python", exclude_none=True), sort_keys=True, ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()
