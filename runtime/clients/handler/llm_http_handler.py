import json
import traceback
from typing import Union, Generator, TypeVar, Any, AsyncGenerator, Coroutine, AsyncIterator, overload

from fastapi import Request
from httpx import Response
from pydantic import BaseModel

from controllers.common.error import InnerError
from runtime.clients.httpx_client import get_httpx_client
from runtime.entities.rerank_entities import RerankRequest, RerankResponse
from runtime.entities.text_embedding_entities import TextEmbeddingResult, EmbeddingRequest
from utils import jsonable_encoder
from runtime.entities import ChatCompletionResponse, ChatCompletionResponseChunk
from runtime.entities.llm_entities import ChatCompletionRequest, CompletionRequest

T = TypeVar("T", bound=(BaseModel | dict | list | bool | str))


class LLMHttpHandler:
    """
    A handler for making HTTP requests to LLM APIs.
    """

    def __init__(self, api_path: str, credentials: dict, stream: bool) -> None:
        self.credentials = credentials
        self.httpx_client = get_httpx_client()
        api_base = credentials["api_base"]
        if api_base.endswith("/"):
            api_base = api_base[:-1]
        if api_base.endswith("/v1"):
            api_base = api_base[:-3]
        self.path = api_base + api_path
        self.headers = credentials["headers"]
        self.stream = stream

    def _request(
        self,
        data: bytes | dict | str | None = None,
        params: dict | None = None,
        files: dict | None = None,
    ) -> Response:
        """
        Make a request to  API.
        """
        response = self.httpx_client.post(
            self.path, params=params, headers=self.headers, json=data, files=files, stream=self.stream,timeout=300
        )

        return response

    def _stream_request(
        self,
        data: bytes | dict | None = None,
        params: dict | None = None,
        files: dict | None = None,
    ) -> Generator[str, None, None]:
        """
        Make a stream request to the plugin daemon inner API
        """
        response = self._request(data, params, files)
        for line in response.iter_lines():
            if line.startswith("data:"):
                line = line[5:].strip()
            if line:
                yield line

    def _stream_request_with_model(
        self,
        type: type[T],
        data: bytes | dict | None = None,
        params: dict | None = None,
        files: dict | None = None,
    ) -> Generator[T, None, None]:
        """
        Make a stream request to the plugin daemon inner API and yield the response as a model.
        """
        for line in self._stream_request(data, params, files):
            try:
                if line == "[DONE]":
                    yield type(done=True)  # type: ignore
                else:
                    yield type(**json.loads(line))  # type: ignore
            except Exception as e:
                raise e

    def _request_with_model(
        self,
        type: type[T],
        data: bytes | dict | None = None,
        params: dict | None = None,
        files: dict | None = None,
    ) -> T | Generator[T, None, None]:
        """
        Make a request to the plugin daemon inner API and return the response as a model.
        """
        response = self._request(data, params, files)
        json = response.json()
        return type(**json)  # type: ignore

    def completion_request(
        self, prompt_messages: Union[ChatCompletionRequest, CompletionRequest]
    ) -> Generator[ChatCompletionResponse, None, None] | ChatCompletionResponse:
        return self.completion_dict(jsonable_encoder(obj=prompt_messages, exclude_none=True, exclude_unset=True))

    def completion_dict(
        self, prompt_messages: dict[str, Any]
    ) -> Generator[ChatCompletionResponse, None, None] | ChatCompletionResponse:
        if self.stream:
            response = self._stream_request_with_model(type=ChatCompletionResponseChunk, data=prompt_messages)
        else:
            response = self._request_with_model(type=ChatCompletionResponse, data=prompt_messages)

        def handle_stream_response(res) -> Generator[ChatCompletionResponse, None, None]:
            """
            Handle the stream response and yield the final response
            """
            yield from res


        def handle_no_stream_response(res) -> ChatCompletionResponse:
            """
            Handle the non-stream response and return the final response
            """
            if isinstance(res, ChatCompletionResponse):
                return res
            else:
                return next(res)
        if isinstance(response, Generator):
            return handle_stream_response(response)
        else:
            return handle_no_stream_response(response)

    def embedding_request(self, texts: EmbeddingRequest) -> TextEmbeddingResult:
        response = self._request_with_model(type=TextEmbeddingResult, data=jsonable_encoder(texts, exclude_none=True))
        return response

    def rerank_request(self, query: RerankRequest) -> RerankResponse:
        response = self._request_with_model(type=RerankResponse, data=jsonable_encoder(query, exclude_none=True))
        return response
