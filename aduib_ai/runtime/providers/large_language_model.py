import logging
import time
from typing import Optional, Union, Generator, Sequence

from pydantic import ConfigDict
from fastapi import Request

from controllers.params import ChatCompletionRequest, CompletionRequest
from ..callbacks.base_callback import Callback
from ..callbacks.console_callback import LoggingCallback
from ..client.llm_client import ModelClient
from ..entities import PromptMessage, PromptMessageTool, ChatCompletionResponse, ChatCompletionResponseChunk, LLMUsage, AssistantPromptMessage, \
    TextPromptMessageContent
from ..entities.message_entities import PromptMessageContentUnionTypes
from ..entities.model_entities import ModelType, PriceType
from .base import AiModel
from configs import config

logger = logging.getLogger(__name__)


class LlMModel(AiModel):
    """
    Base class for all LLM models.
    """
    model_type:ModelType = ModelType.LLM

    model_config = ConfigDict(protected_namespaces=())

    def invoke(
        self,
        prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
        credentials: dict,
        raw_request: Request,
        callbacks: Optional[list[Callback]] = None,
    ) -> Union[ChatCompletionResponse, Generator[ChatCompletionResponseChunk, None, None]]:
        """
        Invoke large language model

        :param prompt_messages: prompt messages
        :param raw_request: raw request
        :param callbacks: callbacks
        :return: full response or stream response chunk generator result
        """

        # self.started_at = time.perf_counter()

        callbacks = callbacks or []
        stream: bool = prompt_messages.stream
        include_reasoning: bool = prompt_messages.include_reasoning
        model: str = prompt_messages.model
        tools: Optional[list[PromptMessageTool]] = prompt_messages.tools
        stop: Optional[Sequence[str]] = prompt_messages.stop
        parameters = {
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
            model_client = ModelClient()
            result= model_client.completion_request(
                credentials=credentials,
                prompt_messages=prompt_messages,
                raw_request=raw_request,
                stream=stream,
            )

            if not stream:
                content = ""
                content_list = []
                usage = LLMUsage.empty_usage()
                system_fingerprint = None
                tools_calls: list[AssistantPromptMessage.ToolCall] = []

                for chunk in result:
                    if isinstance(chunk.delta.message.content, str):
                        content += chunk.delta.message.content
                    elif isinstance(chunk.delta.message.content, list):
                        content_list.extend(chunk.delta.message.content)
                    if chunk.delta.message.tool_calls:
                        # _increase_tool_call(chunk.delta.message.tool_calls, tools_calls)
                     pass

                    usage = chunk.delta.usage or LLMUsage.empty_usage()
                    system_fingerprint = chunk.system_fingerprint
                    break

                result = ChatCompletionResponse(
                    model=model,
                    prompt_messages=prompt_messages,
                    message=AssistantPromptMessage(
                        content=content or content_list,
                        tool_calls=tools_calls,
                    ),
                    usage=usage,
                    system_fingerprint=system_fingerprint,
                )
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
        tools: Optional[list[PromptMessageTool]] = None,
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
        message_content= []
        usage = None
        system_fingerprint = None
        real_model = model

        def _update_message_content(content: str | None):
            if not content:
                return
            if isinstance(content, list):
                message_content.extend(content)
                return
            if isinstance(content, str):
                message_content.append(TextPromptMessageContent(data=content))
                return

        try:
            for chunk in result:
                chunk.prompt_messages = prompt_messages.messages
                yield chunk

                if chunk.choices:
                    _update_message_content(chunkContent.delta.content for chunkContent in chunk.choices)

                self._trigger_new_chunk_callbacks(
                    chunk=chunk,
                    model=model,
                    credentials=credentials,
                    prompt_messages=prompt_messages.messages,
                    model_parameters=model_parameters,
                    tools=tools,
                    stop=stop,
                    stream=stream,
                    user=user,
                    callbacks=callbacks,
                )

                if chunk.delta and chunk.delta.usage:
                    usage = chunk.delta.usage
                if chunk.usage:
                    usage  = chunk.usage
                if chunk.system_fingerprint:
                    system_fingerprint = chunk.system_fingerprint
        except Exception as e:
            raise e

        assistant_message = AssistantPromptMessage(content=message_content)
        self._trigger_after_invoke_callbacks(
            model=model,
            result=ChatCompletionResponse(
                model=real_model,
                prompt_messages=prompt_messages.messages,
                message=assistant_message,
                usage=usage or LLMUsage.empty_usage(),
                system_fingerprint=system_fingerprint,
            ),
            credentials=credentials,
            prompt_messages=prompt_messages.messages,
            model_parameters=model_parameters,
            tools=tools,
            stop=stop,
            stream=stream,
            user=user,
            callbacks=callbacks,
        )

    def get_num_tokens(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        tools: Optional[list[PromptMessageTool]] = None,
    ) -> int:
        """
        Get number of tokens for given prompt messages

        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param tools: tools for tool calling
        :return:
        """
        return 0

    def _trigger_before_invoke_callbacks(
        self,
        model: str,
        credentials: dict,
        prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
        model_parameters: dict,
        tools: Optional[list[PromptMessageTool]] = None,
        stop: Optional[Sequence[str]] = None,
        stream: bool = True,
        include_reasoning:bool=False,
        user: Optional[str] = None,
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
                    callback.on_before_invoke(
                        llm_instance=self,
                        model=model,
                        credentials=credentials,
                        prompt_messages=prompt_messages.messages if prompt_messages.messages else prompt_messages.prompt,
                        model_parameters=model_parameters,
                        tools=tools,
                        stop=stop,
                        stream=stream,
                        include_reasoning=include_reasoning,
                        user=user,
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
        tools: Optional[list[PromptMessageTool]] = None,
        stop: Optional[Sequence[str]] = None,
        stream: bool = True,
        user: Optional[str] = None,
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
                        user=user,
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
        tools: Optional[list[PromptMessageTool]] = None,
        stop: Optional[Sequence[str]] = None,
        stream: bool = True,
        user: Optional[str] = None,
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
                        user=user,
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
        tools: Optional[list[PromptMessageTool]] = None,
        stop: Optional[Sequence[str]] = None,
        stream: bool = True,
        user: Optional[str] = None,
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
                        user=user,
                    )
                except Exception as e:
                    if callback.raise_error:
                        raise e
                    else:
                        logger.warning(f"Callback {callback.__class__.__name__} on_invoke_error failed with error {e}")