from typing import Union, Generator

from runtime.clients.handler.llm_http_handler import LLMHttpHandler
from runtime.entities import ChatCompletionResponse, ChatCompletionResponseChunk
from runtime.entities.llm_entities import ChatCompletionRequest, CompletionRequest
from runtime.entities.rerank_entities import RerankRequest, RerankResponse
from runtime.entities.text_embedding_entities import EmbeddingRequest, TextEmbeddingResult
from runtime.mcp.types import Request
from runtime.transformation.base import LLMTransformation


class DeepseekTransformation(LLMTransformation):
    """
    Translates from Deepseek API to provider-specific API.
    """
    provider_type = "deepseek"

    @classmethod
    def setup_environment(cls, credentials, params=None):
        _credentials = credentials["credentials"]
        if "api_key" not in _credentials or not _credentials["api_key"]:
            raise ValueError("api_key is required in credentials")
        headers = {"Authorization": f"Bearer {_credentials['api_key']}", "X-Api-Key": _credentials['api_key']}
        api_base = _credentials.get("api_base", "https://api.deepseek.com/beta")
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
                           stream: bool = None) -> Union[
        ChatCompletionResponse, Generator[ChatCompletionResponseChunk, None, None]]:
        llm_http_handler = LLMHttpHandler('/chat/completions', credentials, stream)
        return llm_http_handler.completion_request(prompt_messages)

    @classmethod
    def transform_embeddings(cls, texts: EmbeddingRequest, credentials: dict) -> TextEmbeddingResult:
        llm_http_handler = LLMHttpHandler('/embeddings', credentials, False)
        return llm_http_handler.embedding_request(texts)

    @classmethod
    def transform_rerank(cls, query: RerankRequest, credentials: dict) -> RerankResponse:
        llm_http_handler = LLMHttpHandler('/rerank', credentials, False)
        return llm_http_handler.rerank_request(query)