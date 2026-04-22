from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from service.memory import (
    MemorySourceRef,
    MemoryTaskCreateCommand,
    MemoryTriggerType,
    MemoryWriteCommand,
)
from service.memory.base.builders import (
    build_memory_api_idempotency_key,
    build_queue_payload,
    build_task_request_idempotency_key,
)
from service.memory.base.paths import build_memory_api_archive_path, build_session_commit_archive_path


def test_builders_are_stable_for_same_inputs() -> None:
    write_command = MemoryWriteCommand(
        content="same content",
        file_name="notes.md",
        project_id="proj-1",
        user_id="user-1",
        agent_id="agent-1",
        summary_enabled=True,
        memory_source="user_input",
    )
    task_command = MemoryTaskCreateCommand(
        trigger_type=MemoryTriggerType.SESSION_COMMIT,
        user_id="user-1",
        agent_id="agent-1",
        project_id="proj-1",
        source_ref=MemorySourceRef(type="session_commit", id="session-1", path="conversation/session-1"),
    )

    assert build_memory_api_idempotency_key(write_command) == build_memory_api_idempotency_key(write_command)
    assert build_task_request_idempotency_key(task_command) == build_task_request_idempotency_key(task_command)
    assert build_queue_payload(celery_message_id="celery-1") == {
        "celery_task_name": "runtime.tasks.memory_write.execute",
        "celery_message_id": "celery-1",
    }


def test_archive_paths_follow_memory_pipeline_layout() -> None:
    assert build_memory_api_archive_path(user_id="u1", task_id="task-1") == (
        "memory_pipeline/users/u1/sources/memory_api/task-1.json"
    )
    assert build_session_commit_archive_path(
        user_id="u1",
        session_key="session/1",
        task_id="task-1",
    ) == "memory_pipeline/users/u1/sources/session_commit/session-1__task-1.json"
