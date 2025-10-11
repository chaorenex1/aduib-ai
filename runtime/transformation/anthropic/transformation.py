import json
import logging
from typing import Union, Generator, Any

import httpx
from httpx import Response

from runtime.clients.handler.llm_http_handler import LLMHttpHandler
from runtime.entities.llm_entities import ChatCompletionRequest, CompletionRequest, ClaudeChatCompletionResponse, \
    CompletionResponse
from runtime.entities.rerank_entities import RerankRequest, RerankResponse
from runtime.entities.text_embedding_entities import EmbeddingRequest, TextEmbeddingResult
from runtime.transformation.base import LLMTransformation
from utils import jsonable_encoder
from .error import AnthropicErrorMapper, AnthropicAPIError
from ...entities.provider_entities import ProviderSDKType

logger = logging.getLogger(__name__)


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
            "anthropic-version": "2023-06-01"
        }

        # Get API base URL or use default
        api_base = _credentials.get("api_base", "https://api.anthropic.com/v1")

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
        }

    @classmethod
    def _transform_message(
            cls,
            model_params: dict,
            prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
            credentials: dict,
            stream: bool = None,
    ) -> Union[CompletionResponse, Generator[CompletionResponse, None, None]]:
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

        # Transform OpenAI-like request to Anthropic format
        anthropic_request={}
        if credentials["sdk_type"] == ProviderSDKType.ANTHROPIC:
            anthropic_request = cls._transform_to_anthropic_format(prompt_messages, model_params)
        else:
            anthropic_request=jsonable_encoder(obj=prompt_messages, exclude_none=True, exclude_unset=True)

        # Create HTTP handler and make request
        llm_http_handler = LLMHttpHandler("/messages", credentials, stream)
        try:
            response = llm_http_handler._request(data=anthropic_request)
        except httpx.HTTPStatusError as e:
            # Extract error details from response
            error_response = None
            try:
                error_response = e.response.json()
            except:
                pass

            # Map to Anthropic error
            mapped_error = AnthropicErrorMapper.map_error(
                status_code=e.response.status_code,
                error_response=error_response,
                default_message=str(e)
            )
            logger.warning(
                f"Anthropic API request failed: {mapped_error.__class__.__name__}: {mapped_error.message}"
            )
            # If we shouldn't retry, raise the error
            raise mapped_error

        except (httpx.RequestError, httpx.TimeoutException) as e:
            # Create a generic API error for connection issues
            last_error = AnthropicAPIError(
                message=f"Connection error: {str(e)}",
                status_code=None,
                error_type="connection_error"
            )

            logger.warning(
                f"Anthropic API connection error: {e}"
            )
            # If we shouldn't retry, raise the error
            raise last_error
        if credentials["sdk_type"] == ProviderSDKType.ANTHROPIC:
            return cls.handle_anthropic_response(response, stream)
        else:
            return cls.handle_non_anthropic_response(response, stream)

    @classmethod
    def handle_anthropic_response(cls, response: Response, stream: bool | None) -> Union[ClaudeChatCompletionResponse, Generator[ClaudeChatCompletionResponse, None, None]]:
        if stream:
            def response_generator():
                chat_id = ''
                model = ''
                role = ''
                input_tokens = 0
                output_tokens = 0
                stop_reason = ''
                stop_sequence = ''
                for line in response.iter_lines():
                    logger.debug(f"Received streaming line: {line}")
                    if len(line.strip()) == 0:
                        continue
                    if line.strip().startswith("event:"):
                        continue
                    if line.strip().startswith("data:"):
                        line = line[5:].strip()
                    if line == "[DONE]":
                        yield ClaudeChatCompletionResponse(done=True)
                    else:
                        try:
                            completion_response = ClaudeChatCompletionResponse(**json.loads(line.strip()))
                            if completion_response.type == 'message_start':
                                chat_id = completion_response.message['id']
                                model = completion_response.message['model']
                                role = completion_response.message['role']
                                input_tokens = completion_response.message['usage']['input_tokens']
                                completion_response.id = chat_id
                                completion_response.model = model
                                completion_response.role = role
                            if completion_response.type == 'message_delta':
                                output_tokens = completion_response.usage['output_tokens']
                                stop_reason = completion_response.delta[
                                    'stop_reason'] if 'stop_reason' in completion_response.delta else ''
                                stop_sequence = completion_response.delta[
                                    'stop_sequence'] if 'stop_sequence' in completion_response.delta else ''
                                completion_response.id = chat_id
                                completion_response.model = model
                                completion_response.role = role
                                completion_response.usage['input_tokens'] = input_tokens
                                completion_response.stop_reason = stop_reason
                                completion_response.stop_sequence = stop_sequence
                            elif completion_response.type == 'message_stop':
                                completion_response.id = chat_id
                                completion_response.model = model
                                completion_response.role = role
                                completion_response.usage = {'input_tokens': input_tokens,
                                                             'output_tokens': output_tokens}
                                completion_response.stop_reason = stop_reason
                                completion_response.stop_sequence = stop_sequence
                            else:
                                completion_response.id = chat_id
                                completion_response.model = model
                                completion_response.role = role
                            yield completion_response
                        except Exception as e:
                            logger.error(f"Error parsing streaming line: {line}, error: {e}")
                            continue

            return response_generator()
        else:
            # Non-streaming response
            response_json = response.json()
            return ClaudeChatCompletionResponse(**response_json)

    @classmethod
    def handle_non_anthropic_response(cls, response, stream):
        """Handle response for non-Anthropic SDK types by converting OpenAI-compatible
        responses into Anthropic-style ClaudeChatCompletionResponse models/events."""
        def map_finish_reason(fr: str | None) -> str | None:
            if fr is None:
                return None
            fr = str(fr)
            if fr == 'stop':
                return 'end_turn'
            if fr in ('length', 'max_tokens'):
                return 'max_tokens'
            # pass through others
            return fr

        if stream:
            def response_generator():
                chat_id = ''
                model = ''
                role = 'assistant'
                input_tokens = 0
                output_tokens = 0
                started = False
                content_block_started = False
                pending_stop_reason = None

                for raw in response.iter_lines():
                    line = raw.strip() if isinstance(raw, str) else raw
                    if not line:
                        continue
                    # httpx returns str; keep safe
                    if isinstance(line, bytes):
                        try:
                            line = line.decode('utf-8')
                        except Exception:
                            continue
                    if line.startswith("event:"):
                        # Ignore explicit event headers from upstream
                        continue
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if line == "[DONE]":
                        # Finalize stream with message_stop if we started
                        if started:
                            stop_event = ClaudeChatCompletionResponse(
                                type='message_stop',
                                id=chat_id,
                                model=model,
                                role=role,
                                usage={'input_tokens': input_tokens, 'output_tokens': output_tokens},
                                stop_reason=pending_stop_reason,
                                stop_sequence=None,
                            )
                            yield stop_event
                        yield ClaudeChatCompletionResponse(done=True)
                        break

                    # Try parse JSON chunk (OpenAI-style)
                    try:
                        chunk = json.loads(line)
                    except Exception as e:
                        logger.error(f"Error parsing non-anthropic streaming line: {line}, error: {e}")
                        continue

                    # Extract meta
                    chat_id = chunk.get('id') or chat_id
                    model = chunk.get('model') or model
                    choices = chunk.get('choices') or []
                    if not choices:
                        continue
                    choice0 = choices[0]
                    delta = choice0.get('delta') or {}
                    finish_reason = choice0.get('finish_reason')

                    # Attempt to pick up usage if provider includes it in stream
                    usage = chunk.get('usage') or {}
                    if isinstance(usage, dict):
                        input_tokens = usage.get('prompt_tokens', input_tokens) or input_tokens
                        output_tokens = usage.get('completion_tokens', output_tokens) or output_tokens

                    text_piece = ''
                    if isinstance(delta, dict):
                        role = delta.get('role', role) or role
                        text_piece = delta.get('content') or ''
                    else:
                        # Some providers may send {"text": "..."}
                        text_piece = choice0.get('text') or ''

                    # Send message_start once
                    if not started:
                        started = True
                        msg_start = ClaudeChatCompletionResponse(
                            type='message_start',
                            message={
                                'id': chat_id or '',
                                'type': 'message',
                                'role': role or 'assistant',
                                'model': model or '',
                                'usage': {'input_tokens': input_tokens or 0}
                            },
                        )
                        # also expose convenience fields
                        msg_start.id = chat_id or ''
                        msg_start.model = model or ''
                        msg_start.role = role or 'assistant'
                        yield msg_start

                    # Start a single text content block once before deltas
                    if not content_block_started:
                        content_block_started = True
                        cb_start = ClaudeChatCompletionResponse(
                            type='content_block_start',
                            index=0,
                            content_block={'type': 'text', 'text': ''},
                        )
                        cb_start.id = chat_id or ''
                        cb_start.model = model or ''
                        cb_start.role = role or 'assistant'
                        yield cb_start

                    # Emit text delta if present
                    if text_piece:
                        cb_delta = ClaudeChatCompletionResponse(
                            type='content_block_delta',
                            index=0,
                            delta={'type': 'text_delta', 'text': text_piece},
                        )
                        cb_delta.id = chat_id or ''
                        cb_delta.model = model or ''
                        cb_delta.role = role or 'assistant'
                        yield cb_delta

                    # If finish, close blocks and emit message_delta + message_stop
                    if finish_reason is not None:
                        # close the content block
                        cb_stop = ClaudeChatCompletionResponse(
                            type='content_block_stop',
                            index=0,
                        )
                        cb_stop.id = chat_id or ''
                        cb_stop.model = model or ''
                        cb_stop.role = role or 'assistant'
                        yield cb_stop

                        pending_stop_reason = map_finish_reason(finish_reason)

                        msg_delta = ClaudeChatCompletionResponse(
                            type='message_delta',
                            delta={'stop_reason': pending_stop_reason, 'stop_sequence': None},
                            usage={'output_tokens': output_tokens or 0},
                        )
                        msg_delta.id = chat_id or ''
                        msg_delta.model = model or ''
                        msg_delta.role = role or 'assistant'
                        yield msg_delta
                        # message_stop will be emitted when we receive [DONE] or in next iteration end
                # ensure termination if upstream doesn't send [DONE]
                if started:
                    stop_event = ClaudeChatCompletionResponse(
                        type='message_stop',
                        id=chat_id,
                        model=model,
                        role=role,
                        usage={'input_tokens': input_tokens, 'output_tokens': output_tokens},
                        stop_reason=pending_stop_reason,
                        stop_sequence=None,
                    )
                    yield stop_event
                    yield ClaudeChatCompletionResponse(done=True)

            return response_generator()
        else:
            # Non-streaming: Convert OpenAI ChatCompletionResponse to Anthropic message object
            try:
                res = response.json()
            except Exception as e:
                logger.error(f"Error parsing non-streaming response json: {e}")
                raise

            id_ = res.get('id', '')
            model = res.get('model', '')
            choices = (res.get('choices') or [])
            role = 'assistant'
            content_text = ''
            finish_reason = None
            if choices:
                ch0 = choices[0]
                finish_reason = ch0.get('finish_reason')
                # OpenAI non-streaming places message here
                msg = ch0.get('message') or {}
                role = (msg.get('role') or role)
                content_text = msg.get('content') or ch0.get('text') or ''

            usage = res.get('usage') or {}
            input_tokens = usage.get('prompt_tokens', 0) if isinstance(usage, dict) else 0
            output_tokens = usage.get('completion_tokens', 0) if isinstance(usage, dict) else 0

            anthropic_message = {
                'id': id_,
                'type': 'message',
                'role': role or 'assistant',
                'model': model,
                'content': [{
                    'type': 'text',
                    'text': content_text or ''
                }],
                'stop_reason': map_finish_reason(finish_reason),
                'stop_sequence': None,
                'usage': {
                    'input_tokens': input_tokens or 0,
                    'output_tokens': output_tokens or 0
                }
            }
            return ClaudeChatCompletionResponse(**anthropic_message)

    @classmethod
    def _transform_to_anthropic_format(cls, prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
                                       model_params: dict) -> dict:
        """
        Transform OpenAI-like request format to Anthropic format.

        Args:
            prompt_messages: OpenAI-like request
            model_params: Model parameters

        Returns:
            Dictionary in Anthropic API format
        """
        # Extract messages and transform to Anthropic format
        messages = []
        system_prompt = None

        for msg in prompt_messages.messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                messages.append(jsonable_encoder(msg, exclude_none=True))

        # Build Anthropic request
        anthropic_request: dict[str, Any] = {
            "model": prompt_messages.model,
            "messages": messages,
            "max_tokens": prompt_messages.max_tokens or prompt_messages.max_completion_tokens
        }

        # Add system prompt if present
        if system_prompt:
            anthropic_request["system"] = [{"type": "text", "text": system_prompt}]

        if hasattr(prompt_messages, 'stop_sequences') and prompt_messages.stop_sequences:
            anthropic_request["stop_sequences"] = prompt_messages.stop_sequences

        if not system_prompt and prompt_messages.system:
            anthropic_request["system"] = prompt_messages.system

        # Add optional parameters
        if prompt_messages.temperature is not None:
            anthropic_request["temperature"] = prompt_messages.temperature

        if prompt_messages.top_p is not None:
            anthropic_request["top_p"] = prompt_messages.top_p

        if prompt_messages.top_k is not None:
            anthropic_request["top_k"] = prompt_messages.top_k

        # Add streaming if requested
        if hasattr(prompt_messages, 'stream') and prompt_messages.stream:
            anthropic_request["stream"] = True

        if hasattr(prompt_messages, 'thinking') and prompt_messages.thinking:
            anthropic_request["thinking"] = prompt_messages.thinking.model_dump(exclude_none=True)

        if hasattr(prompt_messages, 'tool_choice') and prompt_messages.tool_choice:
            anthropic_request["tool_choice"] = prompt_messages.tool_choice

        if hasattr(prompt_messages, 'tools') and prompt_messages.tools:
            anthropic_request["tools"] = [tool.function.model_dump(exclude_none=True) for tool in prompt_messages.tools]

        return anthropic_request

    @classmethod
    def transform_embeddings(cls, texts: EmbeddingRequest, credentials: dict) -> TextEmbeddingResult:
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
    def transform_rerank(cls, query: RerankRequest, credentials: dict) -> RerankResponse:
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
