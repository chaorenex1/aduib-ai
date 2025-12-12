import decimal
import json
import logging
import time
import traceback
from inspect import isclass
from typing import Optional, Union, Generator, Sequence, cast, get_args

from pydantic import ConfigDict

from configs import config
from .base import AiModel
from ..callbacks.base_callback import Callback
from ..callbacks.console_callback import LoggingCallback
from ..entities import (
    PromptMessage,
    PromptMessageTool,
    ChatCompletionResponse,
    ChatCompletionResponseChunk,
    LLMUsage,
    AssistantPromptMessage,
    TextPromptMessageContent,
    PromptMessageFunction,
)
from ..entities.llm_entities import ChatCompletionRequest, CompletionRequest, CompletionResponse, \
    ClaudeChatCompletionResponse
from ..entities.message_entities import ClaudeThinkingPromptMessageContent
from ..entities.model_entities import ModelType, PriceType, PriceInfo, PriceConfig

logger = logging.getLogger(__name__)


class LlMModel(AiModel):
    """
    Base class for all LLM models.
    """

    model_type: ModelType = ModelType.LLM

    model_config = ConfigDict(protected_namespaces=())

    def invoke(
            self,
            req: Union[ChatCompletionRequest, CompletionRequest],
            callbacks: Optional[list[Callback]] = None,
    ) -> Union[CompletionResponse, Generator[CompletionResponse, None, None]]:
        """
        Invoke large language model

        :param req: prompt messages
        :param callbacks: callbacks
        :return: full response or stream response chunk generator result
        """

        self.started_at = time.perf_counter()

        callbacks = callbacks or []

        from ..transformation import get_llm_transformation

        transformation = get_llm_transformation(self.credentials.get("sdk_type", "openai_like"))

        credentials = transformation.setup_environment(self.credentials, self.model_params)
        req = transformation.setup_model_parameters(credentials,self.model_params, req)

        stream: bool = req.stream
        model: str = req.model
        tools: Optional[list[PromptMessageTool]] = []
        include_reasoning: bool = False
        message_id: Optional[str] = self.get_message_id()
        if isinstance(req, ChatCompletionRequest):
            include_reasoning = (
                    req.include_reasoning
                    or req.enable_thinking
                    or req.thinking is not None
            )
            tools = req.tools
            # if tools:
            #     stream = False  # disable stream for tool calling
        stop: Optional[Sequence[str]] = req.stop

        parameters = {
            "message_id": message_id,
            "temperature": req.temperature,
            "top_p": req.top_p,
            "max_tokens": req.max_tokens,
            "max_completion_tokens": req.max_completion_tokens,
            "top_k": req.top_k,
            "presence_penalty": req.presence_penalty,
            "frequency_penalty": req.frequency_penalty,
            "response_format": req.response_format,
        }

        # if config.DEBUG:
        #     callbacks.append(LoggingCallback())

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
        )

        result: Union[CompletionResponse, Generator[CompletionResponse, None, None]]

        try:
            # invoke model
            result = transformation.transform_message(
                model_params=self.model_params,
                prompt_messages=req,
                credentials=credentials,
                stream=stream,
            )

            if not stream and isinstance(result, ChatCompletionResponse):
                message_content = ""
                tools_calls: list[AssistantPromptMessage.ToolCall] = []
                for chunkContent in result.choices:
                    if chunkContent.message and chunkContent.message.content:
                        if isinstance(chunkContent.message.content, str):
                            message_content += chunkContent.message.content
                        elif isinstance(chunkContent.message.content, list):
                            message_content += "".join([content.data for content in chunkContent.message.content])
                    if chunkContent.text:
                        if isinstance(chunkContent.text, str):
                            message_content += chunkContent.text
                    if chunkContent.message and chunkContent.message.tool_calls:
                        for tool_call in chunkContent.message.tool_calls:
                            tools_calls.append(tool_call)
                    result.message = AssistantPromptMessage(content=message_content, tool_calls=tools_calls)
                    result.id = message_id
                    result = cast(ChatCompletionResponse, result)
            elif not stream and isinstance(result, ClaudeChatCompletionResponse):
                message_content = ""
                tools_calls: list[AssistantPromptMessage.ToolCall] = []
                if result.content or result.delta:
                    for chunkContent in result.content or result.delta:
                        if isinstance(chunkContent, str):
                            message_content += chunkContent
                        elif isinstance(chunkContent, dict) and chunkContent.get('type') == 'text':
                            message_content += chunkContent.get('text', '')
                        elif isinstance(chunkContent, dict) and chunkContent.get('type') == 'thinking':
                            message_content += chunkContent.get('thinking', '')
                        elif isinstance(chunkContent, dict) and chunkContent.get('type') == 'input_json':
                            message_content += chunkContent.get('partial_json', '')
                        elif isinstance(chunkContent, dict) and chunkContent.get('type') == 'tool_use':
                            message_content += json.dumps(chunkContent.get('input', ''))
                        elif isinstance(chunkContent, dict) and chunkContent.get('type') == 'tool_result':
                            message_content += json.dumps(chunkContent.get('content', ''))
                        elif isinstance(chunkContent, dict) and chunkContent.get('type') == 'mcp_tool_use':
                            message_content += json.dumps(chunkContent.get('input', ''))
                        elif isinstance(chunkContent, dict) and chunkContent.get('type') == 'mcp_tool_result':
                            message_content += json.dumps(chunkContent.get('content', ''))
                result.message = AssistantPromptMessage(content=message_content, tool_calls=tools_calls)
                result.id = message_id
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
            )
            raise e

        if stream and isinstance(result, Generator):
            return self._invoke_result_generator(
                model=model,
                result=cast(Generator[ChatCompletionResponseChunk, None, None], result),
                credentials=credentials,
                req=req,
                model_parameters=parameters,
                tools=tools,
                stop=stop,
                stream=stream,
                callbacks=callbacks,
            )
        elif isinstance(result, ChatCompletionResponse):
            result.usage = self.calc_response_usage(model, result.usage.prompt_tokens, result.usage.completion_tokens)
            result.prompt_messages = self.get_messages(req)
            self._trigger_after_invoke_callbacks(
                model=model,
                result=result,
                credentials=credentials,
                prompt_messages=self.get_messages(req),
                model_parameters=parameters,
                tools=tools,
                stop=stop,
                stream=stream,
                callbacks=callbacks,
            )
            return result
        elif isinstance(result, ClaudeChatCompletionResponse):
            usage = LLMUsage.empty_usage()
            chat=ChatCompletionResponse(model=result.model,usage=usage,done=result.done)
            chat.usage = self.calc_response_usage(model, result.usage.get("input_tokens",0), result.usage.get("output_tokens",0))
            result.usage = usage
            result.prompt_messages = self.get_messages(req)
            chat.message=result.message
            chat.id = result.id
            self._trigger_after_invoke_callbacks(
                model=model,
                result=chat,
                credentials=credentials,
                prompt_messages=self.get_messages(req),
                model_parameters=parameters,
                tools=tools,
                stop=stop,
                stream=stream,
                callbacks=callbacks,
            )
            return result
        raise NotImplementedError("unsupported invoke result type", type(result))

    def _invoke_result_generator(
            self,
            model: str,
            result: Generator[CompletionResponse, None, None],
            credentials: dict,
            req: Union[ChatCompletionRequest, CompletionRequest],
            model_parameters: dict,
            tools: Optional[list[PromptMessageFunction]] = None,
            stop: Optional[Sequence[str]] = None,
            stream: bool = True,
            callbacks: Optional[list[Callback]] = None,
    ) -> Generator[CompletionResponse, None, None]:
        """
        Invoke result generator

        :param result: result generator
        :return: result generator
        """
        callbacks = callbacks or []
        message_content = []
        usage = None
        system_fingerprint = None
        real_model = model
        try:
            for chunk in result:
                if isinstance(chunk, ChatCompletionResponseChunk):
                    yield chunk
                    chunk.prompt_messages = self.get_messages(req)

                    if chunk.choices:
                        for chunkContent in chunk.choices:
                            if chunkContent.delta and chunkContent.delta.content:
                                message_content.append(TextPromptMessageContent(data=chunkContent.delta.content))
                            if chunkContent.message and chunkContent.message.content:
                                message_content.append(TextPromptMessageContent(data=chunkContent.message.content))
                            if chunkContent.text:
                                if isinstance(chunkContent.text, str):
                                    message_content.append(TextPromptMessageContent(data=chunkContent.text))

                    self._trigger_new_chunk_callbacks(
                        chunk=chunk,
                        model=model,
                        credentials=credentials,
                        prompt_messages=self.get_messages(req),
                        model_parameters=model_parameters,
                        tools=tools,
                        stop=stop,
                        stream=stream,
                        callbacks=callbacks,
                    )

                    if chunk.delta and chunk.delta.usage:
                        usage = self.calc_response_usage(real_model, chunk.delta.usage.prompt_tokens, chunk.delta.usage.completion_tokens)
                    if chunk.usage:
                        usage = self.calc_response_usage(real_model, chunk.usage.prompt_tokens, chunk.usage.completion_tokens)
                    if chunk.system_fingerprint:
                        system_fingerprint = chunk.system_fingerprint
                elif isinstance(chunk, ClaudeChatCompletionResponse):
                    yield chunk
                    # final chunk
                    chunk.prompt_messages = self.get_messages(req)
                    if chunk.usage:
                        usage = self.calc_response_usage(real_model, chunk.usage.get("input_tokens",0), chunk.usage.get("output_tokens",0))

                    if chunk.content or chunk.delta:
                        chunkContent = chunk.content or chunk.delta
                        if isinstance(chunkContent, str):
                            message_content.append(TextPromptMessageContent(data=chunkContent))
                        elif isinstance(chunkContent, dict) and chunkContent.get('type')=='text_delta':
                            message_content.append(TextPromptMessageContent(data=chunkContent.get('text','')))
                        elif isinstance(chunkContent, dict) and chunkContent.get('type')=='thinking_delta':
                            message_content.append(TextPromptMessageContent(data=chunkContent.get('thinking','')))
                        elif isinstance(chunkContent, dict) and chunkContent.get('type') == 'input_json_delta':
                            message_content.append(TextPromptMessageContent(data=chunkContent.get('partial_json', '')))
                        elif isinstance(chunkContent, dict) and chunkContent.get('type') == 'tool_use':
                            message_content.append(TextPromptMessageContent(data=json.dumps(chunkContent.get('input', ''))))
                        elif isinstance(chunkContent, dict) and chunkContent.get('type') == 'tool_result':
                            message_content.append(TextPromptMessageContent(data=json.dumps(chunkContent.get('content', ''))))
                        elif isinstance(chunkContent, dict) and chunkContent.get('type') == 'mcp_tool_use':
                            message_content.append(TextPromptMessageContent(data=json.dumps(chunkContent.get('input', ''))))
                        elif isinstance(chunkContent, dict) and chunkContent.get('type') == 'mcp_tool_result':
                            message_content.append(TextPromptMessageContent(data=json.dumps(chunkContent.get('content', ''))))
                        else:
                            message_content.append(TextPromptMessageContent(data=''))
                    system_fingerprint = "claude"  # Claude does not return system fingerprint, use fixed value


        except Exception as e:
            logger.error(f"Error in stream processing: {e}", exc_info=True)
            raise e
        finally:
            try:
                assistant_message = AssistantPromptMessage(content=message_content)
                messages = self.get_messages(req)
                self._trigger_after_invoke_callbacks(
                    model=model,
                    result=ChatCompletionResponse(
                        model=real_model,
                        prompt_messages=messages,
                        message=assistant_message,
                        usage=usage
                        if usage
                        else LLMUsage.empty_usage(),
                        system_fingerprint=system_fingerprint,
                    ),
                    credentials=credentials,
                    prompt_messages=messages,
                    model_parameters=model_parameters,
                    tools=tools,
                    stop=stop,
                    stream=stream,
                    callbacks=callbacks,
                )
            except Exception as e:
                logger.error(f"Error in after invoke callback: {e}", exc_info=True)

    def calc_response_usage(self, model: str, prompt_tokens: int, completion_tokens: int) -> LLMUsage:
        """
        Calculate response usage based on prompt and completion tokens
        :param model: model name
        :param prompt_tokens: number of prompt tokens
        :param completion_tokens: number of completion tokens
        :return: LLMUsage object with calculated usage
        """
        prompt_price_info = self.get_price_info(model, PriceType.INPUT, prompt_tokens)
        completion_price_info = self.get_price_info(model, PriceType.OUTPUT, completion_tokens)
        total_tokens = prompt_tokens + completion_tokens
        total_price = prompt_price_info.total_amount + completion_price_info.total_amount
        return LLMUsage(
            prompt_tokens=prompt_tokens,
            prompt_unit_price=prompt_price_info.unit_price,
            prompt_price_unit=prompt_price_info.unit,
            prompt_price=prompt_price_info.total_amount,
            completion_tokens=completion_tokens,
            completion_unit_price=completion_price_info.unit_price,
            completion_price_unit=completion_price_info.unit,
            completion_price=completion_price_info.total_amount,
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
                    )
                except Exception as e:
                    if callback.raise_error:
                        raise e
                    else:
                        logger.warning(f"Callback {callback.__class__.__name__} on_before_invoke failed with error {e}")

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
                    )
                except Exception as e:
                    if callback.raise_error:
                        raise e
                    else:
                        logger.warning(f"Callback {callback.__class__.__name__} on_new_chunk failed with error {e}")

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
                    )
                except Exception as e:
                    traceback.print_exc()
                    if callback.raise_error:
                        raise e
                    else:
                        logger.warning(f"Callback {callback.__class__.__name__} on_after_invoke failed with error {e}")

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
                    )
                except Exception as e:
                    if callback.raise_error:
                        raise e
                    else:
                        logger.warning(f"Callback {callback.__class__.__name__} on_invoke_error failed with error {e}")
