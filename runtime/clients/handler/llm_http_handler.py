import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, TypeVar

from httpx import Response
from pydantic import BaseModel

from configs import config
from runtime.clients.httpx_client import get_async_httpx_client
from runtime.entities import (
    AnthropicStreamEvent,
    ChatCompletionResponse,
    ChatCompletionResponseChunk,
    ResponseOutput,
    ResponseStreamEvent,
)
from runtime.entities.anthropic_entities import AnthropicMessageResponse, parse_sse_event
from runtime.entities.llm_entities import LLMRequest, LLMResponse
from runtime.entities.rerank_entities import RerankRequest, RerankResponse
from runtime.entities.response_entities import parse_response_sse_event
from runtime.entities.text_embedding_entities import EmbeddingRequest, TextEmbeddingResult
from utils import jsonable_encoder

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=(BaseModel | dict | list | bool | str))


class LLMHttpHandler:
    """
    A handler for making HTTP requests to LLM APIs.
    """

    def __init__(self, api_path: str, credentials: dict, stream: bool) -> None:
        self.credentials = credentials
        self.httpx_client = get_async_httpx_client(llm_provider=api_path)
        api_base = credentials["api_base"]
        api_base = api_base.removesuffix("/")
        api_base = api_base.removesuffix("/v1")
        self.path = api_base + api_path
        self.headers = credentials["headers"]
        self.stream = stream

    async def _request(
        self,
        data: bytes | dict | str | None = None,
        params: dict | None = None,
        files: dict | None = None,
    ) -> Response:
        """
        Make a request to  API.
        """
        response = await self.httpx_client.post(
            self.path,
            params=params,
            headers=self.headers,
            json=data,
            files=files,
            stream=self.stream,
            timeout=config.API_TIME_OUT,
        )

        return response

    async def _stream_request(
        self,
        data: bytes | dict | None = None,
        params: dict | None = None,
        files: dict | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Make a stream request to the plugin daemon inner API
        """
        response = await self._request(data, params, files)
        async for line in response.aiter_lines():
            if line.startswith("data:"):
                line = line[5:].strip()
            if line:
                yield line

    async def _stream_anthropic_request(
        self,
        data: bytes | dict | None = None,
        params: dict | None = None,
        files: dict | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Make a stream request to the plugin daemon inner API and yield the response as AnthropicStreamEvent.
        """
        response = await self._request(data, params, files)
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                logger.debug("%Received event line: {line}")
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
            if line:
                yield line

    async def _stream_request_with_model(
        self,
        type: type[T],
        data: bytes | dict | None = None,
        params: dict | None = None,
        files: dict | None = None,
    ) -> AsyncGenerator[T, None]:
        """
        Make a stream request to the plugin daemon inner API and yield the response as a model.
        """
        async for line in self._stream_request(data, params, files):
            try:
                if line == "[DONE]":
                    yield type(done=True)  # type: ignore
                else:
                    # logger.debug("%Parsing line: {line}")
                    chunk = json.loads(line)
                    yield type(**chunk)  # type: ignore
            except Exception as e:
                logger.exception("Error parsing line: {line}, error: {e}")
                raise e

    async def _stream_completion(
        self,
        data: bytes | dict | None = None,
        params: dict | None = None,
        files: dict | None = None,
    ) -> AsyncGenerator[ChatCompletionResponseChunk, None]:
        """OpenAI Chat Completions stream parser: signals end-of-stream with done=True."""
        async for line in self._stream_request(data, params, files):
            try:
                if line == "[DONE]":
                    yield ChatCompletionResponseChunk(done=True)
                else:
                    chunk = json.loads(line)
                    yield ChatCompletionResponseChunk(**chunk)
            except Exception as e:
                logger.exception("Error parsing completion chunk: {line}, error: {e}")
                raise

    async def _stream_anthropic_message(
        self,
        data: bytes | dict | None = None,
        params: dict | None = None,
        files: dict | None = None,
    ) -> AsyncGenerator[AnthropicStreamEvent, None]:
        """Anthropic Messages stream parser: uses parse_sse_event() for subtype dispatch."""
        async for line in self._stream_anthropic_request(data, params, files):
            try:
                if line == "[DONE]":
                    yield AnthropicStreamEvent(type="message_stop", done=True)
                else:
                    chunk = json.loads(line)
                    yield parse_sse_event(chunk)
            except Exception as e:
                logger.exception("Error parsing anthropic message event: {line}, error: {e}")
                raise

    async def _stream_response(
        self,
        data: bytes | dict | None = None,
        params: dict | None = None,
        files: dict | None = None,
    ) -> AsyncGenerator[ResponseStreamEvent, None]:
        """OpenAI Responses API stream parser: uses RESPONSE_SSE_EVENT_TYPES for subtype dispatch."""
        async for line in self._stream_request(data, params, files):
            try:
                if line == "[DONE]":
                    return  # response.done event already yielded as a real SSE line
                else:
                    chunk = json.loads(line)
                    yield parse_response_sse_event(chunk)
            except Exception as e:
                logger.exception("Error parsing response stream event: {line}, error: {e}")
                raise

    async def _request_with_model(
        self,
        type: type[T],
        data: bytes | dict | None = None,
        params: dict | None = None,
        files: dict | None = None,
    ) -> T:
        """
        Make a request to the plugin daemon inner API and return the response as a model.
        """
        response = await self._request(data, params, files)
        json = response.json()
        return type(**json)  # type: ignore

    async def completion_request(self, prompt_messages: LLMRequest) -> LLMResponse:
        return await self.completion_dict(jsonable_encoder(obj=prompt_messages, exclude_none=True))

    async def message_request(self, prompt_messages: LLMRequest) -> LLMResponse:
        return await self.message_dict(jsonable_encoder(obj=prompt_messages, exclude_none=True))

    async def response_request(self, prompt_messages: LLMRequest) -> LLMResponse:
        return await self.response_dict(jsonable_encoder(obj=prompt_messages, exclude_none=True))

    async def response_dict(self, prompt_messages: dict[str, Any]) -> LLMResponse:
        if self.stream:
            return self._stream_response(data=prompt_messages)
        else:
            return await self._request_with_model(type=ResponseOutput, data=prompt_messages)

    async def message_dict(self, prompt_messages: dict[str, Any]) -> LLMResponse:
        if self.stream:
            return self._stream_anthropic_message(data=prompt_messages)
        else:
            return await self._request_with_model(type=AnthropicMessageResponse, data=prompt_messages)

    async def completion_dict(self, prompt_messages: dict[str, Any]) -> LLMResponse:
        if self.stream:
            return self._stream_completion(data=prompt_messages)
        else:
            return await self._request_with_model(type=ChatCompletionResponse, data=prompt_messages)

    async def embedding_request(self, texts: EmbeddingRequest) -> TextEmbeddingResult:
        response = await self._request_with_model(
            type=TextEmbeddingResult, data=jsonable_encoder(texts, exclude_none=True)
        )
        return response

    async def rerank_request(self, query: RerankRequest) -> RerankResponse:
        response = await self._request_with_model(type=RerankResponse, data=jsonable_encoder(query, exclude_none=True))
        return response
