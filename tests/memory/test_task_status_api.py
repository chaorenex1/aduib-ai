from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from controllers.memory.schemas import MemoryWriteReplayRequest, TaskCreateRequest
from controllers.memory.tasks import (
    create_memory_task as create_memory_task_endpoint,
)
from controllers.memory.tasks import (
    get_memory_task as get_memory_task_endpoint,
)
from controllers.memory.tasks import (
    get_memory_task_result as get_memory_task_result_endpoint,
)
from controllers.memory.tasks import (
    replay_memory_task as replay_memory_task_endpoint,
)
from service.memory import MemoryWriteIngestService, MemoryWriteTaskService


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_create_memory_task_returns_accepted_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_accept_task_request(_payload) -> dict:
        return {
            "task_id": "task-10",
            "trace_id": "trace-10",
            "trigger_type": "session_commit",
            "status": "accepted",
            "phase": "accepted",
            "queue_status": "queued",
            "source_ref": {"type": "session_commit", "id": "session-1", "path": "conversation/session-1"},
            "archive_ref": None,
        }

    monkeypatch.setattr(MemoryWriteIngestService, "accept_task_request", staticmethod(_fake_accept_task_request))

    response = await create_memory_task_endpoint(
        TaskCreateRequest(
            user_id="u1",
            agent_id="a1",
            project_id="p1",
            trigger_type="session_commit",
            source_ref={"type": "session_commit", "id": "session-1", "path": "conversation/session-1"},
        )
    )

    body = json.loads(response.body)
    assert response.status_code == 202
    assert body["success"] is True
    assert body["data"]["task_id"] == "task-10"
    assert body["data"]["trigger_type"] == "session_commit"


@pytest.mark.anyio
async def test_task_status_endpoints_return_serialized_task(monkeypatch: pytest.MonkeyPatch) -> None:
    task_payload = {
        "task_id": "task-11",
        "trace_id": "trace-11",
        "trigger_type": "memory_api",
        "status": "running",
        "phase": "prepare_extract_context",
        "queue_status": "queued",
        "source_ref": {
            "type": "memory_api",
            "id": "task-11",
            "path": "memory_pipeline/users/u1/sources/memory_api/task-11.json",
        },
        "archive_ref": {
            "path": "memory_pipeline/users/u1/sources/memory_api/task-11.json",
            "type": "application/json",
            "storage": "default",
        },
        "result_ref": {"skeleton": True},
    }

    monkeypatch.setattr(
        MemoryWriteTaskService,
        "get_task",
        staticmethod(lambda task_id: {**task_payload, "task_id": task_id}),
    )
    monkeypatch.setattr(
        MemoryWriteTaskService,
        "get_task_result",
        staticmethod(lambda task_id: {"task_id": task_id, "result_ref": {"skeleton": True}}),
    )
    monkeypatch.setattr(
        MemoryWriteTaskService,
        "replay",
        staticmethod(lambda task_id, actor=None: {**task_payload, "task_id": task_id, "replayed_by": actor}),
    )

    get_response = await get_memory_task_endpoint("task-11")
    get_body = json.loads(get_response.body)
    assert get_response.status_code == 200
    assert get_body["data"]["phase"] == "prepare_extract_context"

    result_response = await get_memory_task_result_endpoint("task-11")
    result_body = json.loads(result_response.body)
    assert result_response.status_code == 200
    assert result_body["data"]["result_ref"]["skeleton"] is True

    replay_response = await replay_memory_task_endpoint("task-11", MemoryWriteReplayRequest(actor="operator-1"))
    replay_body = json.loads(replay_response.body)
    assert replay_response.status_code == 202
    assert replay_body["data"]["replayed_by"] == "operator-1"
