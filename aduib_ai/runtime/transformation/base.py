import logging
from abc import ABC, abstractmethod
from typing import Union, Generator, Any

from runtime.entities import ToolPromptMessage
from runtime.entities.llm_entities import ChatCompletionRequest, CompletionRequest, ChatCompletionResponse, \
    ChatCompletionResponseChunk
from runtime.entities.text_embedding_entities import EmbeddingRequest, TextEmbeddingResult
from runtime.mcp.types import Request
from runtime.tool.entities import ToolInvokeResult

logger = logging.getLogger(__name__)

class LLMTransformation:
    """Base class for all transformations."""

    @classmethod
    def setup_model_parameters(cls, model_params: dict[str, Any],
                               prompt_messages: Union[ChatCompletionRequest, CompletionRequest]):
        """Validate model parameters."""
        if not prompt_messages.temperature:
            prompt_messages.temperature = model_params.get("temperature", 0.7)
        if not prompt_messages.top_p:
            prompt_messages.top_p = model_params.get("top_p", 1.0)
        if not prompt_messages.top_k:
            prompt_messages.top_k = model_params.get("top_k", 20)
        if not prompt_messages.presence_penalty:
            prompt_messages.presence_penalty = model_params.get("presence_penalty", 0.0)
        if not prompt_messages.frequency_penalty:
            prompt_messages.frequency_penalty = model_params.get("frequency_penalty", 0.0)
        # if not prompt_messages.miniP:
        #     prompt_messages.miniP = model_params.get("miniP", 0.0)

        return prompt_messages

    @classmethod
    def transform_message(
            cls,
            model_params: dict,
            prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
            credentials: dict,
            raw_request: Request,
            stream: bool = None,
    ) -> Union[ChatCompletionResponse, Generator[ChatCompletionResponseChunk, None, None]]:
        """
        Transform the input message using the provided credentials and raw request.
        :param model_params: The model parameters for transformation.
        :param prompt_messages: The input messages to be transformed.
        :param credentials: The credentials required for transformation.
        :param raw_request: The raw request object, typically from FastAPI.
        :param stream: Whether to return a streaming response.
        :return: A response object containing the transformed message, or a streaming response if requested.
        """
        llm_result = cls._transform_message(model_params, prompt_messages, credentials, raw_request, stream)
        if prompt_messages.tools:
            return cls._call_tools(prompt_messages, credentials, raw_request, llm_result)
        return llm_result

    @classmethod
    def _call_tools(cls,
                    model_params: dict,
                    req: Union[ChatCompletionRequest, CompletionRequest],
                    credentials: dict,
                    raw_request: Request,
                    llm_result: Union[ChatCompletionResponse, Generator[ChatCompletionResponseChunk, None, None]],
                    stream: bool = None
                    ) -> Union[ChatCompletionResponse, Generator[ChatCompletionResponseChunk, None, None]]:

        if llm_result.message.tool_calls and len(llm_result.message.tool_calls) > 0:

            from runtime.tool.tool_manager import ToolManager

            tool_manager = ToolManager()
            tool_invoke_result: ToolInvokeResult = tool_manager.invoke_tools(llm_result.message.tool_calls,
                                                                             llm_result.id)
            if not tool_invoke_result:
                logger.info(f"Tool calls for message {llm_result.id} already completed successfully.")
                return llm_result
            req.messages.append(llm_result.message)
            req.messages.append(ToolPromptMessage(
                content=tool_invoke_result.data,
                tool_call_id=llm_result.message.tool_calls[0].id
            ))
            llm_result = cls._transform_message(model_params, prompt_messages=req, credentials=credentials,
                                                raw_request=raw_request, stream=stream)
        return llm_result

    @classmethod
    def _transform_message(
            cls,
            model_params: dict,
            prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
            credentials: dict,
            raw_request: Request,
            stream: bool = None
    ) -> Union[ChatCompletionResponse, Generator[ChatCompletionResponseChunk, None, None]]:
        ...

    @classmethod
    def setup_validate_credentials(cls, credentials):
        """Validate credentials."""
        ...

    @classmethod
    def transform_embeddings(cls, texts:EmbeddingRequest, credentials:dict)->TextEmbeddingResult:
        """Transform embeddings."""
        ...
