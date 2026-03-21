from __future__ import annotations

from abc import ABC, abstractmethod

from runtime.entities.anthropic_entities import AnthropicMessageStopEvent
from runtime.entities.llm_entities import ChatCompletionResponseChunk
from runtime.entities.protocol_entities import AnyProtocolResponse, AnyProtocolStreamEvent, ExternalProtocol
from runtime.entities.response_entities import ResponseDoneEvent
from runtime.protocol._openai_anthropic import (
    anthropic_response_to_openai,
    anthropic_stream_to_openai,
    openai_response_to_anthropic,
    openai_stream_to_anthropic,
)
from runtime.protocol._openai_responses import (
    openai_response_to_responses,
    openai_stream_to_responses,
    responses_stream_to_openai,
    responses_to_openai_response,
)


class EgressAdapter(ABC):
    """Converts provider-native responses/events into the caller-facing protocol."""

    source_protocol: ExternalProtocol
    target_protocol: ExternalProtocol

    @abstractmethod
    def adapt_response(self, resp: AnyProtocolResponse) -> AnyProtocolResponse:
        raise NotImplementedError

    @abstractmethod
    def adapt_stream_event(self, event: AnyProtocolStreamEvent) -> list[AnyProtocolStreamEvent]:
        raise NotImplementedError


class IdentityEgressAdapter(EgressAdapter):
    def __init__(self, protocol: ExternalProtocol) -> None:
        self.source_protocol = protocol
        self.target_protocol = protocol

    def adapt_response(self, resp: AnyProtocolResponse) -> AnyProtocolResponse:
        return resp

    def adapt_stream_event(self, event: AnyProtocolStreamEvent) -> list[AnyProtocolStreamEvent]:
        return [event]


class AnthropicToOpenAIEgressAdapter(EgressAdapter):
    source_protocol = ExternalProtocol.ANTHROPIC_MESSAGES
    target_protocol = ExternalProtocol.OPENAI_CHAT

    def adapt_response(self, resp: AnyProtocolResponse) -> AnyProtocolResponse:
        return anthropic_response_to_openai(resp)

    def adapt_stream_event(self, event: AnyProtocolStreamEvent) -> list[AnyProtocolStreamEvent]:
        if isinstance(event, AnthropicMessageStopEvent):
            return [ChatCompletionResponseChunk(done=True)]

        chunk = anthropic_stream_to_openai(event)
        if not chunk.choices and not chunk.done:
            return []
        return [chunk]


class OpenAIToAnthropicEgressAdapter(EgressAdapter):
    source_protocol = ExternalProtocol.OPENAI_CHAT
    target_protocol = ExternalProtocol.ANTHROPIC_MESSAGES

    def adapt_response(self, resp: AnyProtocolResponse) -> AnyProtocolResponse:
        return openai_response_to_anthropic(resp)

    def adapt_stream_event(self, event: AnyProtocolStreamEvent) -> list[AnyProtocolStreamEvent]:
        if getattr(event, "done", False):
            return []
        return openai_stream_to_anthropic(event)


class ResponsesToOpenAIEgressAdapter(EgressAdapter):
    source_protocol = ExternalProtocol.OPENAI_RESPONSES
    target_protocol = ExternalProtocol.OPENAI_CHAT

    def adapt_response(self, resp: AnyProtocolResponse) -> AnyProtocolResponse:
        return responses_to_openai_response(resp)

    def adapt_stream_event(self, event: AnyProtocolStreamEvent) -> list[AnyProtocolStreamEvent]:
        chunk = responses_stream_to_openai(event)
        chunks: list[AnyProtocolStreamEvent] = []
        if chunk.choices:
            chunks.append(chunk)
        if isinstance(event, ResponseDoneEvent):
            chunks.append(ChatCompletionResponseChunk(done=True))
        return chunks


class OpenAIToResponsesEgressAdapter(EgressAdapter):
    source_protocol = ExternalProtocol.OPENAI_CHAT
    target_protocol = ExternalProtocol.OPENAI_RESPONSES

    def adapt_response(self, resp: AnyProtocolResponse) -> AnyProtocolResponse:
        return openai_response_to_responses(resp)

    def adapt_stream_event(self, event: AnyProtocolStreamEvent) -> list[AnyProtocolStreamEvent]:
        if getattr(event, "done", False):
            return []
        return openai_stream_to_responses(event)


class AnthropicToResponsesEgressAdapter(EgressAdapter):
    source_protocol = ExternalProtocol.ANTHROPIC_MESSAGES
    target_protocol = ExternalProtocol.OPENAI_RESPONSES

    def adapt_response(self, resp: AnyProtocolResponse) -> AnyProtocolResponse:
        return openai_response_to_responses(anthropic_response_to_openai(resp))

    def adapt_stream_event(self, event: AnyProtocolStreamEvent) -> list[AnyProtocolStreamEvent]:
        if isinstance(event, AnthropicMessageStopEvent):
            return []

        chunk = anthropic_stream_to_openai(event)
        if not chunk.choices:
            return []
        return openai_stream_to_responses(chunk)


class ResponsesToAnthropicEgressAdapter(EgressAdapter):
    source_protocol = ExternalProtocol.OPENAI_RESPONSES
    target_protocol = ExternalProtocol.ANTHROPIC_MESSAGES

    def adapt_response(self, resp: AnyProtocolResponse) -> AnyProtocolResponse:
        return openai_response_to_anthropic(responses_to_openai_response(resp))

    def adapt_stream_event(self, event: AnyProtocolStreamEvent) -> list[AnyProtocolStreamEvent]:
        chunk = responses_stream_to_openai(event)
        if not chunk.choices and not isinstance(event, ResponseDoneEvent):
            return []
        if getattr(chunk, "done", False):
            return []
        return openai_stream_to_anthropic(chunk)
