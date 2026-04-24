from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from controllers.memory.memories import (
    get_memory as get_memory_endpoint,
)
from controllers.memory.memories import (
    get_memory_by_path as get_memory_by_path_endpoint,
)
from controllers.memory.memories import (
    get_memory_content as get_memory_content_endpoint,
)
from controllers.memory.memories import (
    list_memories as list_memories_endpoint,
)
from controllers.memory.schemas import MemoryByPathQuery, MemoryListQuery, MemoryScope
from service.memory.read_service import MemoryReadService


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_memories_endpoints_return_formal_read_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        MemoryReadService,
        "list_memories",
        staticmethod(lambda **_: {"items": [{"memory_id": "mem_pref"}], "next_cursor": None}),
    )
    monkeypatch.setattr(
        MemoryReadService,
        "get_memory_by_path",
        staticmethod(lambda path, **scope: {"memory_id": "mem_pref", "file_path": path}),
    )
    monkeypatch.setattr(
        MemoryReadService,
        "get_memory",
        staticmethod(lambda memory_id, **scope: {"memory_id": memory_id, "title": "Python code style"}),
    )
    monkeypatch.setattr(
        MemoryReadService,
        "get_memory_content",
        staticmethod(lambda memory_id, **scope: {"memory_id": memory_id, "content": "Prefer concise Python code."}),
    )

    list_response = await list_memories_endpoint(
        MemoryListQuery(user_id="u1", agent_id=None, project_id=None, kind=None, path_prefix=None, limit=20)
    )
    list_body = json.loads(list_response.body)
    assert list_body["success"] is True
    assert list_body["data"]["items"][0]["memory_id"] == "mem_pref"

    by_path_response = await get_memory_by_path_endpoint(
        MemoryByPathQuery(
            user_id="u1",
            agent_id=None,
            project_id=None,
            path="users/u1/memories/preference/Python-code-style.md",
        )
    )
    by_path_body = json.loads(by_path_response.body)
    assert by_path_body["data"]["memory_id"] == "mem_pref"

    get_response = await get_memory_endpoint("mem_pref", MemoryScope(user_id="u1", agent_id=None, project_id=None))
    get_body = json.loads(get_response.body)
    assert get_body["data"]["title"] == "Python code style"

    content_response = await get_memory_content_endpoint(
        "mem_pref",
        MemoryScope(user_id="u1", agent_id=None, project_id=None),
    )
    content_body = json.loads(content_response.body)
    assert content_body["data"]["content"] == "Prefer concise Python code."
