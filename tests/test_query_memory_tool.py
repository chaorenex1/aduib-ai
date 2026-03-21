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

    monkeypatch.setattr(tool, "_resolve_user_id", lambda tool_parameters: "u1")

    async def fake_retrieve_memories(**kwargs):
        assert kwargs["query"] == "用户偏好"
        assert kwargs["user_id"] == "u1"
        assert kwargs["retrieve_type"] == "llm"
        assert kwargs["top_k"] == 5
        assert kwargs["score_threshold"] == 0.6
        assert kwargs["filters"] == {}
        return [
            SimpleNamespace(memory_id="m1", content="用户偏好中文输出", score=0.91, metadata={"domain": "preference"}),
            SimpleNamespace(memory_id="m2", content="用户喜欢简洁回答", score=0.82, metadata={}),
        ]

    monkeypatch.setattr(tool, "_retrieve_memories", fake_retrieve_memories)

    result = await tool._invoke(
        {
            "query": "用户偏好",
        },
        message_id="msg-1",
    )

    assert result.success is True
    assert result.data["query"] == "用户偏好"
    assert result.data["retrieve_type"] == "llm"
    assert result.data["total"] == 2
    assert result.data["results"][0]["memory_id"] == "m1"
    assert result.meta["message_id"] == "msg-1"
    assert result.meta["user_id"] == "u1"


@pytest.mark.anyio
async def test_query_memory_tool_validates_query():
    tool = _build_tool()

    result = await tool._invoke({"query": ""})

    assert result.success is False
    assert result.error == "'query' must be a non-empty string"


@pytest.mark.anyio
async def test_query_memory_tool_requires_user_id(monkeypatch):
    tool = _build_tool()
    monkeypatch.setattr(
        tool,
        "_resolve_user_id",
        lambda tool_parameters: (_ for _ in ()).throw(ValueError("'user_id' is required")),
    )

    result = await tool._invoke({"query": "test"})

    assert result.success is False
    assert result.error == "'user_id' is required"
