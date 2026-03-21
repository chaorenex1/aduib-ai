import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from runtime.entities import (
    AnthropicMessageResponse,
    AnthropicStreamEvent,
    ChatCompletionResponse,
    ChatCompletionResponseChunk,
    LLMResponse,
    LLMStreamResponse,
    ResponseOutput,
    ResponseOutputFunctionCall,
    ResponseStreamEvent,
)
from runtime.protocol._openai_anthropic import StreamingToolCallCollector
from runtime.protocol._openai_responses import ResponsesStreamingToolCallCollector
from runtime.tool.entities import ToolInvokeParams, ToolProviderType
from runtime.tool.tool_manager import ToolManager

logger = logging.getLogger(__name__)


@dataclass
class ParsedToolCall:
    name: str
    arguments: str
    tool_call_id: str | None = None
    message_id: str | None = None


class ToolCallAdapter:
    def __init__(self, tool_manager: ToolManager):
        self.tool_manager = tool_manager

    @staticmethod
    def _normalize_arguments(arguments: object) -> str:
        if isinstance(arguments, (dict, list)):
            return json.dumps(arguments, ensure_ascii=False)
        if arguments is None:
            return ""
        return str(arguments)

    def _build_invoke_params(self, call: ParsedToolCall) -> ToolInvokeParams | None:
        tool = self.tool_manager.get_builtin_tool_controller().get_tool(call.name)
        if not tool:
            return None
        return ToolInvokeParams(
            name=call.name,
            arguments=self._normalize_arguments(call.arguments),
            message_id=call.message_id,
            tool_call_id=call.tool_call_id,
            tool_provider=tool.tool_provider_type()
            if hasattr(tool, "tool_provider_type")
            else ToolProviderType.BUILTIN,
        )

    def from_response(self, response: LLMResponse) -> list[ToolInvokeParams]:
        parsed_calls: list[ParsedToolCall] = []
        if isinstance(response, ChatCompletionResponse) and response.message.tool_calls:
            for call in response.message.tool_calls:
                parsed_calls.append(
                    ParsedToolCall(
                        name=call.function.name,
                        arguments=call.function.arguments,
                        tool_call_id=call.id,
                        message_id=response.id,
                    )
                )
        elif isinstance(response, AnthropicMessageResponse):
            for content in response.content:
                from runtime.entities import AnthropicToolUseBlock

                if isinstance(content, AnthropicToolUseBlock) and content.type == "tool_use":
                    parsed_calls.append(
                        ParsedToolCall(
                            name=content.name,
                            arguments=self._normalize_arguments(content.input),
                            tool_call_id=content.id,
                            message_id=response.id,
                        )
                    )
        elif isinstance(response, ResponseOutput):
            for content in response.output:
                if isinstance(content, ResponseOutputFunctionCall):
                    parsed_calls.append(
                        ParsedToolCall(
                            name=content.name,
                            arguments=self._normalize_arguments(content.arguments),
                            tool_call_id=content.call_id,
                            message_id=response.id,
                        )
                    )

        tool_calls: list[ToolInvokeParams] = []
        for parsed_call in parsed_calls:
            invoke_params = self._build_invoke_params(parsed_call)
            if invoke_params:
                tool_calls.append(invoke_params)
        return tool_calls

    async def from_stream(
        self,
        response: LLMStreamResponse,
        collector: StreamingToolCallCollector | ResponsesStreamingToolCallCollector,
    ) -> list[ToolInvokeParams]:
        tool_calls: list[ToolInvokeParams] = []
        if not isinstance(response, AsyncGenerator):
            return tool_calls

        try:
            async for result in response:
                if isinstance(result, ChatCompletionResponseChunk):
                    collector.process_chunk(result)
                elif isinstance(result, AnthropicStreamEvent) or isinstance(result, ResponseStreamEvent):
                    collector.process_event(result)
        except Exception as ex:
            logger.error("Error processing stream response for tools: %s", ex)
        finally:
            parsed_calls = [
                ParsedToolCall(
                    name=tool_call["name"],
                    arguments=self._normalize_arguments(tool_call.get("arguments")),
                    tool_call_id=tool_call.get("call_id"),
                    message_id=tool_call.get("message_id"),
                )
                for tool_call in collector.get_completed_tool_calls()
            ]
            for parsed_call in parsed_calls:
                invoke_params = self._build_invoke_params(parsed_call)
                if invoke_params:
                    tool_calls.append(invoke_params)
            collector.clear()

        return tool_calls
