import decimal
import json
import logging
import time
import traceback
import warnings
from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from typing import Any, Optional

from pydantic import ConfigDict

from configs import config

from ..callbacks.base_callback import Callback
from ..callbacks.console_callback import LoggingCallback
from ..entities import (
    AnthropicStreamEvent,
    AssistantPromptMessage,
    ChatCompletionResponse,
    ChatCompletionResponseChunk,
    LLMUsage,
    PromptMessage,
    PromptMessageFunction,
    PromptMessageTool,
    ResponseStreamEvent,
)
from ..entities.anthropic_entities import AnthropicMessageRequest
from ..entities.llm_entities import (
    AnthropicMessageResponse,
    ChatCompletionRequest,
    LLMRequest,
    LLMResponse,
    LLMStreamResponse,
)
from ..entities.model_entities import ModelType, PriceConfig, PriceInfo, PriceType
from ..entities.protocol_entities import ExternalProtocol
from ..entities.provider_entities import ProviderSDKType
from ..entities.response_entities import ResponseOutput, ResponseRequest
from ..protocol import ProtocolConverter
from .base import AiModel

logger = logging.getLogger(__name__)


@dataclass
class NormalizedUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    thinking_tokens: int = 0
    cached_tokens: int = 0
    cache_write_tokens: int = 0

    def merge(self, other: "NormalizedUsage") -> None:
        self.prompt_tokens = max(self.prompt_tokens, other.prompt_tokens)
        self.completion_tokens += other.completion_tokens
        self.thinking_tokens += other.thinking_tokens
        self.cached_tokens = max(self.cached_tokens, other.cached_tokens)
        self.cache_write_tokens = max(self.cache_write_tokens, other.cache_write_tokens)


class ProtocolNormalizer:
    @staticmethod
    def _safe_int(value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, bool):
            return int(value)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _extract_text_content(content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("data") or ""
                    if text:
                        parts.append(str(text))
                elif hasattr(item, "text") and item.text:
                    parts.append(str(item.text))
                elif hasattr(item, "data") and item.data:
                    parts.append(str(item.data))
            return "".join(parts)
        return str(content)

    @staticmethod
    def _tool_call_function(
        name: str | None, arguments: str | None
    ) -> AssistantPromptMessage.ToolCall.ToolCallFunction:
        return AssistantPromptMessage.ToolCall.ToolCallFunction(name=name, arguments=arguments)

    @staticmethod
    def _as_tool_call(data: Any) -> Optional[AssistantPromptMessage.ToolCall]:
        if data is None:
            return None
        if isinstance(data, AssistantPromptMessage.ToolCall):
            return data

        if hasattr(data, "model_dump"):
            data = data.model_dump()

        if isinstance(data, dict):
            fn = data.get("function") or {}
            fn_name = fn.get("name") if isinstance(fn, dict) else getattr(fn, "name", None)
            fn_args = fn.get("arguments") if isinstance(fn, dict) else getattr(fn, "arguments", None)
            return AssistantPromptMessage.ToolCall(
                index=data.get("index"),
                id=data.get("id"),
                type=data.get("type"),
                function=ProtocolNormalizer._tool_call_function(
                    str(fn_name) if fn_name is not None else None,
                    str(fn_args) if fn_args is not None else None,
                ),
            )

        fn_obj = getattr(data, "function", None)
        fn_name = getattr(fn_obj, "name", None) if fn_obj is not None else None
        fn_args = getattr(fn_obj, "arguments", None) if fn_obj is not None else None
        return AssistantPromptMessage.ToolCall(
            index=getattr(data, "index", None),
            id=getattr(data, "id", None),
            type=getattr(data, "type", None),
            function=ProtocolNormalizer._tool_call_function(
                str(fn_name) if fn_name is not None else None,
                str(fn_args) if fn_args is not None else None,
            ),
        )

    @staticmethod
    def _normalized_from_openai_like_usage(usage: Any) -> NormalizedUsage:
        if usage is None:
            return NormalizedUsage()

        if isinstance(usage, LLMUsage):
            return NormalizedUsage(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                thinking_tokens=getattr(usage, "thinking_tokens", 0) or 0,
                cached_tokens=getattr(usage, "cached_tokens", 0) or 0,
            )

        if hasattr(usage, "model_dump"):
            usage = usage.model_dump()

        if isinstance(usage, dict):
            prompt_tokens = ProtocolNormalizer._safe_int(usage.get("prompt_tokens"))
            completion_tokens = ProtocolNormalizer._safe_int(usage.get("completion_tokens"))
            thinking_tokens = ProtocolNormalizer._safe_int(
                usage.get("thinking_tokens") or usage.get("reasoning_tokens")
            )
            cached_tokens = ProtocolNormalizer._safe_int(usage.get("cached_tokens"))
            prompt_details = usage.get("prompt_tokens_details") or {}
            if isinstance(prompt_details, dict):
                cached_tokens = max(cached_tokens, ProtocolNormalizer._safe_int(prompt_details.get("cached_tokens")))
            return NormalizedUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                thinking_tokens=thinking_tokens,
                cached_tokens=cached_tokens,
            )

        prompt_tokens = ProtocolNormalizer._safe_int(getattr(usage, "prompt_tokens", 0))
        completion_tokens = ProtocolNormalizer._safe_int(getattr(usage, "completion_tokens", 0))
        thinking_tokens = ProtocolNormalizer._safe_int(
            getattr(usage, "thinking_tokens", None) or getattr(usage, "reasoning_tokens", None) or 0
        )
        cached_tokens = ProtocolNormalizer._safe_int(getattr(usage, "cached_tokens", 0))
        return NormalizedUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            thinking_tokens=thinking_tokens,
            cached_tokens=cached_tokens,
        )

    @staticmethod
    def _normalized_from_anthropic_usage(usage: Any) -> NormalizedUsage:
        if usage is None:
            return NormalizedUsage()

        if hasattr(usage, "model_dump"):
            usage = usage.model_dump()

        if isinstance(usage, dict):
            return NormalizedUsage(
                prompt_tokens=ProtocolNormalizer._safe_int(usage.get("input_tokens")),
                completion_tokens=ProtocolNormalizer._safe_int(usage.get("output_tokens")),
                cached_tokens=ProtocolNormalizer._safe_int(usage.get("cache_read_input_tokens")),
                cache_write_tokens=ProtocolNormalizer._safe_int(usage.get("cache_creation_input_tokens")),
            )

        return NormalizedUsage(
            prompt_tokens=ProtocolNormalizer._safe_int(getattr(usage, "input_tokens", 0)),
            completion_tokens=ProtocolNormalizer._safe_int(getattr(usage, "output_tokens", 0)),
            cached_tokens=ProtocolNormalizer._safe_int(getattr(usage, "cache_read_input_tokens", 0)),
            cache_write_tokens=ProtocolNormalizer._safe_int(getattr(usage, "cache_creation_input_tokens", 0)),
        )

    @staticmethod
    def extract_full(result: Any) -> tuple[str, list[AssistantPromptMessage.ToolCall], NormalizedUsage, Optional[str]]:
        text = ""
        tool_calls: list[AssistantPromptMessage.ToolCall] = []
        usage = NormalizedUsage()
        system_fingerprint: Optional[str] = None

        if isinstance(result, ChatCompletionResponse):
            system_fingerprint = getattr(result, "system_fingerprint", None)
            if getattr(result, "message", None) is not None:
                if getattr(result.message, "content", None) is not None:
                    text += ProtocolNormalizer._extract_text_content(result.message.content)
                if getattr(result.message, "tool_calls", None):
                    for tc in result.message.tool_calls or []:
                        tool_call = ProtocolNormalizer._as_tool_call(tc)
                        if tool_call is not None:
                            tool_calls.append(tool_call)

            if not text and not tool_calls:
                for choice in getattr(result, "choices", None) or []:
                    if getattr(choice, "message", None) and getattr(choice.message, "content", None) is not None:
                        text += ProtocolNormalizer._extract_text_content(choice.message.content)
                    if getattr(choice, "text", None):
                        text += str(choice.text)
                    if getattr(choice, "message", None) and getattr(choice.message, "tool_calls", None):
                        for tc in choice.message.tool_calls or []:
                            tool_call = ProtocolNormalizer._as_tool_call(tc)
                            if tool_call is not None:
                                tool_calls.append(tool_call)

            usage = ProtocolNormalizer._normalized_from_openai_like_usage(getattr(result, "usage", None))
            return text, tool_calls, usage, system_fingerprint

        if isinstance(result, AnthropicMessageResponse):
            system_fingerprint = "claude"
            for block in result.content or []:
                block_type = getattr(block, "type", None)
                if block_type == "text":
                    text += str(getattr(block, "text", "") or "")
                elif block_type == "thinking":
                    text += str(getattr(block, "thinking", "") or "")
                elif block_type == "redacted_thinking":
                    text += str(getattr(block, "data", "") or "")
                elif block_type in {"tool_use", "server_tool_use"}:
                    args_json = json.dumps(getattr(block, "input", {}) or {}, ensure_ascii=False, default=str)
                    tool_calls.append(
                        AssistantPromptMessage.ToolCall(
                            id=getattr(block, "id", None),
                            type="function",
                            function=ProtocolNormalizer._tool_call_function(getattr(block, "name", None), args_json),
                        )
                    )
                elif block_type == "tool_result":
                    content = getattr(block, "content", "")
                    text += ProtocolNormalizer._extract_text_content(content)

            usage = ProtocolNormalizer._normalized_from_anthropic_usage(getattr(result, "usage", None))
            return text, tool_calls, usage, system_fingerprint

        if isinstance(result, ResponseOutput):
            for item in result.output or []:
                item_type = getattr(item, "type", None)
                if item_type == "message":
                    for part in getattr(item, "content", None) or []:
                        if getattr(part, "type", None) == "text":
                            text += str(getattr(part, "text", "") or "")
                    for tc in getattr(item, "tool_calls", None) or []:
                        tool_call = ProtocolNormalizer._as_tool_call(
                            {
                                "id": getattr(tc, "id", None),
                                "type": getattr(tc, "type", None),
                                "function": getattr(tc, "function", None),
                            }
                        )
                        if tool_call is not None:
                            tool_calls.append(tool_call)
                elif item_type == "function_call":
                    tool_calls.append(
                        AssistantPromptMessage.ToolCall(
                            id=getattr(item, "call_id", None) or getattr(item, "id", None),
                            type="function",
                            function=ProtocolNormalizer._tool_call_function(
                                getattr(item, "name", None), str(getattr(item, "arguments", "") or "")
                            ),
                        )
                    )

            usage = ProtocolNormalizer._normalized_from_openai_like_usage(getattr(result, "usage", None))
            return text, tool_calls, usage, system_fingerprint

        text = ProtocolNormalizer._extract_text_content(getattr(result, "content", None) or str(result))
        return text, tool_calls, usage, system_fingerprint

    @staticmethod
    def extract_chunk(chunk: Any) -> tuple[str, list[AssistantPromptMessage.ToolCall], NormalizedUsage, Optional[str]]:
        delta_text = ""
        new_tool_calls: list[AssistantPromptMessage.ToolCall] = []
        usage = NormalizedUsage()
        system_fingerprint: Optional[str] = None

        if isinstance(chunk, ChatCompletionResponseChunk):
            system_fingerprint = getattr(chunk, "system_fingerprint", None)

            deltas: list[Any]
            if getattr(chunk, "choices", None):
                deltas = list(chunk.choices or [])
            elif getattr(chunk, "delta", None):
                deltas = [chunk.delta]
            else:
                deltas = []

            for choice in deltas:
                if getattr(choice, "delta", None) and getattr(choice.delta, "content", None) is not None:
                    delta_text += ProtocolNormalizer._extract_text_content(choice.delta.content)
                if getattr(choice, "text", None):
                    delta_text += str(choice.text)

                tool_call_candidates: list[Any] = []
                if getattr(choice, "delta", None) and getattr(choice.delta, "tool_calls", None):
                    tool_call_candidates.extend(choice.delta.tool_calls or [])
                if getattr(choice, "message", None) and getattr(choice.message, "tool_calls", None):
                    tool_call_candidates.extend(choice.message.tool_calls or [])

                for tc in tool_call_candidates:
                    tool_call = ProtocolNormalizer._as_tool_call(tc)
                    if tool_call is not None:
                        new_tool_calls.append(tool_call)

            usage_obj = None
            if getattr(chunk, "delta", None) and getattr(chunk.delta, "usage", None):
                usage_obj = chunk.delta.usage
            elif getattr(chunk, "usage", None):
                usage_obj = chunk.usage
            usage = ProtocolNormalizer._normalized_from_openai_like_usage(usage_obj)
            return delta_text, new_tool_calls, usage, system_fingerprint

        if isinstance(chunk, AnthropicStreamEvent):
            system_fingerprint = "claude"
            if getattr(chunk, "usage", None):
                usage = ProtocolNormalizer._normalized_from_anthropic_usage(getattr(chunk, "usage", None))
            if getattr(chunk, "message", None) and getattr(chunk.message, "usage", None):
                usage = ProtocolNormalizer._normalized_from_anthropic_usage(chunk.message.usage)

            delta = getattr(chunk, "delta", None)
            if delta is not None:
                if hasattr(delta, "model_dump"):
                    delta = delta.model_dump()
                if isinstance(delta, dict):
                    delta_type = delta.get("type")
                    if delta_type == "text_delta":
                        delta_text += str(delta.get("text", "") or "")
                    elif delta_type == "thinking_delta":
                        delta_text += str(delta.get("thinking", "") or "")
                    elif delta_type == "input_json_delta":
                        delta_text += str(delta.get("partial_json", "") or "")
                else:
                    delta_type = getattr(delta, "type", None)
                    if str(delta_type) == "text_delta":
                        delta_text += str(getattr(delta, "text", "") or "")
                    elif str(delta_type) == "thinking_delta":
                        delta_text += str(getattr(delta, "thinking", "") or "")
                    elif str(delta_type) == "input_json_delta":
                        delta_text += str(getattr(delta, "partial_json", "") or "")

            return delta_text, new_tool_calls, usage, system_fingerprint

        if isinstance(chunk, ResponseStreamEvent):
            usage_obj = None
            if getattr(chunk, "usage", None) is not None:
                usage_obj = getattr(chunk, "usage", None)
            if getattr(chunk, "response", None) is not None and getattr(chunk.response, "usage", None) is not None:
                usage_obj = chunk.response.usage

            if usage_obj is not None:
                usage = ProtocolNormalizer._normalized_from_openai_like_usage(usage_obj)

            if hasattr(chunk, "output") and getattr(chunk, "output", None):
                for item in chunk.output or []:
                    if getattr(item, "content", None):
                        delta_text += str(item.content)
                    for tc in getattr(item, "tool_calls", None) or []:
                        tool_call = ProtocolNormalizer._as_tool_call(
                            {
                                "id": getattr(tc, "id", None),
                                "type": getattr(tc, "type", None),
                                "function": getattr(tc, "function", None),
                            }
                        )
                        if tool_call is not None:
                            new_tool_calls.append(tool_call)
                return delta_text, new_tool_calls, usage, system_fingerprint

            event_type = getattr(chunk, "type", "") or ""
            if (
                event_type == "response.text.delta"
                and hasattr(chunk, "delta")
                or event_type == "response.refusal.delta"
                and hasattr(chunk, "delta")
            ):
                delta_text += str(getattr(chunk, "delta", "") or "")
            elif hasattr(chunk, "item") and getattr(chunk, "item", None) is not None:
                item = chunk.item
                item_type = getattr(item, "type", None)
                if item_type == "message":
                    for part in getattr(item, "content", None) or []:
                        if getattr(part, "type", None) == "text":
                            delta_text += str(getattr(part, "text", "") or "")
                    for tc in getattr(item, "tool_calls", None) or []:
                        tool_call = ProtocolNormalizer._as_tool_call(
                            {
                                "id": getattr(tc, "id", None),
                                "type": getattr(tc, "type", None),
                                "function": getattr(tc, "function", None),
                            }
                        )
                        if tool_call is not None:
                            new_tool_calls.append(tool_call)
                elif item_type == "function_call":
                    new_tool_calls.append(
                        AssistantPromptMessage.ToolCall(
                            id=getattr(item, "call_id", None) or getattr(item, "id", None),
                            type="function",
                            function=ProtocolNormalizer._tool_call_function(
                                getattr(item, "name", None), str(getattr(item, "arguments", "") or "")
                            ),
                        )
                    )

            return delta_text, new_tool_calls, usage, system_fingerprint

        return delta_text, new_tool_calls, usage, system_fingerprint


class ResponseCollector:
    def __init__(self, model: str, message_id: str) -> None:
        self.model = model
        self.message_id = message_id
        self._text: str = ""
        self._tool_calls: list[AssistantPromptMessage.ToolCall] = []
        self._usage: NormalizedUsage = NormalizedUsage()
        self._system_fingerprint: Optional[str] = None
        self._stop_reason: Optional[str] = None

    def accept_full(self, result: Any) -> None:
        text, tool_calls, usage, fingerprint = ProtocolNormalizer.extract_full(result)
        self._text = text
        self._tool_calls = tool_calls
        self._usage = usage
        self._system_fingerprint = fingerprint
        if hasattr(result, "stop_reason"):
            self._stop_reason = getattr(result, "stop_reason", None)

    def accept_chunk(self, chunk: Any) -> tuple[str, list[AssistantPromptMessage.ToolCall]]:
        delta_text, new_tool_calls, chunk_usage, fingerprint = ProtocolNormalizer.extract_chunk(chunk)
        self._text += delta_text
        self._tool_calls.extend(new_tool_calls)
        self._usage.merge(chunk_usage)
        if fingerprint:
            self._system_fingerprint = fingerprint
        return delta_text, new_tool_calls

    def build_response(self, llm_model: "LlMModel") -> ChatCompletionResponse:
        llm_usage = llm_model.calc_response_usage(
            self.model,
            self._usage.prompt_tokens,
            self._usage.completion_tokens,
            self._usage.thinking_tokens,
            self._usage.cached_tokens,
            self._usage.cache_write_tokens,
        )
        chat = ChatCompletionResponse(
            model=self.model,
            id=self.message_id,
            message=AssistantPromptMessage(content=self._text, tool_calls=self._tool_calls),
            usage=llm_usage,
            system_fingerprint=self._system_fingerprint,
        )
        if self._stop_reason is not None:
            chat.done = True
        return chat


class LlMModel(AiModel):
    """
    Base class for all LLM models.
    """

    model_type: ModelType = ModelType.LLM

    model_config = ConfigDict(protected_namespaces=())

    @staticmethod
    def _detect_request_protocol(req: LLMRequest) -> Optional[ExternalProtocol]:
        if isinstance(req, ChatCompletionRequest):
            return ExternalProtocol.OPENAI_CHAT
        if isinstance(req, AnthropicMessageRequest):
            return ExternalProtocol.ANTHROPIC_MESSAGES
        if isinstance(req, ResponseRequest):
            return ExternalProtocol.OPENAI_RESPONSES
        return None

    @staticmethod
    def _detect_provider_protocol(provider_type: Any) -> Optional[ExternalProtocol]:
        if isinstance(provider_type, str):
            try:
                provider_type = ProviderSDKType.value_of(provider_type)
            except ValueError:
                return None

        if provider_type == ProviderSDKType.ANTHROPIC:
            return ExternalProtocol.ANTHROPIC_MESSAGES
        if provider_type == ProviderSDKType.OPENAI:
            return ExternalProtocol.OPENAI_RESPONSES
        if provider_type in {
            ProviderSDKType.OPENAI_LIKE,
            ProviderSDKType.DEEPSEEK,
            ProviderSDKType.OPENROUTER,
            ProviderSDKType.GITHUB,
            ProviderSDKType.GITHUB_COPILOT,
        }:
            return ExternalProtocol.OPENAI_CHAT
        return None

    async def invoke(
        self,
        req: LLMRequest,
        source: Optional[str] = None,
        callbacks: Optional[list[Callback]] = None,
        user: Optional[str] = None,
        agent_id: Optional[int] = None,
        agent_session_id: Optional[int] = None,
    ) -> LLMResponse:
        """
        Invoke large language model

        :param req: prompt messages (supports ChatCompletionRequest, CompletionRequest, AnthropicMessageRequest, ResponseRequest)
        :param callbacks: callbacks
        :return: LLMResponse (full response or stream response chunk generator)
        """

        self.started_at = time.perf_counter()

        callbacks = callbacks or []

        from ..transformation import get_llm_transformation

        provider_type = self.credentials.get("sdk_type", "openai_like")
        ingress_protocol = self._detect_request_protocol(req)
        provider_protocol = self._detect_provider_protocol(provider_type)
        adapted_req = req
        if ingress_protocol and provider_protocol and ingress_protocol != provider_protocol:
            adapted_req = ProtocolConverter.adapt_request(
                req,
                source_protocol=ingress_protocol,
                target_protocol=provider_protocol,
            )

        transformation = get_llm_transformation(provider_type)
        credentials = transformation.setup_environment(self.credentials, self.model_params)
        req = transformation.setup_model_parameters(credentials, self.model_params, adapted_req)

        stream: bool = req.stream
        model: str = req.model
        tools: Optional[list[PromptMessageTool]] = []

        include_reasoning: bool = False
        message_id: Optional[str] = self.get_message_id()
        if isinstance(req, ChatCompletionRequest):
            include_reasoning = req.include_reasoning or req.enable_thinking or req.thinking is not None
            tools = req.tools
            # if tools:
            #     stream = False  # disable stream for tool calling
        stop: Optional[Sequence[str]] = getattr(req, "stop", None) or getattr(req, "stop_sequences", None)

        parameters = {
            "message_id": message_id,
            "temperature": getattr(req, "temperature", None),
            "top_p": getattr(req, "top_p", None),
            "max_tokens": getattr(req, "max_tokens", None),
            "max_completion_tokens": getattr(req, "max_completion_tokens", None),
            "top_k": getattr(req, "top_k", None),
            "presence_penalty": getattr(req, "presence_penalty", None),
            "frequency_penalty": getattr(req, "frequency_penalty", None),
            "response_format": getattr(req, "response_format", None),
        }

        if config.DEBUG:
            callbacks.append(LoggingCallback())

        # trigger before invoke callbacks
        self._trigger_before_invoke_callbacks(
            model=model,
            credentials=credentials,
            prompt_messages=self.get_messages(req),
            model_parameters=parameters,
            tools=tools,
            stop=stop,
            stream=stream,
            include_reasoning=include_reasoning,
            callbacks=callbacks,
            user=user,
            agent_id=agent_id,
            agent_session_id=agent_session_id,
        )

        result: LLMResponse

        try:
            # invoke model
            result = await transformation.transform_message(
                model_params=self.model_params,
                prompt_messages=req,
                credentials=credentials,
                stream=stream,
                source=source,
            )

        except Exception as e:
            self._trigger_invoke_error_callbacks(
                model=model,
                ex=e,
                credentials=credentials,
                prompt_messages=self.get_messages(req),
                model_parameters=parameters,
                tools=tools,
                stop=stop,
                stream=stream,
                callbacks=callbacks,
                user=user,
                include_reasoning=include_reasoning,
                agent_id=agent_id,
                agent_session_id=agent_session_id,
            )
            raise e

        if stream and isinstance(result, AsyncGenerator):
            return self._invoke_result_generator(
                model=model,
                result=result,
                credentials=credentials,
                req=req,
                source_protocol=provider_protocol,
                target_protocol=ingress_protocol,
                model_parameters=parameters,
                tools=tools,
                stop=stop,
                stream=stream,
                callbacks=callbacks,
                message_id=message_id,
                user=user,
                include_reasoning=include_reasoning,
                agent_id=agent_id,
                agent_session_id=agent_session_id,
            )
        elif isinstance(result, (ChatCompletionResponse, AnthropicMessageResponse, ResponseOutput)):
            # 统一后处理
            normalized_chat = self._post_process(
                result=result,
                model=model,
                message_id=message_id,
                credentials=credentials,
                prompt_messages=self.get_messages(req),
                model_parameters=parameters,
                tools=tools,
                stop=stop,
                stream=stream,
                callbacks=callbacks,
                user=user,
                include_reasoning=include_reasoning,
                agent_id=agent_id,
                agent_session_id=agent_session_id,
            )
            if not ingress_protocol or not provider_protocol:
                return normalized_chat
            if ingress_protocol == provider_protocol:
                if ingress_protocol == ExternalProtocol.OPENAI_CHAT:
                    return normalized_chat
                return result
            return ProtocolConverter.adapt_response(
                result,
                source_protocol=provider_protocol,
                target_protocol=ingress_protocol,
            )
        raise NotImplementedError("unsupported invoke result type", type(result))

    async def _invoke_result_generator(
        self,
        model: str,
        result: LLMStreamResponse,
        credentials: dict,
        req: LLMRequest,
        source_protocol: Optional[ExternalProtocol],
        target_protocol: Optional[ExternalProtocol],
        model_parameters: dict,
        tools: Optional[list[PromptMessageFunction]] = None,
        stop: Optional[Sequence[str]] = None,
        stream: bool = True,
        callbacks: Optional[list[Callback]] = None,
        message_id: Optional[str] = None,
        user: Optional[str] = None,
        include_reasoning: bool = False,
        agent_id: Optional[int] = None,
        agent_session_id: Optional[int] = None,
    ) -> LLMStreamResponse:
        """
        Invoke result generator

        :param result: result generator
        :return: LLMStreamResponse (stream response chunk generator)
        """
        callbacks = callbacks or []
        collector = ResponseCollector(model=model, message_id=message_id or "")
        prompt_messages = self.get_messages(req)
        stream_error: Optional[Exception] = None

        try:
            async for chunk in result:
                # 设置 prompt_messages
                collector.accept_chunk(chunk)
                chunk.prompt_messages = prompt_messages

                # 触发 new_chunk 回调
                self._trigger_new_chunk_callbacks(
                    chunk=chunk,
                    model=model,
                    credentials=credentials,
                    prompt_messages=prompt_messages,
                    model_parameters=model_parameters,
                    tools=tools,
                    stop=stop,
                    stream=stream,
                    callbacks=callbacks,
                    user=user,
                    include_reasoning=include_reasoning,
                    agent_id=agent_id,
                    agent_session_id=agent_session_id,
                )

                outgoing_chunks: list[Any] = [chunk]
                if source_protocol and target_protocol and source_protocol != target_protocol:
                    outgoing_chunks = ProtocolConverter.adapt_stream_event(
                        chunk,
                        source_protocol=source_protocol,
                        target_protocol=target_protocol,
                    )

                for outgoing_chunk in outgoing_chunks:
                    if hasattr(outgoing_chunk, "prompt_messages"):
                        outgoing_chunk.prompt_messages = prompt_messages
                    yield outgoing_chunk

        except Exception as e:
            stream_error = e
            self._trigger_invoke_error_callbacks(
                model=model,
                ex=e,
                credentials=credentials,
                prompt_messages=list(prompt_messages),
                model_parameters=model_parameters,
                tools=tools,
                stop=stop,
                stream=stream,
                callbacks=callbacks,
                user=user,
                include_reasoning=include_reasoning,
                agent_id=agent_id,
                agent_session_id=agent_session_id,
            )
            logger.exception("Error in stream processing: {e}", exc_info=True)
            raise e
        finally:
            if stream_error is None:
                try:
                    chat = collector.build_response(self)
                    chat.prompt_messages = prompt_messages
                    self._trigger_after_invoke_callbacks(
                        model=model,
                        result=chat,
                        credentials=credentials,
                        prompt_messages=prompt_messages,
                        model_parameters=model_parameters,
                        tools=tools,
                        stop=stop,
                        stream=stream,
                        callbacks=callbacks,
                        user=user,
                        include_reasoning=include_reasoning,
                        agent_id=agent_id,
                        agent_session_id=agent_session_id,
                    )
                except Exception as e:
                    logger.exception("Error in after invoke callback: {e}", exc_info=True)

    def calc_response_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        thinking_tokens: int = 0,
        cached_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> LLMUsage:
        """
        Calculate response usage based on prompt, completion, thinking and cached tokens
        :param model: model name
        :param prompt_tokens: number of prompt tokens
        :param completion_tokens: number of completion tokens
        :param thinking_tokens: number of thinking/reasoning tokens
        :param cached_tokens: number of cached tokens (cache hits)
        :param cache_write_tokens: number of cache write tokens
        :return: LLMUsage object with calculated usage
        """
        prompt_price_info = self.get_price_info(model, PriceType.INPUT, prompt_tokens)
        completion_price_info = self.get_price_info(model, PriceType.OUTPUT, completion_tokens)
        thinking_price_info = self.get_price_info(model, PriceType.THINKING, thinking_tokens)
        cache_price_info = self.get_price_info(model, PriceType.CACHE_READ, cached_tokens)
        cache_write_price_info = self.get_price_info(model, PriceType.CACHE_WRITE, cache_write_tokens)

        total_tokens = prompt_tokens + completion_tokens
        total_price = (
            prompt_price_info.total_amount
            + completion_price_info.total_amount
            + thinking_price_info.total_amount
            + cache_price_info.total_amount
            + cache_write_price_info.total_amount
        )

        return LLMUsage(
            prompt_tokens=prompt_tokens,
            prompt_unit_price=prompt_price_info.unit_price,
            prompt_price_unit=prompt_price_info.unit,
            prompt_price=prompt_price_info.total_amount,
            completion_tokens=completion_tokens,
            completion_unit_price=completion_price_info.unit_price,
            completion_price_unit=completion_price_info.unit,
            completion_price=completion_price_info.total_amount,
            thinking_tokens=thinking_tokens,
            thinking_unit_price=thinking_price_info.unit_price,
            thinking_price=thinking_price_info.total_amount,
            cached_tokens=cached_tokens,
            cache_unit_price=cache_price_info.unit_price,
            cache_price=cache_price_info.total_amount,
            cache_write_tokens=cache_write_tokens,
            cache_write_unit_price=cache_write_price_info.unit_price,
            cache_write_price=cache_write_price_info.total_amount,
            total_tokens=total_tokens,
            total_price=total_price,
            currency=prompt_price_info.currency or "USD",
            latency=time.perf_counter() - self.started_at,
        )

    def get_price_info(self, model: str, price_type: PriceType, tokens: int) -> PriceInfo:
        """
        Get price info for given model and price type

        :param model: model name
        :param price_type: price type
        :param tokens: number of tokens
        :return: price info
        """
        model_schema = self.get_model_schema(model)
        price_config: Optional[PriceConfig] = None
        if model_schema and model_schema.pricing:
            price_config = model_schema.pricing

        unit_price = None
        if price_config:
            if price_type == PriceType.INPUT and price_config.input is not None:
                unit_price = price_config.input
            elif price_type == PriceType.OUTPUT and price_config.output is not None:
                unit_price = price_config.output
            elif price_type == PriceType.THINKING and price_config.thinking is not None:
                unit_price = price_config.thinking
            elif price_type == PriceType.CACHE_READ and price_config.cache_read is not None:
                unit_price = price_config.cache_read
            elif price_type == PriceType.CACHE_WRITE and price_config.cache_write is not None:
                unit_price = price_config.cache_write
        if unit_price is None:
            return PriceInfo(
                unit_price=decimal.Decimal(0.0),
                unit=decimal.Decimal(0.0),
                currency="USD",
                total_amount=decimal.Decimal(0.0),
            )

        if not price_config:
            raise ValueError(f"Model {model} does not have pricing info")

        total_amount = tokens * unit_price * price_config.unit
        total_amount = total_amount.quantize(decimal.Decimal("0.0000001"), rounding=decimal.ROUND_HALF_UP)
        return PriceInfo(
            unit_price=unit_price,
            unit=price_config.unit,
            total_amount=total_amount,
            currency=price_config.currency or "USD",
        )

    def _trigger_before_invoke_callbacks(
        self,
        model: str,
        credentials: dict,
        prompt_messages: Sequence[PromptMessage],
        model_parameters: dict,
        tools: Optional[list[PromptMessageFunction]] = None,
        stop: Optional[Sequence[str]] = None,
        stream: bool = True,
        include_reasoning: bool = False,
        callbacks: Optional[list[Callback]] = None,
        user: Optional[str] = None,
        agent_id: Optional[int] = None,
        agent_session_id: Optional[int] = None,
    ) -> None:
        """
        Trigger before invoke callbacks

        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools for tool calling
        :param stop: stop words
        :param stream: is stream response
        :param callbacks: callbacks
        """
        if callbacks:
            for callback in callbacks:
                try:
                    callback.on_before_invoke(
                        llm_instance=self,
                        model=model,
                        credentials=credentials,
                        prompt_messages=list(prompt_messages),
                        model_parameters=model_parameters,
                        tools=tools,
                        stop=stop,
                        stream=stream,
                        include_reasoning=include_reasoning,
                        user=user,
                        agent_id=agent_id,
                        agent_session_id=agent_session_id,
                    )
                except Exception as e:
                    if callback.raise_error:
                        raise e
                    else:
                        logger.warning("%Callback {callback.__class__.__name__} on_before_invoke failed with error {e}")

    def _trigger_new_chunk_callbacks(
        self,
        chunk: ChatCompletionResponseChunk,
        model: str,
        credentials: dict,
        prompt_messages: Sequence[PromptMessage],
        model_parameters: dict,
        tools: Optional[list[PromptMessageFunction]] = None,
        stop: Optional[Sequence[str]] = None,
        stream: bool = True,
        callbacks: Optional[list[Callback]] = None,
        user: Optional[str] = None,
        include_reasoning: bool = False,
        agent_id: Optional[int] = None,
        agent_session_id: Optional[int] = None,
    ) -> None:
        """
        Trigger new chunk callbacks

        :param chunk: chunk
        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools for tool calling
        :param stop: stop words
        :param stream: is stream response
        """
        if callbacks:
            for callback in callbacks:
                try:
                    callback.on_new_chunk(
                        llm_instance=self,
                        chunk=chunk,
                        model=model,
                        credentials=credentials,
                        prompt_messages=prompt_messages,
                        model_parameters=model_parameters,
                        tools=tools,
                        stop=stop,
                        stream=stream,
                        user=user,
                        include_reasoning=include_reasoning,
                        agent_id=agent_id,
                        agent_session_id=agent_session_id,
                    )
                except Exception as e:
                    if callback.raise_error:
                        raise e
                    else:
                        logger.warning("%Callback {callback.__class__.__name__} on_new_chunk failed with error {e}")

    def _trigger_after_invoke_callbacks(
        self,
        model: str,
        result: ChatCompletionResponse,
        credentials: dict,
        prompt_messages: Sequence[PromptMessage],
        model_parameters: dict,
        tools: Optional[list[PromptMessageFunction]] = None,
        stop: Optional[Sequence[str]] = None,
        stream: bool = True,
        callbacks: Optional[list[Callback]] = None,
        user: Optional[str] = None,
        include_reasoning: bool = False,
        agent_id: Optional[int] = None,
        agent_session_id: Optional[int] = None,
    ) -> None:
        """
        Trigger after invoke callbacks

        :param model: model name
        :param result: result
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools for tool calling
        :param stop: stop words
        :param stream: is stream response
        :param callbacks: callbacks
        """
        if callbacks:
            for callback in callbacks:
                try:
                    callback.on_after_invoke(
                        llm_instance=self,
                        result=result,
                        model=model,
                        credentials=credentials,
                        prompt_messages=prompt_messages,
                        model_parameters=model_parameters,
                        tools=tools,
                        stop=stop,
                        stream=stream,
                        user=user,
                        include_reasoning=include_reasoning,
                        agent_id=agent_id,
                        agent_session_id=agent_session_id,
                    )
                except Exception as e:
                    traceback.print_exc()
                    if callback.raise_error:
                        raise e
                    else:
                        logger.warning("%Callback {callback.__class__.__name__} on_after_invoke failed with error {e}")

    def _trigger_invoke_error_callbacks(
        self,
        model: str,
        ex: Exception,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: dict,
        tools: Optional[list[PromptMessageFunction]] = None,
        stop: Optional[Sequence[str]] = None,
        stream: bool = True,
        callbacks: Optional[list[Callback]] = None,
        user: Optional[str] = None,
        include_reasoning: bool = False,
        agent_id: Optional[int] = None,
        agent_session_id: Optional[int] = None,
    ) -> None:
        """
        Trigger invoke error callbacks

        :param model: model name
        :param ex: exception
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools for tool calling
        :param stop: stop words
        :param stream: is stream response
        :param callbacks: callbacks
        """
        if callbacks:
            for callback in callbacks:
                try:
                    callback.on_invoke_error(
                        llm_instance=self,
                        ex=ex,
                        model=model,
                        credentials=credentials,
                        prompt_messages=prompt_messages,
                        model_parameters=model_parameters,
                        tools=tools,
                        stop=stop,
                        stream=stream,
                        user=user,
                        include_reasoning=include_reasoning,
                        agent_id=agent_id,
                        agent_session_id=agent_session_id,
                    )
                except Exception as e:
                    if callback.raise_error:
                        raise e
                    else:
                        logger.warning("%Callback {callback.__class__.__name__} on_invoke_error failed with error {e}")

    # =========================================================================
    # 统一后处理方法
    # =========================================================================

    def _aggregate_content(self, result: LLMResponse) -> tuple[str, list[AssistantPromptMessage.ToolCall]]:
        """
        Deprecated: replaced by ProtocolNormalizer + ResponseCollector.

        聚合任意响应类型的 content 为 (message_content, tool_calls)

        Args:
            result: LLM 响应对象

        Returns:
            (message_content: str, tool_calls: list[ToolCall])
        """
        warnings.warn(
            "LlMModel._aggregate_content is deprecated; use ProtocolNormalizer/ResponseCollector instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        text, tool_calls, _usage, _fp = ProtocolNormalizer.extract_full(result)
        return text, tool_calls

    def _aggregate_stream_chunk(
        self,
        chunk: LLMResponse,
    ) -> tuple[str, list[AssistantPromptMessage.ToolCall], Optional[LLMUsage], Optional[str]]:
        """
        Deprecated: replaced by ProtocolNormalizer + ResponseCollector.

        聚合流式 chunk 的 content

        Args:
            chunk: 流式 chunk 对象

        Returns:
            (message_content, tool_calls, usage, system_fingerprint)
        """
        warnings.warn(
            "LlMModel._aggregate_stream_chunk is deprecated; use ProtocolNormalizer/ResponseCollector instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        chunk_content, tool_calls, normalized, system_fingerprint = ProtocolNormalizer.extract_chunk(chunk)
        usage = LLMUsage(
            prompt_tokens=normalized.prompt_tokens,
            completion_tokens=normalized.completion_tokens,
            thinking_tokens=normalized.thinking_tokens,
            cached_tokens=normalized.cached_tokens,
            cache_write_tokens=normalized.cache_write_tokens,
        )
        return chunk_content, tool_calls, usage, system_fingerprint

    def _convert_to_chat_response(
        self,
        result: LLMResponse,
        model: str,
        message_id: str,
        prompt_messages,
        message_content: str,
        tool_calls: list[AssistantPromptMessage.ToolCall],
    ) -> ChatCompletionResponse:
        """
        Deprecated: replaced by ProtocolNormalizer + ResponseCollector.

        将 LLM 响应转换为 ChatCompletionResponse

        Args:
            result: 原始 LLM 响应
            model: 模型名称
            message_id: 消息 ID
            prompt_messages: 提示消息
            message_content: 聚合后的消息内容
            tool_calls: 聚合后的 tool calls

        Returns:
            ChatCompletionResponse 对象
        """
        warnings.warn(
            "LlMModel._convert_to_chat_response is deprecated; use ProtocolNormalizer/ResponseCollector instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        _text, _normalized_tool_calls, normalized, fingerprint = ProtocolNormalizer.extract_full(result)
        chat = ChatCompletionResponse(
            model=getattr(result, "model", None) or model,
            id=getattr(result, "id", None) or message_id,
            message=AssistantPromptMessage(content=message_content, tool_calls=tool_calls),
            usage=self.calc_response_usage(
                model,
                normalized.prompt_tokens,
                normalized.completion_tokens,
                normalized.thinking_tokens,
                normalized.cached_tokens,
                normalized.cache_write_tokens,
            ),
            system_fingerprint=fingerprint,
        )
        if hasattr(result, "stop_reason") and getattr(result, "stop_reason", None) is not None:
            chat.done = True
        chat.prompt_messages = prompt_messages
        return chat

    def _post_process(
        self,
        result: LLMResponse,
        model: str,
        message_id: str,
        credentials: dict,
        prompt_messages,
        model_parameters: dict,
        tools: Optional[list[PromptMessageFunction]] = None,
        stop: Optional[Sequence[str]] = None,
        stream: bool = False,
        callbacks: Optional[list[Callback]] = None,
        user: Optional[str] = None,
        include_reasoning: bool = False,
        agent_id: Optional[int] = None,
        agent_session_id: Optional[int] = None,
    ) -> ChatCompletionResponse:
        """
        统一的后处理逻辑：聚合 → 转换 → 回调 → 返回

        Args:
            result: LLM 响应对象
            model: 模型名称
            message_id: 消息 ID
            credentials: 凭证
            prompt_messages: 提示消息
            model_parameters: 模型参数
            tools: 工具列表
            stop: 停止词
            stream: 是否流式
            callbacks: 回调列表

        Returns:
            ChatCompletionResponse 对象
        """
        collector = ResponseCollector(model=model, message_id=message_id)
        collector.accept_full(result)
        chat = collector.build_response(self)
        chat.prompt_messages = prompt_messages

        # 3. 触发 after 回调
        self._trigger_after_invoke_callbacks(
            model=model,
            result=chat,
            credentials=credentials,
            prompt_messages=prompt_messages,
            model_parameters=model_parameters,
            tools=tools,
            stop=stop,
            stream=stream,
            callbacks=callbacks,
            user=user,
            include_reasoning=include_reasoning,
            agent_id=agent_id,
            agent_session_id=agent_session_id,
        )

        # 4. 返回
        return chat
