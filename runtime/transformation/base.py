import logging
from typing import Union, Generator, Any

from runtime.entities import ToolPromptMessage, AssistantPromptMessage, TextPromptMessageContent, UserPromptMessage
from runtime.entities.llm_entities import (
    ChatCompletionRequest,
    CompletionRequest,
    ChatCompletionResponse,
    ChatCompletionResponseChunk, CompletionResponse,
)
from runtime.entities.rerank_entities import RerankRequest, RerankResponse
from runtime.entities.text_embedding_entities import EmbeddingRequest, TextEmbeddingResult
from runtime.tool.entities import ToolInvokeResult

logger = logging.getLogger(__name__)


class LLMTransformation:
    """Base class for all transformations."""

    @classmethod
    def setup_model_parameters(
        cls,credentials:dict, model_params: dict[str, Any], prompt_messages: Union[ChatCompletionRequest, CompletionRequest]
    ):
        """Validate model parameters."""
        if not prompt_messages.temperature:
            prompt_messages.temperature = model_params.get("temperature")
        if not prompt_messages.top_p:
            prompt_messages.top_p = model_params.get("top_p")
        if not prompt_messages.top_k:
            prompt_messages.top_k = model_params.get("top_k")
        if not prompt_messages.presence_penalty:
            prompt_messages.presence_penalty = model_params.get("presence_penalty")
        if not prompt_messages.frequency_penalty:
            prompt_messages.frequency_penalty = model_params.get("frequency_penalty")
        # if not prompt_messages.miniP:
        #     prompt_messages.miniP = model_params.get("miniP", 0.0)
        # 判断模型名称是否包含Qwen3
        if 'Qwen3' in prompt_messages.model and isinstance(prompt_messages, ChatCompletionRequest):
            content=prompt_messages.messages[-1].content
            if isinstance(content,str):
                if prompt_messages.enable_thinking:
                    prompt_messages.messages[-1].content = content+" /think"
                else:
                    prompt_messages.messages[-1].content = content+" /no_think"
            elif isinstance(content,list):
                if prompt_messages.enable_thinking:
                    content.insert(len(content),TextPromptMessageContent(data="/think",text="/think"))
                else:
                    content.insert(len(content),TextPromptMessageContent(data="/no_think",text="/no_think"))
                prompt_messages.messages[-1].content = content
        return prompt_messages

    @classmethod
    def transform_message(
        cls,
        model_params: dict,
        prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
        credentials: dict,
        stream: bool = None,
    ) -> Union[CompletionResponse, Generator[CompletionResponse, None, None]]:
        """
        Transform the input message using the provided credentials and raw request.
        :param model_params: The model parameters for transformation.
        :param prompt_messages: The input messages to be transformed.
        :param credentials: The credentials required for transformation.
        :param stream: Whether to return a streaming response.
        :return: A response object containing the transformed message, or a streaming response if requested.
        """
        llm_result = cls._transform_message(model_params, prompt_messages, credentials, stream)
        if prompt_messages.tools:
            return cls._call_tools(model_params,prompt_messages, credentials, llm_result,stream)
        return llm_result

    @classmethod
    def _call_tools(
        cls,
        model_params: dict,
        req: Union[ChatCompletionRequest, CompletionRequest],
        credentials: dict,
        llm_result: Union[CompletionResponse, Generator[CompletionResponse, None, None]],
        stream: bool = None,
    ) -> Union[CompletionResponse, Generator[CompletionResponse, None, None]]:
        if not isinstance(llm_result, ChatCompletionResponse):
            return llm_result
        tools_calls: list[AssistantPromptMessage.ToolCall] = []
        for chunkContent in llm_result.choices:
            if chunkContent.message and chunkContent.message.tool_calls:
                for tool_call in chunkContent.message.tool_calls:
                    tools_calls.append(tool_call)
        if len(tools_calls) > 0:
            from runtime.tool.tool_manager import ToolManager

            tool_manager = ToolManager()
            tool_invoke_result: ToolInvokeResult = tool_manager.invoke_tools(
                tools_calls, llm_result.id
            )
            if not tool_invoke_result:
                logger.info(f"Tool calls for message {llm_result.id} already completed successfully.")
                return llm_result
            if tool_invoke_result.success:
                for chunkContent in llm_result.choices:
                    if chunkContent.message:
                        req.messages.append(chunkContent.message)
                    else:
                        req.messages.append(chunkContent.delta)
                req.messages.append(
                    ToolPromptMessage(content=tool_invoke_result.data, tool_call_id=tools_calls[0].id)
                )
                llm_result = cls._transform_message(
                    model_params, prompt_messages=req, credentials=credentials, stream=stream
                )
        return llm_result

    @classmethod
    def _transform_message(
        cls,
        model_params: dict,
        prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
        credentials: dict,
        stream: bool = None,
    ) -> Union[CompletionResponse, Generator[CompletionResponse, None, None]]: ...

    @classmethod
    def setup_environment(cls, credentials: dict, model_params: dict):
        """Validate credentials."""
        ...

    @classmethod
    def transform_embeddings(cls, texts: EmbeddingRequest, credentials: dict) -> TextEmbeddingResult:
        """Transform embeddings."""
        ...

    @classmethod
    def transform_rerank(cls, query: RerankRequest, credentials: dict) -> RerankResponse:
        """Transform rerank."""
        ...
