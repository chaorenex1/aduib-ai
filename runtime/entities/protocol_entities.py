from __future__ import annotations

from enum import Enum
from typing import TypeAlias

from runtime.entities.anthropic_entities import AnthropicMessageRequest, AnthropicMessageResponse, AnthropicStreamEvent
from runtime.entities.llm_entities import ChatCompletionRequest, ChatCompletionResponse, ChatCompletionResponseChunk
from runtime.entities.response_entities import ResponseOutput, ResponseRequest, ResponseStreamEvent


class ExternalProtocol(str, Enum):
    """Supported external request/response protocols."""

    OPENAI_CHAT = "openai_chat"
    ANTHROPIC_MESSAGES = "anthropic_messages"
    OPENAI_RESPONSES = "openai_responses"


AnyProtocolRequest: TypeAlias = ChatCompletionRequest | AnthropicMessageRequest | ResponseRequest
AnyProtocolResponse: TypeAlias = ChatCompletionResponse | AnthropicMessageResponse | ResponseOutput
AnyProtocolStreamEvent: TypeAlias = ChatCompletionResponseChunk | AnthropicStreamEvent | ResponseStreamEvent
