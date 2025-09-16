import decimal
import logging
import time
from typing import Optional, Union, Generator, Sequence, cast

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
from ..entities.llm_entities import ChatCompletionRequest, CompletionRequest
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
        prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
        callbacks: Optional[list[Callback]] = None,
    ) -> Union[ChatCompletionResponse, Generator[ChatCompletionResponseChunk, None, None]]:
        """
        Invoke large language model

        :param prompt_messages: prompt messages
        :param callbacks: callbacks
        :return: full response or stream response chunk generator result
        """

        self.started_at = time.perf_counter()

        callbacks = callbacks or []

        from ..transformation import get_llm_transformation

        transformation = get_llm_transformation(self.credentials.get("sdk_type", "openai_like"))

        prompt_messages = transformation.setup_model_parameters(self.model_params, prompt_messages)
        credentials = transformation.setup_environment(self.credentials, self.model_params)

        stream: bool = prompt_messages.stream
        model: str = prompt_messages.model
        tools: Optional[list[PromptMessageTool]] = []
        include_reasoning: bool = False
        message_id: Optional[str] = self.get_message_id()
        if isinstance(prompt_messages, ChatCompletionRequest):
            include_reasoning = prompt_messages.include_reasoning
            tools = prompt_messages.tools
            if tools:
                stream = False  # disable stream for tool calling
        stop: Optional[Sequence[str]] = prompt_messages.stop

        parameters = {
            "message_id": message_id,
            "temperature": prompt_messages.temperature,
            "top_p": prompt_messages.top_p,
            "max_tokens": prompt_messages.max_tokens,
            "max_completion_tokens": prompt_messages.max_completion_tokens,
            "top_k": prompt_messages.top_k,
            "presence_penalty": prompt_messages.presence_penalty,
            "frequency_penalty": prompt_messages.frequency_penalty,
            "response_format": prompt_messages.response_format,
        }

        if config.DEBUG:
            callbacks.append(LoggingCallback())

        # trigger before invoke callbacks
        self._trigger_before_invoke_callbacks(
            model=model,
            credentials=credentials,
            prompt_messages=prompt_messages,
            model_parameters=parameters,
            tools=tools,
            stop=stop,
            stream=stream,
            include_reasoning=include_reasoning,
            callbacks=callbacks,
        )

        result: Union[ChatCompletionResponse, Generator[ChatCompletionResponseChunk, None, None]]

        try:
            # invoke model
            result = transformation.transform_message(
                model_params=self.model_params,
                credentials=credentials,
                prompt_messages=prompt_messages,
                stream=stream,
            )

            if not stream:
                message_content = ""
                tools_calls: list[AssistantPromptMessage.ToolCall] = []
                for chunk in result:
                    for chunkContent in chunk.choices:
                        if chunkContent.message and chunkContent.message.content:
                            if isinstance(chunkContent.message.content, str):
                                message_content += chunkContent.message.content
                        if chunkContent.text:
                            if isinstance(chunkContent.text, str):
                                message_content += chunkContent.text
                        if chunkContent.message and chunkContent.message.tool_calls:
                            for tool_call in chunkContent.message.tool_calls:
                                tools_calls.append(tool_call)
                    chunk.message = AssistantPromptMessage(content=message_content, tool_calls=tools_calls)
                    chunk.id = message_id
                    result = cast(ChatCompletionResponse, chunk)
        except Exception as e:
            self._trigger_invoke_error_callbacks(
                model=model,
                ex=e,
                credentials=credentials,
                prompt_messages=prompt_messages,
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
                result=result,
                credentials=credentials,
                prompt_messages=prompt_messages,
                model_parameters=parameters,
                tools=tools,
                stop=stop,
                stream=stream,
                callbacks=callbacks,
            )
        elif isinstance(result, ChatCompletionResponse):
            self._trigger_after_invoke_callbacks(
                model=model,
                result=result,
                credentials=credentials,
                prompt_messages=prompt_messages,
                model_parameters=parameters,
                tools=tools,
                stop=stop,
                stream=stream,
                callbacks=callbacks,
            )
            result.usage = self.calc_response_usage(model, result.usage.prompt_tokens, result.usage.completion_tokens)
            result.prompt_messages = prompt_messages
            return result
        raise NotImplementedError("unsupported invoke result type", type(result))

    def _invoke_result_generator(
        self,
        model: str,
        result: Generator[ChatCompletionResponseChunk, None, None],
        credentials: dict,
        prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
        model_parameters: dict,
        tools: Optional[list[PromptMessageFunction]] = None,
        stop: Optional[Sequence[str]] = None,
        stream: bool = True,
        user: Optional[str] = None,
        callbacks: Optional[list[Callback]] = None,
    ) -> Generator[ChatCompletionResponseChunk, None, None]:
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

        def _update_message_content(content: str | None):
            if not content:
                return

            if isinstance(content, Generator):
                for c in content:
                    if isinstance(c, str):
                        message_content.append(TextPromptMessageContent(data=c))
                    elif isinstance(c, list):
                        message_content.extend(c)
                return

        try:
            for chunk in result:
                chunk.prompt_messages = self.get_messages(prompt_messages)
                yield chunk

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
                    prompt_messages=self.get_messages(prompt_messages),
                    model_parameters=model_parameters,
                    tools=tools,
                    stop=stop,
                    stream=stream,
                    callbacks=callbacks,
                )

                if chunk.delta and chunk.delta.usage:
                    usage = chunk.delta.usage
                if chunk.usage:
                    usage = chunk.usage
                if chunk.system_fingerprint:
                    system_fingerprint = chunk.system_fingerprint
        except Exception as e:
            logger.error(f"Error in stream processing: {e}", exc_info=True)
            raise e
        finally:
            try:
                assistant_message = AssistantPromptMessage(content=message_content)
                messages = self.get_messages(prompt_messages)
                self._trigger_after_invoke_callbacks(
                    model=model,
                    result=ChatCompletionResponse(
                        model=real_model,
                        prompt_messages=messages,
                        message=assistant_message,
                        usage=self.calc_response_usage(real_model, usage.prompt_tokens, usage.completion_tokens)
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
        prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
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
        :param user: unique user id
        :param callbacks: callbacks
        """
        if callbacks:
            for callback in callbacks:
                try:
                    messages = self.get_messages(prompt_messages)
                    callback.on_before_invoke(
                        llm_instance=self,
                        model=model,
                        credentials=credentials,
                        prompt_messages=messages,
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
        :param user: unique user id
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
        :param user: unique user id
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
        :param user: unique user id
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
