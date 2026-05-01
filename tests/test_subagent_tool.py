from types import SimpleNamespace

import pytest

from runtime.entities import PromptMessageRole
from runtime.tool.builtin_tool.providers.subagent.subagent import SubagentTool
from runtime.tool.entities import ToolEntity


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _build_tool() -> SubagentTool:
    return SubagentTool(
        entity=ToolEntity(
            name="subagent",
            description="Delegate to subagent",
            parameters={},
            provider="builtin_provider",
            configs={},
        )
    )


@pytest.mark.anyio
async def test_subagent_tool_invokes_target_agent(monkeypatch):
    tool = _build_tool()
    target_agent = SimpleNamespace(
        id=42,
        name="worker_agent",
        model_id="test-model",
        prompt_template="You are a worker.",
        user_id="u1",
        builtin=0,
    )

    monkeypatch.setattr(tool, "_resolve_target_agent", lambda tool_parameters: target_agent)

    async def fake_invoke_subagent(agent, *, task: str, context: str | None = None) -> str:
        assert agent is target_agent
        assert task == "整理结果"
        assert context == "上游已经完成数据采集"
        return "已整理完成"

    monkeypatch.setattr(tool, "_invoke_subagent", fake_invoke_subagent)

    result = await tool._invoke(
        {
            "agent_name": "worker_agent",
            "task": "整理结果",
            "context": "上游已经完成数据采集",
            "agent_id": "7",
        },
        message_id="msg-1",
    )

    assert result.success is True
    assert result.data == {
        "agent_id": 42,
        "agent_name": "worker_agent",
        "task": "整理结果",
        "result": "已整理完成",
    }
    assert result.meta["target_agent_id"] == 42
    assert result.meta["delegated_by_agent_id"] == 7


@pytest.mark.anyio
async def test_subagent_tool_blocks_self_delegation(monkeypatch):
    tool = _build_tool()
    target_agent = SimpleNamespace(
        id=7,
        name="worker_agent",
        model_id="test-model",
        prompt_template="You are a worker.",
        user_id="u1",
        builtin=0,
    )
    monkeypatch.setattr(tool, "_resolve_target_agent", lambda tool_parameters: target_agent)

    result = await tool._invoke({"agent_name": "worker_agent", "task": "整理结果", "agent_id": "7"})

    assert result.success is False
    assert "current agent itself" in result.error


def test_subagent_tool_builds_chat_request_with_system_prompt():
    tool = _build_tool()
    target_agent = SimpleNamespace(
        id=42,
        name="worker_agent",
        model_id="test-model",
        prompt_template="You are a worker.",
    )

    request = tool._build_subagent_request(
        target_agent,
        task="分析日志",
        context="关注最近 24 小时的 error",
    )

    assert request.model == "test-model"
    assert request.stream is True
    assert len(request.messages) == 1
    assert request.messages[0].role == PromptMessageRole.USER
    assert "Context:\n关注最近 24 小时的 error" in request.messages[0].content
    assert "Task:\n分析日志" in request.messages[0].content


@pytest.mark.anyio
async def test_subagent_tool_requires_agent_name():
    tool = _build_tool()

    result = await tool._invoke({"task": "整理结果"})

    assert result.success is False
    assert result.error == "'agent_name' must be a non-empty string"
