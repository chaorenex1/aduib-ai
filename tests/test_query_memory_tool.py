from types import SimpleNamespace

import pytest

from runtime.tool.builtin_tool.providers.query_memory.query_memory import QueryMemoryTool
from runtime.tool.entities import ToolEntity


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _build_tool() -> QueryMemoryTool:
    return QueryMemoryTool(
        entity=ToolEntity(
            name="queryMemory",
            description="Query agent memory",
            parameters={},
            provider="builtin_provider",
            configs={},
        )
    )


@pytest.mark.anyio
async def test_query_memory_tool_returns_structured_results(monkeypatch):
    tool = _build_tool()

    async def fake_retrieve_context(*, query: str, long_term_memory: bool):
        assert query == "用户偏好"
        assert long_term_memory is True
        return {
            "long_term": [
                SimpleNamespace(
                    memory_id="m1",
                    content="用户偏好中文输出",
                    score=0.91,
                    metadata={"domain": "preference"},
                ),
                SimpleNamespace(memory_id="m2", content="用户喜欢简洁回答", score=0.82, metadata={}),
            ]
        }

    agent_manager = SimpleNamespace(memory_manager=SimpleNamespace(retrieve_context=fake_retrieve_context))

    result = await tool._invoke(
        {
            "query": "用户偏好",
            "user_id": "u1",
            "agent_manager": agent_manager,
        },
        message_id="msg-1",
    )

    assert result.success is True
    assert result.data["query"] == "用户偏好"
    assert result.data["total"] == 2
    assert result.data["results"][0].memory_id == "m1"
    assert result.meta["message_id"] == "msg-1"
    assert result.meta["user_id"] == "u1"


@pytest.mark.anyio
async def test_query_memory_tool_validates_query():
    tool = _build_tool()

    result = await tool._invoke({"query": ""})

    assert result.success is False
    assert result.error == "'query' is required"


@pytest.mark.anyio
async def test_query_memory_tool_allows_empty_user_id():
    tool = _build_tool()

    async def fake_retrieve_context(*, query: str, long_term_memory: bool):
        assert query == "test"
        assert long_term_memory is True
        return {"long_term": []}

    agent_manager = SimpleNamespace(memory_manager=SimpleNamespace(retrieve_context=fake_retrieve_context))

    result = await tool._invoke({"query": "test", "agent_manager": agent_manager})

    assert result.success is True
    assert result.data["total"] == 0
    assert result.meta["user_id"] == ""
