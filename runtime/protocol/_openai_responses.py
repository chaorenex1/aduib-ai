"""
OpenAI Chat Completions <-> OpenAI Responses API bidirectional converter.

Request conversions:
  openai_to_responses: ChatCompletionRequest -> ResponseRequest
  responses_to_openai: ResponseRequest       -> ChatCompletionRequest

Response conversions:
  openai_response_to_responses: ChatCompletionResponse -> ResponseOutput
  responses_to_openai_response: ResponseOutput         -> ChatCompletionResponse
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from runtime.entities.llm_entities import (
    AssistantPromptMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionResponseChunk,
    ChatCompletionResponseChunkDelta,
    LLMUsage,
)
from runtime.entities.response_entities import (
    ResponseContentPartAddedEvent,
    ResponseCreatedEvent,
    ResponseFunctionTool,
    ResponseInProgressEvent,
    ResponseInputItem,
    ResponseOutput,
    ResponseOutputFunctionCall,
    ResponseOutputItem,
    ResponseOutputItemAddedEvent,
    ResponseOutputMessage,
    ResponseRequest,
    ResponseStreamEvent,
    ResponseToolCall,
    TextContentBlock,
)
from runtime.protocol._utils import extract_text_content

logger = logging.getLogger(__name__)


# ── Request: OpenAI -> Responses ─────────────────────────────────────────────


def openai_to_responses(req: ChatCompletionRequest) -> ResponseRequest:
    """Convert a ChatCompletionRequest into a ResponseRequest.

    System messages are converted to instructions field (Responses API does not have
    a separate system field at the request level).
    """
    input_items: list[ResponseInputItem] = []
    instructions: Optional[str] = None

    for msg in req.messages or []:
        role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
        if role == "system":
            # Responses API has no system field; convert to instructions.
            sys_content = extract_text_content(msg.content)
            if sys_content:
                instructions = sys_content if instructions is None else f"{instructions}\n{sys_content}"
            continue
        content = extract_text_content(msg.content)
        input_items.append(ResponseInputItem(role=role, content=content))

    tools: Optional[list[ResponseFunctionTool]] = None
    if req.tools:
        tools = []
        for t in req.tools:
            fn = getattr(t, "function", None) or t
            name = getattr(fn, "name", "") or getattr(t, "name", "")
            desc = getattr(fn, "description", "") or ""
            params = getattr(fn, "parameters", {}) or {}
            tools.append(
                ResponseFunctionTool(
                    name=name,
                    description=desc,
                    parameters=params,
                )
            )

    return ResponseRequest(
        id=getattr(req, "id", None),
        model=req.model or "",
        input=input_items,
        instructions=instructions,
        tools=tools,
        temperature=req.temperature,
        max_tokens=req.max_tokens or req.max_completion_tokens,
        stream=bool(req.stream),
        top_p=req.top_p,
        stop=req.stop,
        frequency_penalty=req.frequency_penalty,
        presence_penalty=req.presence_penalty,
        user=req.user,
    )


# ── Request: Responses -> OpenAI ─────────────────────────────────────────────


def responses_to_openai(req: ResponseRequest) -> ChatCompletionRequest:
    """Convert a ResponseRequest into a ChatCompletionRequest."""
    raw_messages: list[dict[str, Any]] = []

    # Convert instructions to system message
    if req.instructions:
        raw_messages.append({"role": "system", "content": req.instructions})

    if isinstance(req.input, str):
        raw_messages.append({"role": "user", "content": req.input})
    else:
        for item in req.input:
            content = item.content if isinstance(item.content, str) else extract_text_content(item.content)
            raw_messages.append({"role": item.role, "content": content})

    openai_tools: Optional[list[dict]] = None
    if req.tools:
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.parameters or {},
                },
            }
            for t in req.tools
        ]

    # Build response_format from text config if present
    response_format: Optional[dict[str, Any]] = None
    if req.text:
        response_format = {"type": "text"}

    return ChatCompletionRequest(
        id=getattr(req, "id", None),
        model=req.model,
        messages=raw_messages,
        tools=openai_tools,
        tool_choice=req.tool_choice,
        temperature=req.temperature,
        max_tokens=req.max_tokens or req.max_completion_tokens,
        stream=req.stream,
        top_p=req.top_p,
        stop=req.stop,
        frequency_penalty=req.frequency_penalty,
        presence_penalty=req.presence_penalty,
        user=req.user,
        response_format=response_format or req.response_format,
    )


# ── Response: OpenAI -> Responses ────────────────────────────────────────────


def openai_response_to_responses(resp: ChatCompletionResponse) -> ResponseOutput:
    """Convert a ChatCompletionResponse into a ResponseOutput."""
    content = ""
    tool_calls: Optional[list[dict]] = None

    if resp.message:
        content = str(resp.message.content or "")
        if resp.message.tool_calls:
            tool_calls = []
            for tc in resp.message.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                )

    output_items: list[ResponseOutputItem] = []
    if content:
        output_items.append(ResponseOutputItem(role="assistant", content=content))

    # Add tool calls if present
    if tool_calls:
        for tc in tool_calls:
            output_items.append(
                ResponseOutputItem(
                    type="function_call",
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"],
                )
            )

    usage = resp.usage or LLMUsage.empty_usage()
    return ResponseOutput(
        id=resp.id or f"resp_{int(time.time())}",
        created=int(time.time()),
        model=resp.model or "",
        output=output_items,
        usage=usage,
        system_fingerprint=resp.system_fingerprint,
    )


# ── Response: Responses -> OpenAI ────────────────────────────────────────────


def responses_to_openai_response(resp: ResponseOutput) -> ChatCompletionResponse:
    """Convert a ResponseOutput into a ChatCompletionResponse."""
    text = ""
    tool_calls: list[AssistantPromptMessage.ToolCall] = []

    for item in resp.output or []:
        if hasattr(item, "content") and item.content:
            text += str(item.content)
        elif hasattr(item, "type") and item.type == "function_call":
            # Handle function call output
            tool_calls.append(
                AssistantPromptMessage.ToolCall(
                    id=item.id or "",
                    type="function",
                    function=AssistantPromptMessage.ToolCall.ToolCallFunction(
                        name=item.name or "",
                        arguments=item.arguments or "",
                    ),
                )
            )

    usage = (
        resp.usage
        if isinstance(resp.usage, LLMUsage)
        else LLMUsage(
            prompt_tokens=getattr(resp.usage, "prompt_tokens", 0),
            completion_tokens=getattr(resp.usage, "completion_tokens", 0),
            total_tokens=getattr(resp.usage, "total_tokens", 0),
        )
    )

    msg_kwargs: dict[str, Any] = {"content": text}
    if tool_calls:
        msg_kwargs["tool_calls"] = tool_calls

    return ChatCompletionResponse(
        id=resp.id or f"chatcmpl-{int(time.time())}",
        model=resp.model,
        message=AssistantPromptMessage(**msg_kwargs),
        usage=usage,
        system_fingerprint=getattr(resp, "system_fingerprint", None),
    )


# ── Streaming Response: OpenAI -> Responses ─────────────────────────────────────


def openai_stream_to_responses(
    chunk: ChatCompletionResponseChunk,
) -> list[ResponseStreamEvent]:
    """Convert a ChatCompletionResponseChunk into Responses API SSE events.

    Maps OpenAI streaming chunks to Responses API event types.
    """
    events: list[ResponseStreamEvent] = []
    import time as time_module

    chunk_id = chunk.id or f"chatcmpl-{int(time_module.time() * 1000)}"
    model = chunk.model or ""
    choices = chunk.choices or []

    # Track state
    if not hasattr(openai_stream_to_responses, "_state"):
        openai_stream_to_responses._state = {
            "id": chunk_id,
            "created": int(time_module.time()),
            "output": [],
        }
    state = openai_stream_to_responses._state
    state["id"] = chunk_id
    state["model"] = model

    # response.created event on first chunk
    if not hasattr(openai_stream_to_responses, "_initialized"):
        openai_stream_to_responses._initialized = True
        state["output"] = []
        events.append(
            ResponseCreatedEvent(
                type="response.created",
                response=ResponseOutput(
                    id=chunk_id,
                    created=state["created"],
                    model=model,
                    output=[],
                    usage=LLMUsage.empty_usage(),
                ),
            )
        )

    # Process deltas
    for choice in choices:
        delta = choice.delta
        index = choice.index

        if delta:
            text = delta.content or delta.text or ""
            if text:
                # Add text to output
                if not state["output"]:
                    state["output"].append(
                        ResponseOutputMessage(
                            type="message",
                            id=f"msg_{index}",
                            role="assistant",
                            content=[],
                        )
                    )

                # Find or create text content
                msg = state["output"][0]
                text_block = TextContentBlock(type="text", text=text)
                msg.content.append(text_block)

                events.append(
                    ResponseContentPartAddedEvent(
                        type="response.content_part.added",
                        item_id=msg.id,
                        output_index=0,
                        content_index=len(msg.content) - 1,
                        part=text_block,
                    )
                )

            # Tool calls
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    tool_call = ResponseToolCall(
                        id=tc.id or f"call_{index}",
                        type="function",
                        function={
                            "name": tc.function.name or "",
                            "arguments": tc.function.arguments or "",
                        },
                    )
                    state["output"].append(
                        ResponseOutputFunctionCall(
                            type="function_call",
                            id=tc.id or f"call_{index}",
                            call_id=tc.id or f"call_{index}",
                            name=tc.function.name or "",
                            arguments=tc.function.arguments or "",
                        )
                    )
                    events.append(
                        ResponseOutputItemAddedEvent(
                            type="response.output_item.added",
                            output_index=len(state["output"]) - 1,
                            item=state["output"][-1],
                        )
                    )

        # Finish
        if choice.finish_reason:
            usage = chunk.usage or LLMUsage.empty_usage()
            final_response = ResponseOutput(
                id=chunk_id,
                created=state["created"],
                model=model,
                output=state["output"],
                usage=usage,
            )
            events.append(
                ResponseInProgressEvent(
                    type="response.in_progress",
                    response=final_response,
                )
            )

    return events


# ── Streaming Response: Responses -> OpenAI ───────────────────────────────────


def responses_stream_to_openai(
    event: ResponseStreamEvent,
) -> ChatCompletionResponseChunk:
    """Convert a Responses API SSE event into a ChatCompletionResponseChunk."""
    import time as time_module

    # Track state
    if not hasattr(responses_stream_to_openai, "_state"):
        responses_stream_to_openai._state = {
            "id": None,
            "model": None,
            "text": "",
            "tool_calls": [],
            "finish_reason": None,
            "usage": None,
        }
    state = responses_stream_to_openai._state

    if isinstance(event, ResponseCreatedEvent):
        state["id"] = event.response.id
        state["model"] = event.response.model
        state["usage"] = event.response.usage

    elif isinstance(event, ResponseInProgressEvent):
        state["usage"] = event.response.usage
        state["finish_reason"] = "stop"

    elif isinstance(event, ResponseOutputItemAddedEvent):
        item = event.item
        if hasattr(item, "content"):
            # Text content
            for block in item.content:
                if hasattr(block, "text"):
                    state["text"] += block.text or ""
        elif hasattr(item, "type") and item.type == "function_call":
            state["tool_calls"].append(
                {
                    "id": item.id,
                    "name": item.name,
                    "arguments": item.arguments,
                }
            )

    # Build chunk
    chunk = ChatCompletionResponseChunk(
        id=state["id"] or f"chatcmpl-{int(time_module.time() * 1000)}",
        model=state["model"] or "",
        created=int(time_module.time()),
    )

    delta = AssistantPromptMessage(content=state["text"])
    if state["tool_calls"]:
        delta.tool_calls = []
        for tc in state["tool_calls"]:
            delta.tool_calls.append(
                AssistantPromptMessage.ToolCall(
                    id=tc["id"],
                    type="function",
                    function=AssistantPromptMessage.ToolCall.ToolCallFunction(
                        name=tc["name"],
                        arguments=tc["arguments"],
                    ),
                )
            )

    chunk.choices = [
        ChatCompletionResponseChunkDelta(
            index=0,
            delta=delta,
            finish_reason=state["finish_reason"],
        )
    ]

    if state["usage"]:
        chunk.usage = state["usage"]

    return chunk


def reset_responses_stream_state():
    """Reset streaming state. Call between conversations."""
    for func in [openai_stream_to_responses, responses_stream_to_openai]:
        if hasattr(func, "_state"):
            func._state = {
                "id": None,
                "model": None,
                "text": "",
                "tool_calls": [],
                "finish_reason": None,
                "usage": None,
            }
        if hasattr(func, "_initialized"):
            func._initialized = False


# ── Tool Call Collection ─────────────────────────────────────────────────────────


class ResponsesStreamingToolCallCollector:
    """Collects and assembles tool calls from Responses API streaming events.

    Since tool call arguments are delivered in chunks during streaming,
    this class accumulates partial JSON until the tool call is complete.
    """

    def __init__(self):
        self._tool_calls: dict[str, dict] = {}  # call_id -> {name, arguments}
        self._message_id: str = ""

    def process_event(self, event: ResponseStreamEvent) -> None:
        """Process a Responses API stream event and accumulate tool call data."""
        if isinstance(event, ResponseCreatedEvent):
            self._message_id = event.response.id
        if isinstance(event, ResponseOutputItemAddedEvent):
            item = event.item
            if hasattr(item, "type") and item.type == "function_call":
                self._tool_calls[item.id] = {
                    "id": item.id,
                    "call_id": item.call_id,
                    "name": item.name,
                    "arguments": item.arguments or "",
                }

    def process_chunk(self, chunk: ChatCompletionResponseChunk) -> None:
        """Process an OpenAI streaming chunk and accumulate tool call data."""
        if not chunk.choices:
            return
        if len(chunk.id) == 0:
            self._message_id = chunk.id
        for choice in chunk.choices:
            delta = choice.delta
            if delta and delta.tool_calls:
                for tc in delta.tool_calls:
                    tc_id = tc.id or f"call_{len(self._tool_calls)}"
                    if tc_id not in self._tool_calls:
                        self._tool_calls[tc_id] = {
                            "id": tc_id,
                            "call_id": tc_id,
                            "name": "",
                            "arguments": "",
                        }
                    self._tool_calls[tc_id]["name"] = tc.function.name or self._tool_calls[tc_id]["name"]
                    self._tool_calls[tc_id]["arguments"] += tc.function.arguments or ""

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
                    "call_id": tc["call_id"],
                    "name": tc["name"],
                    "arguments": json.dumps(args),
                    "input": args,
                    "message_id": self._message_id,
                }
            )
        return result

    def get_tool_calls_json(self) -> str:
        """Get tool calls as JSON string."""
        return json.dumps(self.get_completed_tool_calls())

    def clear(self) -> None:
        """Clear accumulated tool calls."""
        self._tool_calls.clear()
        self._message_id = ""


def create_responses_tool_call_collector() -> ResponsesStreamingToolCallCollector:
    """Factory function to create a new tool call collector."""
    return ResponsesStreamingToolCallCollector()
