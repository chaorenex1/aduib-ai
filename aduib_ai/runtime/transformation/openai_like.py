from typing import Union, Generator

from runtime.clients.openai_like_client import OpenAILikeClient
from runtime.entities import ChatCompletionResponse, ChatCompletionResponseChunk
from runtime.entities.llm_entities import ChatCompletionRequest, CompletionRequest
from runtime.mcp.types import Request
from runtime.transformation.base import LLMTransformation


class OpenAILikeTransformation(LLMTransformation):
    """
    Translates from OpenAI's `/v1/chat/completions` to the target LLM's chat completion API.
    """

    @classmethod
    def _transform_message(cls, prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
                           credentials: dict,
                           raw_request: Request,
                           stream:bool = None) -> Union[
        ChatCompletionResponse, Generator[ChatCompletionResponseChunk, None, None]]:

        client = OpenAILikeClient()
        return client.completion_request(prompt_messages, credentials, raw_request,stream)

