import logging
from collections.abc import AsyncGenerator
from typing import Optional

from runtime.entities import (
    AnthropicMessageResponse,
    AnthropicStreamEvent,
    AnthropicTextBlock,
    ChatCompletionResponse,
    ChatCompletionResponseChunk,
    LLMResponse,
    LLMStreamResponse,
    ResponseOutput,
    ResponseOutputMessage,
    ResponseStreamEvent,
    TextContentBlock,
)

logger = logging.getLogger(__name__)


class ResponseTextExtractor:
    @classmethod
    def flatten_content(cls, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (list, tuple)):
            return "".join(cls.flatten_content(item) for item in value)
        if isinstance(value, dict):
            text = value.get("text") or value.get("data") or value.get("output")
            if text:
                return str(text)
            for key in ("content", "summary", "action", "image_url"):
                if key in value:
                    return cls.flatten_content(value.get(key))
            for key in ("transcript", "url", "file_id"):
                data = value.get(key)
                if data:
                    return str(data)
            name = value.get("name")
            arguments = value.get("arguments")
            if name or arguments:
                parts: list[str] = []
                if name:
                    parts.append(f"Function call: {name}")
                if arguments:
                    parts.append(f"Arguments: {arguments}")
                return "\n".join(parts)
            return ""

        if isinstance(value, AnthropicTextBlock):
            return value.text or ""
        if isinstance(value, TextContentBlock):
            return value.text or ""
        if isinstance(value, ResponseOutputMessage):
            return cls.flatten_content(value.content)

        summary = getattr(value, "summary", None)
        if summary:
            return "".join(cls.flatten_content(item) for item in summary)

        action = getattr(value, "action", None)
        if action:
            return cls.flatten_content(action)

        image_url = getattr(value, "image_url", None)
        if image_url:
            return cls.flatten_content(image_url)

        content = getattr(value, "content", None)
        if content is not None:
            return cls.flatten_content(content)

        for attr in ("transcript", "text", "data", "output", "url", "file_id"):
            attr_value = getattr(value, attr, None)
            if attr_value:
                return str(attr_value)

        if getattr(value, "name", None) or getattr(value, "arguments", None):
            parts: list[str] = []
            if getattr(value, "name", None):
                parts.append(f"Function call: {value.name}")
            if getattr(value, "arguments", None):
                parts.append(f"Arguments: {value.arguments}")
            return "\n".join(parts)

        return ""

    @classmethod
    def from_response(cls, raw_response: LLMResponse) -> str:
        if isinstance(raw_response, ChatCompletionResponse):
            return cls.flatten_content(getattr(raw_response.message, "content", None))
        if isinstance(raw_response, AnthropicMessageResponse):
            return cls.flatten_content(raw_response.content)
        if isinstance(raw_response, ResponseOutput):
            return "".join(cls.flatten_content(output_item) for output_item in raw_response.output)
        if isinstance(raw_response, LLMStreamResponse):
            from utils import run_async

            return run_async(cls.from_stream, raw_response)
        return str(raw_response) if raw_response else ""

    @classmethod
    async def from_stream(cls, response: LLMStreamResponse) -> str:
        if not isinstance(response, AsyncGenerator):
            return ""

        chat_text_chunks: list[str] = []
        anthropic_text_blocks: dict[int, str] = {}
        latest_response_output: Optional[ResponseOutput] = None
        response_items: dict[int, object] = {}
        response_text_fallback: dict[tuple[int, int], list[str]] = {}

        try:
            async for event in response:
                if isinstance(event, ChatCompletionResponseChunk):
                    choices = event.choices or []
                    if not choices and getattr(event, "delta", None):
                        choices = [event.delta]
                    for choice in choices:
                        delta = getattr(choice, "delta", None) or getattr(choice, "message", None)
                        if delta:
                            content = cls.flatten_content(getattr(delta, "content", None))
                            if content:
                                chat_text_chunks.append(content)
                        if getattr(choice, "text", None):
                            chat_text_chunks.append(choice.text)
                elif isinstance(event, AnthropicStreamEvent):
                    evt_type = getattr(event, "type", "")
                    if evt_type == "content_block_start":
                        block = getattr(event, "content_block", None)
                        if getattr(block, "type", "") == "text":
                            anthropic_text_blocks[event.index] = getattr(block, "text", "") or ""
                    elif evt_type == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if getattr(delta, "text", None):
                            block_index = getattr(event, "index", -1)
                            anthropic_text_blocks[block_index] = anthropic_text_blocks.get(block_index, "") + delta.text
                elif isinstance(event, ResponseStreamEvent):
                    evt_type = getattr(event, "type", "")
                    if hasattr(event, "response"):
                        latest_response_output = getattr(event, "response", None)
                    if evt_type in ("response.output_item.added", "response.output_item.done"):
                        response_items[event.output_index] = event.item
                    elif evt_type in ("response.content_part.added", "response.content_part.done"):
                        item = response_items.get(event.output_index)
                        if item and hasattr(item, "content"):
                            if not getattr(item, "content", None):
                                item.content = []
                            while len(item.content) <= event.content_index:
                                item.content.append(None)
                            item.content[event.content_index] = event.part
                    elif evt_type in ("response.text.delta", "response.text.done"):
                        item = response_items.get(event.output_index)
                        if item and hasattr(item, "content"):
                            if not getattr(item, "content", None):
                                item.content = []
                            while len(item.content) <= event.content_index:
                                item.content.append(TextContentBlock(text=""))
                            block = item.content[event.content_index]
                            if not isinstance(block, TextContentBlock):
                                block = TextContentBlock(text=getattr(block, "text", "") or "")
                                item.content[event.content_index] = block
                            delta_text = (
                                getattr(event, "delta", None)
                                if evt_type == "response.text.delta"
                                else getattr(event, "text", None)
                            )
                            if delta_text:
                                block.text = (block.text or "") + delta_text
                        fallback_key = (event.output_index, event.content_index)
                        if evt_type == "response.text.delta" and getattr(event, "delta", None):
                            response_text_fallback.setdefault(fallback_key, []).append(event.delta)
                        elif evt_type == "response.text.done" and getattr(event, "text", None):
                            response_text_fallback.setdefault(fallback_key, [event.text])
        except Exception as ex:
            logger.error("Error processing stream response for messages: %s", ex)

        if chat_text_chunks:
            return "".join(chat_text_chunks)
        if anthropic_text_blocks:
            return "".join(anthropic_text_blocks[index] for index in sorted(anthropic_text_blocks))
        if latest_response_output and getattr(latest_response_output, "output", None):
            content_text = "".join(cls.flatten_content(output_item) for output_item in latest_response_output.output)
            if content_text:
                return content_text
        if response_items:
            content_text = "".join(cls.flatten_content(response_items[index]) for index in sorted(response_items))
            if content_text:
                return content_text
        if response_text_fallback:
            return "".join("".join(response_text_fallback[key]) for key in sorted(response_text_fallback))
        return ""
