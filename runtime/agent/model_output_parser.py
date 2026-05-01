from __future__ import annotations

from typing import Any

from runtime.agent.adapters.response_text_extractor import ResponseTextExtractor
from runtime.entities.anthropic_entities import AnthropicMessageResponse, AnthropicToolUseBlock
from runtime.tool.base.tool import Tool


class ModelOutputParser:
    @classmethod
    def extract_assistant_text(cls, response: AnthropicMessageResponse) -> str:
        return ResponseTextExtractor.flatten_content(response.content)

    @classmethod
    def extract_tool_calls(cls, response: AnthropicMessageResponse, *, tools: list[Tool]) -> list[dict[str, Any]]:
        tool_lookup = {tool.entity.name: tool for tool in tools}
        calls: list[dict[str, Any]] = []
        for block in response.content:
            if not isinstance(block, AnthropicToolUseBlock):
                continue
            tool = tool_lookup.get(block.name)
            if tool is None:
                continue
            calls.append(
                {
                    "tool_use_id": block.id,
                    "tool_name": block.name,
                    "tool_input": dict(block.input or {}),
                    "provider": tool.entity.type.value,
                }
            )
        return calls
