from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from controllers.memory.legacy import store_memory as store_memory_endpoint
from controllers.memory.schemas import MemoryCreateRequest
from service.memory import MemoryService, MemoryWritePublishError


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_legacy_store_returns_accepted_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_store_memory(_payload: MemoryCreateRequest) -> dict:
        return {
            "task_id": "task-1",
            "trace_id": "trace-1",
            "trigger_type": "memory_api",
            "status": "accepted",
            "phase": "accepted",
            "queue_status": "queued",
            "source_ref": {
                "type": "memory_api",
                "id": "task-1",
                "path": "memory_pipeline/users/u1/sources/memory_api/task-1.json",
            },
            "archive_ref": {
                "path": "memory_pipeline/users/u1/sources/memory_api/task-1.json",
                "type": "application/json",
                "storage": "default",
            },
        }

    monkeypatch.setattr(MemoryService, "store_memory", staticmethod(_fake_store_memory))

    response = await store_memory_endpoint(
        MemoryCreateRequest(
            content="Store this through the new queue-first path.",
            project_id="proj-1",
            user_id="u1",
            agent_id="a1",
        )
    )

    body = json.loads(response.body)
    assert response.status_code == 202
    assert body["success"] is True
    assert body["data"]["task_id"] == "task-1"
    assert body["data"]["status"] == "accepted"
    assert body["data"]["queue_status"] == "queued"


@pytest.mark.anyio
async def test_legacy_store_surfaces_publish_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_store_memory(_payload: MemoryCreateRequest) -> dict:
        raise MemoryWritePublishError("queue unavailable", task_id="task-2")

    monkeypatch.setattr(MemoryService, "store_memory", staticmethod(_fake_store_memory))

    response = await store_memory_endpoint(
        MemoryCreateRequest(
            content="This publish should fail.",
            project_id="proj-1",
            user_id="u1",
            agent_id="a1",
        )
    )

    body = json.loads(response.body)
    assert response.status_code == 503
    assert body["success"] is False
    assert body["error"]["code"] == "memory_queue_publish_failed"
    assert body["error"]["details"]["task_id"] == "task-2"
