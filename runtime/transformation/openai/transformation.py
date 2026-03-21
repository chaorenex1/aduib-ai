import logging
from typing import Any

from runtime.clients.handler.llm_http_handler import LLMHttpHandler
from runtime.entities.llm_entities import (
    LLMRequest,
    LLMResponse,
)
from runtime.entities.response_entities import (
    ResponseRequest,
)
from runtime.transformation.base import LLMTransformation

logger = logging.getLogger(__name__)


class OpenaiResponseTransformation(LLMTransformation):
    """
    Transformation for OpenAI Response API (/v1/responses).
    """

    provider_type = "response"

    @classmethod
    def setup_model_parameters(cls, credentials: dict, model_params: dict[str, Any], prompt_messages: LLMRequest):
        """Setup model parameters for Response API."""
        if not isinstance(prompt_messages, ResponseRequest):
            # Delegate to parent for ChatCompletionRequest
            return super().setup_model_parameters(credentials, model_params, prompt_messages)

        # ResponseRequest - apply model_params defaults if not set
        if not prompt_messages.temperature:
            prompt_messages.temperature = model_params.get("temperature")
        if not prompt_messages.top_p:
            prompt_messages.top_p = model_params.get("top_p")

        return prompt_messages

    @classmethod
    def setup_environment(cls, credentials: dict, params: dict = None):
        """Setup environment for transformation."""
        _credentials = credentials.get("credentials", credentials)
        if "api_key" not in _credentials or not _credentials["api_key"]:
            raise ValueError("api_key is required in credentials")

        headers = {
            "Authorization": f"Bearer {_credentials['api_key']}",
            "X-Api-Key": _credentials["api_key"],
            "Content-Type": "application/json;charset=utf-8",
        }

        api_base = _credentials.get("api_base", "https://api.openai.com/v1")

        return {
            "api_key": _credentials["api_key"],
            "api_base": api_base,
            "headers": headers,
            "sdk_type": credentials.get("sdk_type", ""),
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
        Transform message - directly call /v1/responses endpoint.
        """
        # Directly call /v1/responses endpoint
        llm_http_handler = LLMHttpHandler("/responses", credentials, stream)
        return await llm_http_handler.response_request(prompt_messages)
