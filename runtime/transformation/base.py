import logging
from typing import Any, Optional

from runtime.entities import (
    TextPromptMessageContent,
)
from runtime.entities.llm_entities import (
    ChatCompletionRequest,
    LLMRequest,
    LLMResponse,
)
from runtime.entities.rerank_entities import RerankRequest, RerankResponse
from runtime.entities.text_embedding_entities import EmbeddingRequest, TextEmbeddingResult
from runtime.entities.tts_entities import TTSRequest, TTSResponse, TTSVoice
from runtime.entities.asr_entities import ASRRequest, ASRResponse

logger = logging.getLogger(__name__)


class LLMTransformation:
    """Base class for all transformations."""

    @classmethod
    def setup_model_parameters(cls, credentials: dict, model_params: dict[str, Any], prompt_messages: LLMRequest):
        """Validate model parameters."""
        if hasattr(prompt_messages, "temperature") and not getattr(prompt_messages, "temperature", None):
            prompt_messages.temperature = model_params.get("temperature")
        if hasattr(prompt_messages, "top_p") and not getattr(prompt_messages, "top_p", None):
            prompt_messages.top_p = model_params.get("top_p")
        if hasattr(prompt_messages, "top_k") and not getattr(prompt_messages, "top_k", None):
            prompt_messages.top_k = model_params.get("top_k")
        if hasattr(prompt_messages, "presence_penalty") and not getattr(prompt_messages, "presence_penalty", None):
            prompt_messages.presence_penalty = model_params.get("presence_penalty")
        if hasattr(prompt_messages, "frequency_penalty") and not getattr(prompt_messages, "frequency_penalty", None):
            prompt_messages.frequency_penalty = model_params.get("frequency_penalty")
        # if not prompt_messages.miniP:
        #     prompt_messages.miniP = model_params.get("miniP", 0.0)
        if hasattr(prompt_messages, "max_tokens") and getattr(prompt_messages, "max_tokens", None):
            prompt_messages.max_tokens = min(prompt_messages.max_tokens, model_params.get("max_tokens"))
        # 判断模型名称是否包含Qwen3
        if getattr(prompt_messages, "model", None) and "Qwen3" in prompt_messages.model and isinstance(
            prompt_messages, ChatCompletionRequest
        ):
            content = prompt_messages.messages[-1].content
            if isinstance(content, str):
                if prompt_messages.enable_thinking:
                    prompt_messages.messages[-1].content = content + " /think"
                else:
                    prompt_messages.messages[-1].content = content + " /no_think"
            elif isinstance(content, list):
                if prompt_messages.enable_thinking:
                    content.insert(len(content), TextPromptMessageContent(data="/think", text="/think"))
                else:
                    content.insert(len(content), TextPromptMessageContent(data="/no_think", text="/no_think"))
                prompt_messages.messages[-1].content = content
        return prompt_messages

    @classmethod
    async def transform_message(
        cls,
        model_params: dict,
        prompt_messages: LLMRequest,
        credentials: dict,
        stream: bool = None,
        source: Optional[str] = None,
    ) -> LLMResponse:
        """
        Transform the input message using the provided credentials and raw request.
        :param model_params: The model parameters for transformation.
        :param prompt_messages: The input messages to be transformed.
        :param credentials: The credentials required for transformation.
        :param stream: Whether to return a streaming response.
        :return: LLMResponse (full response or stream response chunk generator)
        """
        llm_result = await cls._transform_message(model_params, prompt_messages, credentials, stream)
        return llm_result

    @classmethod
    async def _transform_message(
        cls,
        model_params: dict,
        prompt_messages: LLMRequest,
        credentials: dict,
        stream: bool = None,
    ) -> LLMResponse: ...

    @classmethod
    def setup_environment(cls, credentials: dict, model_params: dict):
        """Validate credentials."""
        ...

    @classmethod
    async def transform_embeddings(cls, texts: EmbeddingRequest, credentials: dict) -> TextEmbeddingResult:
        """Transform embeddings."""
        ...

    @classmethod
    async def transform_rerank(cls, query: RerankRequest, credentials: dict) -> RerankResponse:
        """Transform rerank."""
        ...

    @classmethod
    async def transform_tts(cls, tts_request: TTSRequest, credentials: dict) -> TTSResponse:
        """
        Transform TTS request and return audio content.
        :param tts_request: The TTS request to be transformed.
        :param credentials: The credentials required for transformation.
        :return: TTSResponse containing audio data.
        """
        ...

    @classmethod
    async def transform_tts_voices(cls, model: str, credentials: dict, language: Optional[str] = None) -> list[dict]:
        """
        Transform TTS voices request and return available voices.
        :param model: The TTS model name.
        :param credentials: The credentials required for transformation.
        :param language: Optional language code to filter voices.
        :return: List of voice dictionaries.
        """
        ...

    @classmethod
    async def transform_audio2text(cls, asr_request: ASRRequest, credentials: dict) -> ASRResponse:
        """
        Transform ASR request and return transcription.
        :param asr_request: The ASR request to be transformed.
        :param credentials: The credentials required for transformation.
        :return: ASRResponse containing transcribed text.
        """
        ...
