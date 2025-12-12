import pytest

from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.entities.message_entities import (
    AssistantPromptMessage,
    ToolPromptMessage,
    UserPromptMessage,
    PromptMessageRole,
)


def build_messages():
    # Assistant with tool_calls id order: a1, a2
    assistant = AssistantPromptMessage(
        role=PromptMessageRole.ASSISTANT,
        tool_calls=[
            AssistantPromptMessage.ToolCall(id="a1"),
            AssistantPromptMessage.ToolCall(id="a2"),
        ],
        content="assistant",
    )

    # Tool messages initially in wrong order and positions
    tool2 = ToolPromptMessage(role=PromptMessageRole.TOOL, tool_call_id="a2", content="tool-a2")
    tool1 = ToolPromptMessage(role=PromptMessageRole.TOOL, tool_call_id="a1", content="tool-a1")

    user = UserPromptMessage(role=PromptMessageRole.USER, content="hi")

    # Original order: user, tool2, assistant, tool1
    return [user, tool2, assistant, tool1]


def test_change_tool_calls_sequence_moves_tools_after_assistant_in_order():
    req = ChatCompletionRequest(messages=build_messages())

    # After model validation, messages should be reordered:
    # user, assistant, tool-a1, tool-a2
    msgs = req.messages

    assert msgs[0].role == PromptMessageRole.USER
    assert isinstance(msgs[1], AssistantPromptMessage)
    assert msgs[2].role == PromptMessageRole.TOOL and msgs[2].tool_call_id == "a1"
    assert msgs[3].role == PromptMessageRole.TOOL and msgs[3].tool_call_id == "a2"
    # Ensure no extra tool messages left at original positions
    assert len(msgs) == 4

