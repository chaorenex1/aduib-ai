"""
ProtocolConverter: unified facade for cross-protocol request/response conversion.

Supported conversions (6 directions + streaming):
  OpenAI Chat Completions <-> Anthropic Messages
  OpenAI Chat Completions <-> OpenAI Responses API
  Anthropic Messages      <-> OpenAI Responses API (via OpenAI as hub)
  + Streaming event conversions for all protocols
"""

from __future__ import annotations

from runtime.entities.anthropic_entities import AnthropicMessageRequest, AnthropicMessageResponse, AnthropicStreamEvent
from runtime.entities.llm_entities import ChatCompletionRequest, ChatCompletionResponse, ChatCompletionResponseChunk
from runtime.entities.protocol_entities import (
    AnyProtocolRequest,
    AnyProtocolResponse,
    AnyProtocolStreamEvent,
    ExternalProtocol,
)
from runtime.entities.response_entities import ResponseOutput, ResponseRequest, ResponseStreamEvent
from runtime.protocol.registry import ProtocolAdapterRegistry
from runtime.protocol._openai_anthropic import (
    StreamingToolCallCollector,
    anthropic_response_to_openai,
    anthropic_stream_to_openai,
    anthropic_to_openai,
    create_anthropic_tool_call_collector,
    openai_response_to_anthropic,
    openai_stream_to_anthropic,
    openai_to_anthropic,
    reset_anthropic_stream_state,
)
from runtime.protocol._openai_responses import (
    ResponsesStreamingToolCallCollector,
    create_responses_tool_call_collector,
    openai_response_to_responses,
    openai_stream_to_responses,
    openai_to_responses,
    reset_responses_stream_state,
    responses_stream_to_openai,
    responses_to_openai,
    responses_to_openai_response,
)


class ProtocolConverter:
    """Unified facade for bidirectional conversion between three LLM protocols.

    Protocol hub topology (OpenAI Chat as hub):
        OpenAI Chat <-> Anthropic Messages  (direct)
        OpenAI Chat <-> Responses API       (direct)
        Anthropic   <-> Responses API       (via OpenAI Chat)

    Usage:
        req_anthropic = ProtocolConverter.openai_to_anthropic(req_openai)
        req_openai    = ProtocolConverter.anthropic_to_openai(req_anthropic)
        req_responses = ProtocolConverter.openai_to_responses(req_openai)
        req_openai    = ProtocolConverter.responses_to_openai(req_responses)
    """

    # ── Request conversions ───────────────────────────────────────────────────

    @staticmethod
    def openai_to_anthropic(req: ChatCompletionRequest) -> AnthropicMessageRequest:
        """Convert ChatCompletionRequest -> AnthropicMessageRequest."""
        return openai_to_anthropic(req)

    @staticmethod
    def anthropic_to_openai(req: AnthropicMessageRequest) -> ChatCompletionRequest:
        """Convert AnthropicMessageRequest -> ChatCompletionRequest."""
        return anthropic_to_openai(req)

    @staticmethod
    def openai_to_responses(req: ChatCompletionRequest) -> ResponseRequest:
        """Convert ChatCompletionRequest -> ResponseRequest."""
        return openai_to_responses(req)

    @staticmethod
    def responses_to_openai(req: ResponseRequest) -> ChatCompletionRequest:
        """Convert ResponseRequest -> ChatCompletionRequest."""
        return responses_to_openai(req)

    @staticmethod
    def anthropic_to_responses(req: AnthropicMessageRequest) -> ResponseRequest:
        """Convert AnthropicMessageRequest -> ResponseRequest (via OpenAI Chat hub)."""
        return openai_to_responses(anthropic_to_openai(req))

    @staticmethod
    def responses_to_anthropic(req: ResponseRequest) -> AnthropicMessageRequest:
        """Convert ResponseRequest -> AnthropicMessageRequest (via OpenAI Chat hub)."""
        return openai_to_anthropic(responses_to_openai(req))

    # ── Response conversions ──────────────────────────────────────────────────

    @staticmethod
    def openai_response_to_anthropic(resp: ChatCompletionResponse) -> AnthropicMessageResponse:
        """Convert ChatCompletionResponse -> AnthropicMessageResponse."""
        return openai_response_to_anthropic(resp)

    @staticmethod
    def anthropic_response_to_openai(resp: AnthropicMessageResponse) -> ChatCompletionResponse:
        """Convert AnthropicMessageResponse -> ChatCompletionResponse."""
        return anthropic_response_to_openai(resp)

    @staticmethod
    def openai_response_to_responses(resp: ChatCompletionResponse) -> ResponseOutput:
        """Convert ChatCompletionResponse -> ResponseOutput."""
        return openai_response_to_responses(resp)

    @staticmethod
    def responses_to_openai_response(resp: ResponseOutput) -> ChatCompletionResponse:
        """Convert ResponseOutput -> ChatCompletionResponse."""
        return responses_to_openai_response(resp)

    @staticmethod
    def anthropic_response_to_responses(resp: AnthropicMessageResponse) -> ResponseOutput:
        """Convert AnthropicMessageResponse -> ResponseOutput (via OpenAI Chat hub)."""
        return openai_response_to_responses(anthropic_response_to_openai(resp))

    @staticmethod
    def responses_to_anthropic_response(resp: ResponseOutput) -> AnthropicMessageResponse:
        """Convert ResponseOutput -> AnthropicMessageResponse (via OpenAI Chat hub)."""
        return openai_response_to_anthropic(responses_to_openai_response(resp))

    # ── Streaming conversions ───────────────────────────────────────────────────

    @staticmethod
    def openai_stream_to_anthropic(chunk: ChatCompletionResponseChunk) -> list[AnthropicStreamEvent]:
        """Convert ChatCompletionResponseChunk -> Anthropic SSE events."""
        return openai_stream_to_anthropic(chunk)

    @staticmethod
    def anthropic_stream_to_openai(event: AnthropicStreamEvent) -> ChatCompletionResponseChunk:
        """Convert Anthropic SSE event -> ChatCompletionResponseChunk."""
        return anthropic_stream_to_openai(event)

    @staticmethod
    def openai_stream_to_responses(chunk: ChatCompletionResponseChunk) -> list[ResponseStreamEvent]:
        """Convert ChatCompletionResponseChunk -> Responses API SSE events."""
        return openai_stream_to_responses(chunk)

    @staticmethod
    def responses_stream_to_openai(event: ResponseStreamEvent) -> ChatCompletionResponseChunk:
        """Convert Responses API SSE event -> ChatCompletionResponseChunk."""
        return responses_stream_to_openai(event)

    @staticmethod
    def anthropic_stream_to_responses(event: AnthropicStreamEvent) -> list[ResponseStreamEvent]:
        """Convert Anthropic SSE event -> Responses API SSE events (via OpenAI)."""
        chunk = anthropic_stream_to_openai(event)
        return openai_stream_to_responses(chunk)

    @staticmethod
    def responses_stream_to_anthropic(event: ResponseStreamEvent) -> list[AnthropicStreamEvent]:
        """Convert Responses API SSE event -> Anthropic SSE events (via OpenAI)."""
        chunk = responses_stream_to_openai(event)
        return openai_stream_to_anthropic(chunk)

    @staticmethod
    def adapt_request(
        req: AnyProtocolRequest,
        *,
        source_protocol: ExternalProtocol,
        target_protocol: ExternalProtocol,
    ) -> AnyProtocolRequest:
        """Convert a request object from one external protocol into another."""
        adapter = ProtocolAdapterRegistry.get_ingress_adapter(source_protocol, target_protocol)
        return adapter.adapt(req)

    @staticmethod
    def adapt_response(
        resp: AnyProtocolResponse,
        *,
        source_protocol: ExternalProtocol,
        target_protocol: ExternalProtocol,
    ) -> AnyProtocolResponse:
        """Convert a non-streaming response object from one protocol into another."""
        adapter = ProtocolAdapterRegistry.get_egress_adapter(source_protocol, target_protocol)
        return adapter.adapt_response(resp)

    @staticmethod
    def adapt_stream_event(
        event: AnyProtocolStreamEvent,
        *,
        source_protocol: ExternalProtocol,
        target_protocol: ExternalProtocol,
    ) -> list[AnyProtocolStreamEvent]:
        """Convert a single streaming event from one protocol into another."""
        adapter = ProtocolAdapterRegistry.get_egress_adapter(source_protocol, target_protocol)
        return adapter.adapt_stream_event(event)

    @staticmethod
    def reset_stream_state():
        """Reset all streaming conversion states. Call between conversations."""
        reset_anthropic_stream_state()
        reset_responses_stream_state()

    # ── Tool Call Collectors ─────────────────────────────────────────────────────

    @staticmethod
    def create_anthropic_tool_collector() -> StreamingToolCallCollector:
        """Create a collector for Anthropic streaming tool calls.

        Usage:
            collector = ProtocolConverter.create_anthropic_tool_collector()
            for event in stream:
                collector.process_event(event)
                if event.type == "message_stop":
                    tool_calls = collector.get_completed_tool_calls()
                    collector.clear()
        """
        return create_anthropic_tool_call_collector()

    @staticmethod
    def create_responses_tool_collector() -> ResponsesStreamingToolCallCollector:
        """Create a collector for Responses API streaming tool calls.

        Usage:
            collector = ProtocolConverter.create_responses_tool_collector()
            for chunk in stream:
                collector.process_chunk(chunk)
                if is_final_chunk:
                    tool_calls = collector.get_completed_tool_calls()
                    collector.clear()
        """
        return create_responses_tool_call_collector()
