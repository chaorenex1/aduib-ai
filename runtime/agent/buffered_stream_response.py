from dataclasses import dataclass, field

from runtime.entities import AnthropicStreamEvent, ChatCompletionResponseChunk, ResponseStreamEvent
from runtime.tool.entities import ToolInvokeParams


@dataclass
class BufferedStreamResponse:
    events: list[ResponseStreamEvent | ChatCompletionResponseChunk | AnthropicStreamEvent] = field(default_factory=list)
    tool_calls: list[ToolInvokeParams] = field(default_factory=list)
    text: str = ""
