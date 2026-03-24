from typing import Optional

from runtime.clients.handler.llm_http_handler import LLMHttpHandler
from runtime.entities.llm_entities import LLMRequest, LLMResponse
from runtime.entities.rerank_entities import RerankRequest, RerankResponse
from runtime.entities.text_embedding_entities import EmbeddingRequest, TextEmbeddingResult
from runtime.entities.tts_entities import TTSRequest, TTSResponse, TTSVoice
from runtime.entities.asr_entities import ASRRequest, ASRResponse
from runtime.transformation.base import LLMTransformation


class OpenAILikeTransformation(LLMTransformation):
    """
    Translates from OpenAI_like API to provider-specific API.
    """

    provider_type = "openai_like"

    @classmethod
    def setup_environment(cls, credentials, params=None):
        _credentials = credentials["credentials"]
        if "api_key" not in _credentials or not _credentials["api_key"]:
            raise ValueError("api_key is required in credentials")
        headers = {"Authorization": f"Bearer {_credentials['api_key']}", "X-Api-Key": _credentials["api_key"]}
        api_base = _credentials.get("api_base", "https://api.openai.com/v1")
        user_agent = "AduibLLM-OpenAI-Client/1.0"
        if params:
            user_agent = params.get("user_agent")
        if user_agent:
            headers["User-Agent"] = user_agent
        headers["Content-Type"] = "application/json;charset=utf-8"
        return {
            "api_key": _credentials["api_key"],
            "api_base": api_base,
            "headers": headers,
            "sdk_type": credentials["sdk_type"],
        }

    @classmethod
    async def _transform_message(
        cls,
        model_params: dict,
        prompt_messages: LLMRequest,
        credentials: dict,
        stream: bool = None,
    ) -> LLMResponse:
        llm_http_handler = LLMHttpHandler("/v1/chat/completions", credentials, stream)
        return await llm_http_handler.completion_request(prompt_messages)

    @classmethod
    async def transform_embeddings(cls, texts: EmbeddingRequest, credentials: dict) -> TextEmbeddingResult:
        llm_http_handler = LLMHttpHandler("/v1/embeddings", credentials, False)
        return await llm_http_handler.embedding_request(texts)

    @classmethod
    async def transform_rerank(cls, query: RerankRequest, credentials: dict) -> RerankResponse:
        llm_http_handler = LLMHttpHandler("/v1/rerank", credentials, False)
        return await llm_http_handler.rerank_request(query)

    @classmethod
    async def transform_tts(cls, tts_request: TTSRequest, credentials: dict) -> TTSResponse:
        llm_http_handler = LLMHttpHandler("/v1/audio/speech", credentials, False)
        return await llm_http_handler.tts_request(tts_request)

    @classmethod
    async def transform_tts_voices(cls, model: str, credentials: dict, language: Optional[str] = None) -> list[dict]:
        llm_http_handler = LLMHttpHandler("/v1/audio/voices", credentials, False)
        return await llm_http_handler.tts_voices_request(model, language)

    @classmethod
    async def transform_audio2text(cls, asr_request: ASRRequest, credentials: dict) -> ASRResponse:
        llm_http_handler = LLMHttpHandler("/v1/audio/transcriptions", credentials, False)
        return await llm_http_handler.audio2text_request(asr_request)
