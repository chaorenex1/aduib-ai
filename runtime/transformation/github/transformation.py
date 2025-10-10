import json
from multiprocessing import AuthenticationError
from typing import Union, Generator, List

from starlette.requests import Request

from runtime.clients.handler.llm_http_handler import LLMHttpHandler
from runtime.entities import ChatCompletionResponse, ChatCompletionResponseChunk, PromptMessage
from runtime.entities.llm_entities import ChatCompletionRequest, CompletionRequest, CompletionResponse
from runtime.entities.rerank_entities import RerankRequest, RerankResponse
from runtime.entities.text_embedding_entities import EmbeddingRequest, TextEmbeddingResult
from runtime.transformation.base import LLMTransformation
from runtime.transformation.github.Authenticator import Authenticator
from runtime.transformation.github.error import GetAPIKeyError
from utils import jsonable_encoder


class GithubCopilotTransformation(LLMTransformation):
    """
    Translates from Deepseek API to provider-specific API.
    """

    provider_type = "github_copilot"

    GITHUB_COPILOT_API_BASE = "https://api.githubcopilot.com"

    @classmethod
    def setup_environment(cls, credentials, params=None):
        _credentials = credentials["credentials"]
        authenticator = Authenticator()
        dynamic_api_base = authenticator.get_api_base() or cls.GITHUB_COPILOT_API_BASE
        vision = False
        if params:
            vision = params.get("vision", False)
        headers = authenticator.get_copilot_headers(vision=vision)
        return {
            "api_key": _credentials["api_key"],
            "api_base": dynamic_api_base,
            "headers": headers,
            "sdk_type": credentials["sdk_type"],
        }

    @classmethod
    def _transform_message(
        cls,
        model_params: dict,
        prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
        credentials: dict,
        stream: bool = None,
    ) -> Union[CompletionResponse, Generator[CompletionResponse, None, None]]:
        # credentials["headers"]["X-User-Initiator"] = cls._determine_initiator(prompt_messages.messages)
        # credentials["headers"]["X-Initiator"] = cls._determine_initiator(prompt_messages.messages)
        llm_http_handler = LLMHttpHandler("/chat/completions", credentials, stream)
        return llm_http_handler.completion_request(prompt_messages)
        # data = jsonable_encoder(prompt_messages, exclude_unset=True, exclude_none=True)
        # print("Request to Github Copilot:", json.dumps(data, indent=2))
        # return None

    @classmethod
    def transform_embeddings(cls, texts: EmbeddingRequest, credentials: dict) -> TextEmbeddingResult:
        llm_http_handler = LLMHttpHandler("/embeddings", credentials, False)
        return llm_http_handler.embedding_request(texts)

    @classmethod
    def transform_rerank(cls, query: RerankRequest, credentials: dict) -> RerankResponse:
        llm_http_handler = LLMHttpHandler("/rerank", credentials, False)
        return llm_http_handler.rerank_request(query)

    def _determine_initiator(self, messages: List[PromptMessage]) -> str:
        """
        Determine if request is user or agent initiated based on message roles.
        Returns 'agent' if any message has role 'tool' or 'assistant', otherwise 'user'.
        """
        for message in messages:
            role = message.role.value
            if role in ["tool", "assistant"]:
                return "agent"
        return "user"
