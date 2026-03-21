"""
OpenAI Chat Completions <-> Anthropic Messages bidirectional converter.

Request conversions:
  openai_to_anthropic: ChatCompletionRequest  -> AnthropicMessageRequest
  anthropic_to_openai: AnthropicMessageRequest -> ChatCompletionRequest

Response conversions:
  openai_response_to_anthropic: ChatCompletionResponse  -> AnthropicMessageResponse
  anthropic_response_to_openai: AnthropicMessageResponse -> ChatCompletionResponse
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from runtime.entities.anthropic_entities import (
    AnthropicContentBlock,
    AnthropicContentBlockDeltaEvent,
    AnthropicContentBlockStartEvent,
    AnthropicMessage,
    AnthropicMessageDelta,
    AnthropicMessageDeltaEvent,
    AnthropicMessageRequest,
    AnthropicMessageResponse,
    AnthropicMessageStartEvent,
    AnthropicMessageStartMessage,
    AnthropicMessageStopEvent,
    AnthropicMetadata,
    AnthropicOutputConfig,
    AnthropicStreamDelta,
    AnthropicStreamDeltaType,
    AnthropicStreamEvent,
    AnthropicSystemBlock,
    AnthropicTextBlock,
    AnthropicThinkingBlock,
    AnthropicTool,
    AnthropicToolResultBlock,
    AnthropicToolUseBlock,
    AnthropicUsage,
)
from runtime.entities.llm_entities import (
    AssistantPromptMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionResponseChunk,
    ChatCompletionResponseChunkDelta,
    LLMUsage,
)
from runtime.protocol._utils import (
    anthropic_tool_choice_to_openai,
    extract_text_content,
    map_stop_reason_to_anthropic,
    map_stop_reason_to_openai,
    normalize_tool_schema,
    openai_tool_choice_to_anthropic,
)

logger = logging.getLogger(__name__)


# ── Request: OpenAI -> Anthropic ─────────────────────────────────────────────


def openai_to_anthropic(req: ChatCompletionRequest) -> AnthropicMessageRequest:
    """Convert a ChatCompletionRequest into an AnthropicMessageRequest.

    Handles:
    - system message extraction -> system top-level field
    - tool messages -> tool_result content blocks merged into preceding user message
    - assistant tool_calls -> tool_use content blocks
    - tools schema: parameters -> input_schema (with uri format removal)
    - stop: list/str -> stop_sequences
    - tool_choice mapping
    """
    messages: list[AnthropicMessage] = []
    system: Optional[list[AnthropicSystemBlock]] = None

    for msg in req.messages or []:
        role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)

        if role == "system":
            system = [AnthropicSystemBlock(text=extract_text_content(msg.content))]

        elif role == "tool":
            # Merge tool results into the preceding user message as tool_result blocks.
            tool_result = AnthropicToolResultBlock(
                tool_use_id=getattr(msg, "tool_call_id", "") or "",
                content=extract_text_content(msg.content),
            )
            last = messages[-1] if messages else None
            if last and last.role == "user":
                existing = last.content if isinstance(last.content, list) else []
                messages[-1] = AnthropicMessage(role="user", content=existing + [tool_result])
            else:
                messages.append(AnthropicMessage(role="user", content=[tool_result]))

        elif role == "assistant":
            blocks: list[Any] = []
            text = extract_text_content(msg.content)
            if text:
                blocks.append(AnthropicTextBlock(text=text))
            for tc in getattr(msg, "tool_calls", None) or []:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}
                blocks.append(
                    AnthropicToolUseBlock(
                        id=str(tc.id or ""),
                        name=tc.function.name or "",
                        input=args,
                    )
                )
            content: Any = blocks if blocks else extract_text_content(msg.content)
            messages.append(AnthropicMessage(role="assistant", content=content))

        else:  # user
            messages.append(
                AnthropicMessage(
                    role="user",
                    content=extract_text_content(msg.content),
                )
            )

    # Also check for system passed via req.system (Anthropic-compat patch field)
    if system is None and getattr(req, "system", None):
        raw_sys = req.system  # type: ignore[attr-defined]
        if isinstance(raw_sys, list):
            texts = []
            for item in raw_sys:
                if isinstance(item, dict):
                    texts.append(item.get("text") or "")
                elif isinstance(item, str):
                    texts.append(item)
            system = [AnthropicSystemBlock(text=" ".join(t for t in texts if t))]
        elif isinstance(raw_sys, str):
            system = [AnthropicSystemBlock(text=raw_sys)]

    # Tools
    anthropic_tools: Optional[list[AnthropicTool]] = None
    if req.tools:
        anthropic_tools = []
        for t in req.tools:
            fn = getattr(t, "function", None) or t
            name = getattr(fn, "name", "") or getattr(t, "name", "")
            desc = getattr(fn, "description", None) or getattr(t, "description", None)
            params = getattr(fn, "parameters", {}) or getattr(fn, "input_schema", {}) or {}
            anthropic_tools.append(
                AnthropicTool(
                    name=name,
                    description=desc,
                    input_schema=normalize_tool_schema(params),
                )
            )

    # stop -> stop_sequences
    stop_sequences: Optional[list[str]] = None
    if req.stop:
        stop_sequences = list(req.stop) if isinstance(req.stop, (list, tuple)) else [req.stop]

    # response_format -> output_config
    output_config: Optional[AnthropicOutputConfig] = None
    if req.response_format:
        rf = req.response_format
        rf_type = rf.get("type") if isinstance(rf, dict) else None
        if rf_type == "json_object":
            output_config = AnthropicOutputConfig(
                type="json",
                schema=rf.get("schema") or rf.get("json_schema"),
            )
        elif rf_type == "text":
            output_config = AnthropicOutputConfig(type="text")

    return AnthropicMessageRequest(
        model=req.model or "",
        messages=messages,
        system=system,
        tools=anthropic_tools,
        tool_choice=openai_tool_choice_to_anthropic(req.tool_choice),
        max_tokens=req.max_tokens or req.max_completion_tokens or 4096,
        temperature=req.temperature,
        top_p=req.top_p,
        top_k=req.top_k,
        stream=bool(req.stream),
        stop_sequences=stop_sequences,
        thinking=req.thinking,
        output_config=output_config,
    )


# ── Request: Anthropic -> OpenAI ─────────────────────────────────────────────


def anthropic_to_openai(req: AnthropicMessageRequest) -> ChatCompletionRequest:
    """Convert an AnthropicMessageRequest into a ChatCompletionRequest.

    Handles:
    - system field -> messages[0] {role: system}
    - tool_result blocks -> {role: tool, tool_call_id, content} messages
    - tool_use blocks -> assistant tool_calls
    - input_schema -> parameters
    - stop_sequences -> stop
    - tool_choice mapping
    """
    raw_messages: list[dict[str, Any]] = []

    # System
    if req.system:
        if isinstance(req.system, str):
            sys_text = req.system
        else:
            sys_text = " ".join(b.text for b in req.system if isinstance(b, AnthropicSystemBlock))
        if sys_text:
            raw_messages.append({"role": "system", "content": sys_text})

    for msg in req.messages:
        if isinstance(msg.content, str):
            raw_messages.append({"role": msg.role, "content": msg.content})
            continue

        pending_text_parts: list[dict[str, str]] = []
        pending_tool_calls: list[dict[str, Any]] = []
        tool_results: list[dict[str, Any]] = []

        for block in msg.content:
            if isinstance(block, AnthropicTextBlock):
                pending_text_parts.append({"type": "text", "text": block.text})
            elif isinstance(block, AnthropicThinkingBlock):
                # Represent thinking as a text part for OpenAI compat
                if block.thinking:
                    pending_text_parts.append({"type": "text", "text": block.thinking})
            elif isinstance(block, AnthropicToolUseBlock):
                pending_tool_calls.append(
                    {
                        "type": "function",
                        "id": block.id,
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input),
                        },
                    }
                )
            elif isinstance(block, AnthropicToolResultBlock):
                content_str = block.content if isinstance(block.content, str) else extract_text_content(block.content)
                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": block.tool_use_id,
                        "content": content_str,
                    }
                )
            else:
                block_text = extract_text_content(getattr(block, "content", None))
                if block_text:
                    pending_text_parts.append({"type": "text", "text": block_text})

        if pending_text_parts or pending_tool_calls:
            msg_dict: dict[str, Any] = {"role": msg.role}
            msg_dict["content"] = extract_text_content(pending_text_parts) if pending_text_parts else ""
            if pending_tool_calls:
                msg_dict["tool_calls"] = pending_tool_calls
            raw_messages.append(msg_dict)
        if tool_results:
            raw_messages.extend(tool_results)

    # Tools
    openai_tools: Optional[list[dict]] = None
    if req.tools:
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.input_schema,
                },
            }
            for t in req.tools
        ]

    # Extract user from metadata
    user: Optional[str] = None
    if req.metadata:
        if isinstance(req.metadata, AnthropicMetadata):
            user = req.metadata.user_id
        elif isinstance(req.metadata, dict):
            user = req.metadata.get("user_id")

    # Convert output_config back to response_format
    response_format: Optional[dict[str, Any]] = None
    if req.output_config:
        oc = req.output_config
        if hasattr(oc, "type"):
            if oc.type == "json":
                response_format = {"type": "json_object"}
                if hasattr(oc, "schema") and oc.schema:
                    response_format["json_schema"] = oc.schema
            elif oc.type == "text":
                response_format = {"type": "text"}

    return ChatCompletionRequest(
        model=req.model,
        messages=raw_messages,
        tools=openai_tools,
        tool_choice=anthropic_tool_choice_to_openai(req.tool_choice),
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        top_p=req.top_p,
        top_k=req.top_k,
        stream=req.stream,
        stop=req.stop_sequences,
        thinking=req.thinking,
        user=user,
        response_format=response_format,
    )


# ── Response: OpenAI -> Anthropic ────────────────────────────────────────────


def openai_response_to_anthropic(resp: ChatCompletionResponse) -> AnthropicMessageResponse:
    """Convert a ChatCompletionResponse into an AnthropicMessageResponse."""
    blocks: list[Any] = []
    if resp.message:
        if resp.message.content:
            blocks.append(AnthropicTextBlock(text=str(resp.message.content)))
        for tc in resp.message.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            blocks.append(
                AnthropicToolUseBlock(
                    id=str(tc.id or ""),
                    name=tc.function.name or "",
                    input=args,
                )
            )

    usage = resp.usage or LLMUsage.empty_usage()
    return AnthropicMessageResponse(
        id=resp.id or "",
        type="message",
        role="assistant",
        content=blocks,
        model=resp.model or "",
        stop_reason="end_turn",
        stop_sequence=getattr(resp, "stop_sequence", None),
        usage=AnthropicUsage(
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
        ),
    )


# ── Response: Anthropic -> OpenAI ────────────────────────────────────────────


def anthropic_response_to_openai(resp: AnthropicMessageResponse) -> ChatCompletionResponse:
    """Convert an AnthropicMessageResponse into a ChatCompletionResponse."""
    text = ""
    tool_calls: list[AssistantPromptMessage.ToolCall] = []

    for block in resp.content:
        if isinstance(block, AnthropicTextBlock):
            text += block.text
        elif isinstance(block, AnthropicThinkingBlock):
            text += block.thinking
        elif isinstance(block, AnthropicToolUseBlock):
            tool_calls.append(
                AssistantPromptMessage.ToolCall(
                    id=block.id,
                    type="function",
                    function=AssistantPromptMessage.ToolCall.ToolCallFunction(
                        name=block.name,
                        arguments=json.dumps(block.input),
                    ),
                )
            )

    usage = LLMUsage(
        prompt_tokens=resp.usage.input_tokens,
        completion_tokens=resp.usage.output_tokens,
        total_tokens=resp.usage.input_tokens + resp.usage.output_tokens,
    )
    finish_reason = map_stop_reason_to_openai(resp.stop_reason)
    _ = finish_reason  # available for callers via stop_reason field

    return ChatCompletionResponse(
        id=resp.id,
        model=resp.model,
        message=AssistantPromptMessage(
            content=text,
            **{"tool_calls": tool_calls} if tool_calls else {},
        ),
        usage=usage,
        system_fingerprint=None,  # Anthropic doesn't have this field
    )


# ── Streaming Response: OpenAI -> Anthropic ───────────────────────────────────


def openai_stream_to_anthropic(
    chunk: ChatCompletionResponseChunk,
) -> list[AnthropicStreamEvent]:
    """Convert a ChatCompletionResponseChunk into Anthropic SSE events.

    Maps OpenAI streaming chunks to Anthropic event types:
    - ChatCompletionResponseChunk -> message_start + content_block_delta + message_delta
    """
    events: list[AnthropicStreamEvent] = []

    # Extract chunk info
    chunk_id = chunk.id or ""
    model = chunk.model or ""
    choices = chunk.choices or []

    # First chunk: message_start event
    if not hasattr(openai_stream_to_anthropic, "_seen_ids"):
        openai_stream_to_anthropic._seen_ids = set()

    is_first = chunk_id and chunk_id not in openai_stream_to_anthropic._seen_ids
    if chunk_id:
        openai_stream_to_anthropic._seen_ids.add(chunk_id)

    if is_first or not chunk_id:
        # Build usage from chunk
        usage = chunk.usage
        anthropic_usage = AnthropicUsage(
            input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
        )
        message_start = AnthropicMessageStartMessage(
            id=chunk_id or f"msg_{id(chunk)}",
            type="message",
            role="assistant",
            content=[],
            model=model,
            usage=anthropic_usage,
        )
        events.append(
            AnthropicMessageStartEvent(
                type="message_start",
                id=chunk_id or f"evt_{id(chunk)}",
                model=model,
                message=message_start,
            )
        )

    # Process deltas
    for choice in choices:
        delta = choice.delta
        index = choice.index

        if delta:
            # Text delta -> content_block_delta
            if delta.content or (delta.text):
                text = delta.content or delta.text or ""
                if text:
                    events.append(
                        AnthropicContentBlockDeltaEvent(
                            type="content_block_delta",
                            id=chunk_id or f"evt_{id(chunk)}",
                            model=model,
                            index=index,
                            delta=AnthropicStreamDelta(
                                type=AnthropicStreamDeltaType.TEXT_DELTA,
                                text=text,
                            ),
                        )
                    )

            # Tool call delta -> content_block_delta with tool_use
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    # Tool use start
                    events.append(
                        AnthropicContentBlockStartEvent(
                            type="content_block_start",
                            id=chunk_id or f"evt_{id(chunk)}",
                            model=model,
                            index=index,
                            content_block=AnthropicContentBlock(
                                type="tool_use",
                                id=tc.id or "",
                                name=tc.function.name or "",
                                input={},
                            ),
                        )
                    )
                    # Tool use delta
                    if tc.function.arguments:
                        events.append(
                            AnthropicContentBlockDeltaEvent(
                                type="content_block_delta",
                                id=chunk_id or f"evt_{id(chunk)}",
                                model=model,
                                index=index,
                                delta=AnthropicStreamDelta(
                                    type=AnthropicStreamDeltaType.INPUT_JSON_DELTA,
                                    partial_json=tc.function.arguments,
                                ),
                            )
                        )

        # Finish reason -> message_delta
        if choice.finish_reason:
            stop_reason = map_stop_reason_to_anthropic(choice.finish_reason)
            events.append(
                AnthropicMessageDeltaEvent(
                    type="message_delta",
                    id=chunk_id or f"evt_{id(chunk)}",
                    model=model,
                    delta=AnthropicMessageDelta(stop_reason=stop_reason),
                    usage=AnthropicUsage(),
                )
            )
            events.append(
                AnthropicMessageStopEvent(
                    type="message_stop",
                    id=chunk_id or f"evt_{id(chunk)}",
                    model=model,
                )
            )

    return events


# ── Streaming Response: Anthropic -> OpenAI ───────────────────────────────────


def anthropic_stream_to_openai(
    event: AnthropicStreamEvent,
) -> ChatCompletionResponseChunk:
    """Convert an Anthropic SSE event into a ChatCompletionResponseChunk.

    Maps Anthropic event types to OpenAI streaming chunks:
    - message_start -> first chunk with id/model
    - content_block_delta -> chunk with text/tool_call delta
    - message_delta -> chunk with finish_reason
    """
    import time

    # Track state for building chunks
    if not hasattr(anthropic_stream_to_openai, "_state"):
        anthropic_stream_to_openai._state = {
            "id": None,
            "model": None,
            "tool_calls": {},
            "finish_reason": None,
            "usage": None,
        }

    state = anthropic_stream_to_openai._state
    delta_message: Optional[AssistantPromptMessage] = None
    finish_reason: Optional[str] = None

    if isinstance(event, AnthropicMessageStartEvent):
        state["id"] = event.message.id if event.message else None
        state["model"] = event.message.model if event.message else None
        state["usage"] = event.message.usage if event.message else None
        state["tool_calls"] = {}
        state["finish_reason"] = None

    elif isinstance(event, AnthropicContentBlockDeltaEvent):
        delta = event.delta
        if delta:
            if delta.type == AnthropicStreamDeltaType.TEXT_DELTA and delta.text:
                delta_message = AssistantPromptMessage(content=delta.text)
            elif delta.type == AnthropicStreamDeltaType.INPUT_JSON_DELTA:
                tc = state["tool_calls"].get(event.index)
                if tc is not None:
                    tc["arguments"] = (tc.get("arguments") or "") + (delta.partial_json or "")
                    delta_message = AssistantPromptMessage(
                        content="",
                        tool_calls=[
                            AssistantPromptMessage.ToolCall(
                                index=event.index,
                                id=tc["id"],
                                type="function",
                                function=AssistantPromptMessage.ToolCall.ToolCallFunction(
                                    name=tc["name"],
                                    arguments=delta.partial_json or "",
                                ),
                            )
                        ],
                    )

    elif isinstance(event, AnthropicContentBlockStartEvent):
        if event.content_block and event.content_block.type == "tool_use":
            state["tool_calls"][event.index] = {
                "id": event.content_block.id,
                "name": event.content_block.name,
                "arguments": "",
            }
            delta_message = AssistantPromptMessage(
                content="",
                tool_calls=[
                    AssistantPromptMessage.ToolCall(
                        index=event.index,
                        id=event.content_block.id,
                        type="function",
                        function=AssistantPromptMessage.ToolCall.ToolCallFunction(
                            name=event.content_block.name,
                            arguments="",
                        ),
                    )
                ],
            )

    elif isinstance(event, AnthropicMessageDeltaEvent):
        if event.delta:
            finish_reason = map_stop_reason_to_openai(
                event.delta.stop_reason.value
                if hasattr(event.delta.stop_reason, "value")
                else str(event.delta.stop_reason or "")
            )
            state["finish_reason"] = finish_reason
        if event.usage:
            state["usage"] = event.usage

    # Build chunk
    chunk = ChatCompletionResponseChunk(
        id=state["id"] or f"chatcmpl-{int(time.time() * 1000)}",
        model=state["model"] or "",
        choices=[],
    )

    if delta_message is not None or finish_reason is not None:
        chunk.choices = [
            ChatCompletionResponseChunkDelta(
                index=0,
                delta=delta_message or AssistantPromptMessage(content=""),
                finish_reason=finish_reason,
            )
        ]

        # Add usage on final chunk
        if isinstance(event, AnthropicMessageDeltaEvent):
            usage = state["usage"] or AnthropicUsage()
            chunk.usage = LLMUsage(
                prompt_tokens=usage.input_tokens,
                completion_tokens=usage.output_tokens,
                total_tokens=usage.input_tokens + usage.output_tokens,
            )

    return chunk


def reset_anthropic_stream_state():
    """Reset streaming state. Call between conversations."""
    if hasattr(anthropic_stream_to_openai, "_state"):
        anthropic_stream_to_openai._state = {
            "id": None,
            "model": None,
            "tool_calls": {},
            "finish_reason": None,
            "usage": None,
        }
    if hasattr(openai_stream_to_anthropic, "_seen_ids"):
        openai_stream_to_anthropic._seen_ids = set()


# ── Tool Call Collection ─────────────────────────────────────────────────────────


class StreamingToolCallCollector:
    """Collects and assembles tool calls from Anthropic streaming events.

    Since tool call arguments are delivered in chunks during streaming,
    this class accumulates partial JSON until the tool call is complete.
    """

    def __init__(self):
        self._tool_calls: dict[str, dict] = {}  # tool_use_id -> {name, arguments, input}
        self._tool_call_index_map: dict[int, str] = {}
        self._message_id: str = ""

    def process_event(self, event: AnthropicStreamEvent) -> None:
        """Process an Anthropic stream event and accumulate tool call data."""
        if isinstance(event, AnthropicMessageStartEvent):
            self._message_id = event.message.id

        if isinstance(event, AnthropicContentBlockStartEvent):
            block = event.content_block
            if block and block.type == "tool_use":
                self._tool_calls[block.id] = {
                    "id": block.id,
                    "name": block.name,
                    "arguments": "",
                    "input": block.input or {},
                }
                self._tool_call_index_map[event.index] = block.id

        elif isinstance(event, AnthropicContentBlockDeltaEvent):
            delta = event.delta
            if delta and delta.type == AnthropicStreamDeltaType.INPUT_JSON_DELTA:
                tool_call_id = self._tool_call_index_map.get(event.index)
                if tool_call_id and tool_call_id in self._tool_calls:
                    self._tool_calls[tool_call_id]["arguments"] += delta.partial_json or ""

    def get_completed_tool_calls(self) -> list[dict]:
        """Get all accumulated tool calls with parsed input."""
        result = []
        for tc in self._tool_calls.values():
            try:
                args = json.loads(tc["arguments"]) if tc["arguments"] else {}
            except json.JSONDecodeError:
                args = {"_partial": tc["arguments"]}
            result.append(
                {
                    "id": tc["id"],
                    "call_id": tc["id"],
                    "name": tc["name"],
                    "arguments": json.dumps(args),
                    "message_id": self._message_id,
                    "input": args,
                }
            )
        return result

    def get_tool_calls_json(self) -> str:
        """Get tool calls as JSON string."""
        return json.dumps(self.get_completed_tool_calls())

    def clear(self) -> None:
        """Clear accumulated tool calls."""
        self._tool_calls.clear()
        self._tool_call_index_map.clear()
        self._message_id: str = ""


def create_anthropic_tool_call_collector() -> StreamingToolCallCollector:
    """Factory function to create a new tool call collector."""
    return StreamingToolCallCollector()
