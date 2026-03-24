import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, Optional, TypeVar

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
from runtime.entities.tts_entities import TTSRequest, TTSResponse
from runtime.entities.asr_entities import ASRRequest, ASRResponse
from utils import jsonable_encoder

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=(BaseModel | dict | list | bool | str))

# Maximum audio response size: 100MB
MAX_AUDIO_SIZE_BYTES = 100 * 1024 * 1024

DEFAULT_TTS_MODEL = "tts-1"


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

    async def tts_request(self, tts_request: TTSRequest | dict) -> TTSResponse:
        """
        Make a TTS request and return audio content.

        :param tts_request: TTS request object or dict
        :return: TTSResponse containing audio data
        """
        if isinstance(tts_request, TTSRequest):
            tts_dict = jsonable_encoder(obj=tts_request, exclude_none=True)
        else:
            tts_dict = tts_request

        response = await self._request(data=tts_dict)
        audio_data = response.content

        # Security check: validate audio data size to prevent memory exhaustion
        if len(audio_data) > MAX_AUDIO_SIZE_BYTES:
            raise ValueError(
                f"Audio response too large: {len(audio_data)} bytes exceeds maximum "
                f"allowed size of {MAX_AUDIO_SIZE_BYTES} bytes"
            )

        model = tts_dict.get("model", DEFAULT_TTS_MODEL)
        return TTSResponse(model=model, audio_data=audio_data)

    async def tts_voices_request(self, model: str, language: Optional[str] = None) -> list[dict]:
        """
        Get available voices for a TTS model.

        :param model: TTS model name
        :param language: Optional language code to filter voices
        :return: List of voice dictionaries
        """
        params = {"model": model}
        if language:
            params["language"] = language

        response = await self._request(data=None, params=params)
        json_data = response.json()
        return json_data.get("voices", [])

    async def audio2text_request(self, asr_request: ASRRequest | dict) -> ASRResponse:
        """
        Make an ASR (audio-to-text) request and return transcription.

        :param asr_request: ASR request object or dict
        :return: ASRResponse containing transcribed text
        """
        if isinstance(asr_request, ASRRequest):
            asr_dict = jsonable_encoder(obj=asr_request, exclude_none=True)
        else:
            asr_dict = asr_request

        # Security check: validate audio data size to prevent memory exhaustion
        if "file" in asr_dict:
            file_content = asr_dict["file"]
            if len(file_content) > MAX_AUDIO_SIZE_BYTES:
                raise ValueError(
                    f"Audio file too large: {len(file_content)} bytes exceeds maximum "
                    f"allowed size of {MAX_AUDIO_SIZE_BYTES} bytes"
                )

        # For ASR, we need to send the audio file as a file upload
        # The file content is in the 'file' field
        files = None
        if "file" in asr_dict:
            file_content = asr_dict.pop("file")
            model_name = asr_dict.get("model", "whisper-1")
            # Determine MIME type based on format field or default to mp3
            audio_format = asr_dict.get("format", "mp3")
            # Security: validate audio format against whitelist to prevent path traversal
            ALLOWED_AUDIO_FORMATS = {"mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm", "flac"}
            if audio_format not in ALLOWED_AUDIO_FORMATS:
                raise ValueError(f"Unsupported audio format: {audio_format}")
            mime_types = {
                "mp3": "audio/mpeg",
                "mp4": "audio/mp4",
                "mpeg": "audio/mpeg",
                "mpga": "audio/mpeg",
                "m4a": "audio/m4a",
                "wav": "audio/wav",
                "webm": "audio/webm",
                "flac": "audio/flac",
            }
            mime_type = mime_types[audio_format]
            files = {
                "file": (f"audio.{audio_format}", file_content, mime_type),
                "model": (None, model_name, "text/plain"),
            }
            # Add optional form fields with validation
            ALLOWED_RESPONSE_FORMATS = {"json", "text", "srt", "verbose_json"}
            for key in ["language", "prompt", "temperature", "response_format"]:
                if key in asr_dict and asr_dict[key] is not None:
                    # Security: validate response_format against whitelist
                    if key == "response_format" and asr_dict[key] not in ALLOWED_RESPONSE_FORMATS:
                        raise ValueError(f"Unsupported response_format: {asr_dict[key]}")
                    files[key] = (None, str(asr_dict[key]), "text/plain")
            # Remove all fields from asr_dict since they're in files now
            asr_dict.clear()

        response = await self._request(data=asr_dict if asr_dict else None, files=files)
        json_data = response.json()

        model = json_data.get("model", "whisper-1")
        text = json_data.get("text", "")

        # Handle empty response as error
        if not text:
            raise ValueError("ASR returned empty transcription")

        return ASRResponse(
            model=model,
            text=text,
            duration=json_data.get("duration"),
            language=json_data.get("language"),
        )
