from concurrent import futures
from typing import Union, Generator

from runtime.clients.handler.llm_http_handler import LLMHttpHandler
from runtime.entities import ChatCompletionResponse, ChatCompletionResponseChunk
from runtime.entities.llm_entities import ChatCompletionRequest, CompletionRequest
from runtime.mcp.types import Request
from runtime.transformation.base import LLMTransformation


class OpenAILikeTransformation(LLMTransformation):
    """
    Translates from OpenAI's `/v1/chat/completions` to the target LLM's chat completion API.
    """
    provider_type = "openai_like"

    @classmethod
    def setup_validate_credentials(cls, credentials, params=None):
        _credentials = credentials["credentials"]
        if "api_key" not in _credentials or not _credentials["api_key"]:
            raise ValueError("api_key is required in credentials")
        headers = {"Authorization": f"Bearer {_credentials['api_key']}", "X-Api-Key": _credentials['api_key']}
        api_base = _credentials.get("api_base", "https://api.openai.com/v1")
        user_agent = "AduibLLM-OpenAI-Client/1.0"
        if params:
            user_agent = params.get("user_agent")
        if user_agent:
            headers["User-Agent"] = user_agent
        headers["Content-Type"] = "application/json;charset=utf-8"
        return {"api_key": _credentials["api_key"], "api_base": api_base, "headers": headers,
                "sdk_type": credentials["sdk_type"]}

    @classmethod
    def _transform_message(cls, model_params: dict,
                           prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
                           credentials: dict,
                           raw_request: Request,
                           stream: bool = None) -> Union[
        ChatCompletionResponse, Generator[ChatCompletionResponseChunk, None, None]]:
        llm_http_handler = LLMHttpHandler('/v1/chat/completions', credentials, stream)
        return llm_http_handler.completion_request(prompt_messages)
