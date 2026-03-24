from runtime.clients.handler.llm_http_handler import LLMHttpHandler
from runtime.entities.llm_entities import LLMRequest, LLMResponse
from runtime.entities.rerank_entities import RerankRequest, RerankResponse
from runtime.entities.text_embedding_entities import EmbeddingRequest, TextEmbeddingResult
from runtime.transformation.base import LLMTransformation


class OllamaTransformation(LLMTransformation):
    """
    Translates from OpenAI-like API to Ollama API.

    Ollama API specifics:
    - API Base: http://localhost:11434
    - Chat endpoint: /api/chat (not /v1/chat/completions)
    - Embeddings endpoint: /api/embeddings
    - API Key: Optional (Ollama doesn't require it)
    """

    provider_type = "ollama"
    DEFAULT_API_BASE = "http://localhost:11434"

    @classmethod
    def setup_environment(cls, credentials, params=None):
        _credentials = credentials.get("credentials", {})
        api_base = _credentials.get("api_base", cls.DEFAULT_API_BASE)
        api_key = _credentials.get("api_key")

        headers = {"Content-Type": "application/json;charset=utf-8"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        user_agent = "AduibLLM-Ollama-Client/1.0"
        if params:
            user_agent = params.get("user_agent") or user_agent
        if user_agent:
            headers["User-Agent"] = user_agent

        return {
            "api_key": api_key,
            "api_base": api_base,
            "headers": headers,
            "sdk_type": credentials.get("sdk_type"),
        }

    @classmethod
    async def _transform_message(
        cls,
        model_params: dict,
        prompt_messages: LLMRequest,
        credentials: dict,
        stream: bool = None,
    ) -> LLMResponse:
        llm_http_handler = LLMHttpHandler("/api/chat", credentials, stream)
        return await llm_http_handler.completion_request(prompt_messages)

    @classmethod
    async def transform_embeddings(cls, texts: EmbeddingRequest, credentials: dict) -> TextEmbeddingResult:
        llm_http_handler = LLMHttpHandler("/api/embeddings", credentials, False)
        return await llm_http_handler.embedding_request(texts)
