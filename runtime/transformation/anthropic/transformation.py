import logging
from typing import Any, Optional

from runtime.clients.handler.llm_http_handler import LLMHttpHandler
from runtime.entities.llm_entities import LLMRequest, LLMResponse
from runtime.entities.rerank_entities import RerankRequest, RerankResponse
from runtime.entities.text_embedding_entities import EmbeddingRequest, TextEmbeddingResult
from runtime.transformation.base import LLMTransformation

from ...entities.provider_entities import ProviderSDKType

logger = logging.getLogger(__name__)


def map_stop_reason(finish_reason: Optional[str]) -> str:
    if finish_reason == "tool_calls":
        return "tool_use"
    if finish_reason == "stop":
        return "end_turn"
    if finish_reason == "length":
        return "max_tokens"
    return "end_turn"


def normalize_content(content: Any) -> Optional[str]:
    # If content is a string, return it directly.
    if isinstance(content, str):
        return content
    # If content is a list of blocks (with potential {text}), join texts.
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                txt = item.get("text")
                if isinstance(txt, str):
                    parts.append(txt)
        return " ".join(parts) if len(parts) > 0 else "..."
    return None


def remove_uri_format(schema: Any) -> Any:
    # Recursively traverse JSON schema and remove format: 'uri'
    if not isinstance(schema, (dict, list)):
        return schema

    if isinstance(schema, list):
        return [remove_uri_format(it) for it in schema]

    # dict case
    if schema.get("type") == "string" and schema.get("format") == "uri":
        # return a copy without 'format'
        result = dict(schema)
        result.pop("format", None)
        return result

    result: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "properties" and isinstance(value, dict):
            result[key] = {k: remove_uri_format(v) for k, v in value.items()}
        elif (
            key == "items"
            and isinstance(value, (dict, list))
            or key == "additionalProperties"
            and isinstance(value, (dict, list))
        ):
            result[key] = remove_uri_format(value)
        elif key in ("anyOf", "allOf", "oneOf") and isinstance(value, list):
            result[key] = [remove_uri_format(v) for v in value]
        else:
            result[key] = remove_uri_format(value)
    return result


def _approx_tokens_from_text(text: str) -> int:
    # Very rough estimate: word count as token count fallback
    if not text:
        return 0
    return len([w for w in text.strip().split() if w])


def _approx_tokens_from_messages(msgs: list[dict[str, Any]]) -> int:
    total = 0
    for m in msgs or []:
        c = m.get("content")
        if isinstance(c, str):
            total += _approx_tokens_from_text(c)
    return total


class AnthropicTransformation(LLMTransformation):
    """
    Transformation class for Anthropic Claude models.
    Handles API communication with Anthropic's Claude API using x-api-key authentication.
    """

    @classmethod
    def setup_environment(cls, credentials, params=None):
        """
        Setup environment for Anthropic API.
        Validates credentials and prepares headers with x-api-key authentication.

        Args:
            credentials: Dictionary containing API credentials
            params: Additional parameters

        Returns:
            Dictionary with API configuration

        Raises:
            ValueError: If API key is missing or invalid
        """
        _credentials = credentials["credentials"]

        # Validate API key
        if "api_key" not in _credentials or not _credentials["api_key"]:
            raise ValueError("api_key is required in credentials for Anthropic API")

        # Prepare headers with x-api-key authentication
        headers = {
            "X-Api-Key": _credentials["api_key"],
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        # Get API base URL or use default
        api_base = _credentials.get("api_base", "https://api.anthropic.com/v1")
        if credentials["none_anthropic"] and credentials["orig_sdk_type"] == ProviderSDKType.GITHUB_COPILOT:
            from runtime.transformation.github.Authenticator import Authenticator

            authenticator = Authenticator()
            api_base = authenticator.get_api_base()

            vision = False
            if params:
                vision = params.get("vision", False)
            headers = authenticator.get_copilot_headers(vision=vision)
        else:
            # Add user agent if provided
            user_agent = "AduibLLM-Anthropic-Client/1.0"
            if params:
                user_agent = params.get("user_agent", user_agent)
            headers["User-Agent"] = user_agent

        return {
            "api_key": _credentials["api_key"],
            "api_base": api_base,
            "headers": headers,
            "sdk_type": credentials["sdk_type"],
            "none_anthropic": credentials["none_anthropic"],
            "orig_sdk_type": credentials["orig_sdk_type"],
        }

    @classmethod
    async def _transform_message(
        cls,
        model_params: dict,
        prompt_messages: LLMRequest,
        credentials: dict,
        stream: bool = None,
    ) -> LLMResponse:
        """
        Transform messages for Anthropic Claude API.

        Args:
            model_params: Model parameters
            prompt_messages: Input messages
            credentials: API credentials
            stream: Whether to use streaming

        Returns:
            Chat completion response or generator for streaming
        """

        llm_http_handler = LLMHttpHandler("/messages", credentials, stream)
        return await llm_http_handler.message_request(prompt_messages)

    @classmethod
    async def transform_embeddings(cls, texts: EmbeddingRequest, credentials: dict) -> TextEmbeddingResult:
        """
        Transform embeddings request for Anthropic API.
        Note: Anthropic doesn't have a dedicated embeddings endpoint.

        Args:
            texts: Embedding request
            credentials: API credentials

        Returns:
            Text embedding result

        Raises:
            NotImplementedError: As Anthropic doesn't support embeddings
        """
        raise NotImplementedError("Anthropic API does not support embeddings endpoint")

    @classmethod
    async def transform_rerank(cls, query: RerankRequest, credentials: dict) -> RerankResponse:
        """
        Transform rerank request for Anthropic API.
        Note: Anthropic doesn't have a dedicated rerank endpoint.

        Args:
            query: Rerank request
            credentials: API credentials

        Returns:
            Rerank response

        Raises:
            NotImplementedError: As Anthropic doesn't support reranking
        """
        raise NotImplementedError("Anthropic API does not support rerank endpoint")

    @classmethod
    def get_supported_models(cls) -> list[str]:
        """
        Get list of supported Claude model versions.

        Returns:
            List of supported model names
        """
        return []

    @classmethod
    def validate_model(cls, model_name: str) -> bool:
        """
        Validate if a model name is supported by Anthropic.

        Args:
            model_name: Model name to validate

        Returns:
            True if model is supported, False otherwise
        """
        return False
