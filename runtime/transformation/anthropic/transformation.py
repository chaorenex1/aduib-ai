import json
import logging
from typing import Union, Generator, Any, Optional, List, Dict

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
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                txt = item.get("text")
                if isinstance(txt, str):
                    parts.append(txt)
        return " ".join(parts) if parts else None
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

    result: Dict[str, Any] = {}
    for key, value in schema.items():
        if key == "properties" and isinstance(value, dict):
            result[key] = {k: remove_uri_format(v) for k, v in value.items()}
        elif key == "items" and isinstance(value, (dict, list)):
            result[key] = remove_uri_format(value)
        elif key == "additionalProperties" and isinstance(value, (dict, list)):
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


def _approx_tokens_from_messages(msgs: List[Dict[str, Any]]) -> int:
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
            "anthropic-version": "2023-06-01"
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
        if not credentials["none_anthropic"]:
            anthropic_request = cls._transform_to_anthropic_format(prompt_messages, model_params)
            llm_http_handler = LLMHttpHandler("/messages", credentials, stream)
        elif credentials["orig_sdk_type"] == ProviderSDKType.GITHUB_COPILOT:
            anthropic_request = cls._transform_to_openai_format(prompt_messages, model_params)
            llm_http_handler = LLMHttpHandler("/chat/completions", credentials, stream)
        else:
            anthropic_request= cls._transform_to_openai_format(prompt_messages, model_params)
            llm_http_handler = LLMHttpHandler("/v1/chat/completions", credentials, stream)

        # Create HTTP handler and make request
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
        if not credentials["none_anthropic"]:
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
                encountered_tool_call = False
                accumulated_content = ""
                accumulated_reasoning = ""
                tool_call_accumulators: Dict[int, str] = {}
                usage={}

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
                        if encountered_tool_call:
                            # Close any open tool_use blocks
                            for idx in tool_call_accumulators.keys():
                                if tool_call_accumulators[idx]:
                                    cb_stop = ClaudeChatCompletionResponse(
                                        type='content_block_stop',
                                        index=idx,
                                        id=chat_id,
                                        model=model,
                                        role=role
                                    )
                                    yield cb_stop
                        elif content_block_started:
                            # Close text content block if open
                            cb_stop = ClaudeChatCompletionResponse(
                                type='content_block_stop',
                                index=0,
                                id=chat_id,
                                model=model,
                                role=role
                            )
                            yield cb_stop
                        yield ClaudeChatCompletionResponse(
                            type='message_delta',
                            delta={'stop_reason': 'tool_use' if encountered_tool_call else 'end_turn',
                                   'stop_sequence': None},
                            usage={'output_tokens': output_tokens},
                            id=chat_id,
                            model=model,
                            role=role
                        )
                        yield ClaudeChatCompletionResponse(
                            type='message_stop',
                            id=chat_id,
                            model=model,
                            role=role,
                            usage={'input_tokens': input_tokens, 'output_tokens': output_tokens},
                            stop_reason=pending_stop_reason,
                            stop_sequence=None,
                        )
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
                    # finish_reason = choice0.get('finish_reason')

                    # Attempt to pick up usage if provider includes it in stream
                    usage = chunk.get('usage') or {}
                    if isinstance(usage, dict):
                        input_tokens = usage.get('prompt_tokens', input_tokens) or input_tokens
                        output_tokens = usage.get('completion_tokens', output_tokens) or output_tokens

                    # Send message_start once
                    if not started:
                        started = True
                        yield ClaudeChatCompletionResponse(
                            type='message_start',
                            message={
                                'id': chat_id or '',
                                'type': 'message',
                                'role': role or 'assistant',
                                'model': model or '',
                                'usage': {'input_tokens': input_tokens or 0, 'output_tokens': 0}
                            },
                            id=chat_id or '',
                            model=model or '',
                            role=role or 'assistant'
                        )
                        # also expose convenience fields
                        ping=ClaudeChatCompletionResponse(
                            type='ping',
                            id=chat_id or '',
                            model=model or '',
                            role=role or 'assistant'
                        )
                        yield ping

                    # Start a single text content block once before deltas
                    # Tool calls streaming
                    if delta.get("tool_calls"):
                        for tc in delta["tool_calls"]:
                            encountered_tool_call = True
                            idx = int(tc.get("index", 0))
                            if idx not in tool_call_accumulators:
                                tool_call_accumulators[idx] = ""

                                yield ClaudeChatCompletionResponse(
                                    type='content_block_start',
                                    index=idx,
                                    content_block={
                                        "type": "tool_use",
                                        "id": tc.get("id"),
                                        "name": ((tc.get("function") or {}).get("name")),
                                        "input": {},
                                    },
                                    id=chat_id or '',
                                    model=model or '',
                                    role=role or 'assistant'
                                )
                            new_args = ((tc.get("function") or {}).get("arguments")) or ""
                            old_args = tool_call_accumulators.get(idx, "")
                            if len(new_args) > len(old_args):
                                delta_text = new_args[len(old_args):]

                                yield ClaudeChatCompletionResponse(
                                    type='content_block_delta',
                                    index=idx,
                                    delta={
                                        "type": "input_json_delta",
                                        "partial_json": delta_text,
                                    },
                                    id=chat_id or '',
                                    model=model or '',
                                    role=role or 'assistant'
                                )
                                tool_call_accumulators[idx] = new_args

                    # Text streaming
                    elif isinstance(delta.get("content"), str):
                        if not content_block_started:
                            content_block_started = True

                            yield ClaudeChatCompletionResponse(
                                type='content_block_start',
                                index=0,
                                content_block={'type': 'text', 'text': ''},
                                id=chat_id or '',
                                model=model or '',
                                role=role or 'assistant'
                            )

                        accumulated_content += delta["content"]

                        yield ClaudeChatCompletionResponse(
                            type='content_block_delta',
                            index=0,
                            delta={'type': 'text_delta', 'text': delta["content"]},
                            id=chat_id or '',
                            model=model or '',
                            role=role or 'assistant'
                        )

                    # Reasoning/thinking streaming (if provided by upstream)
                    elif isinstance(delta.get("reasoning"), str):
                        if not content_block_started:
                            content_block_started = True

                            yield ClaudeChatCompletionResponse(
                                type='content_block_start',
                                index=0,
                                content_block={'type': 'text', 'text': ''},
                                id=chat_id or '',
                                model=model or '',
                                role=role or 'assistant'
                            )
                        accumulated_reasoning += delta["reasoning"]

                        yield ClaudeChatCompletionResponse(
                            type='content_block_delta',
                            index=0,
                            delta={'type': 'thinking_delta', 'thinking': delta["reasoning"]},
                            id=chat_id or '',
                            model=model or '',
                            role=role or 'assistant'
                        )
            return response_generator()
        else:
            # Non-streaming: Convert OpenAI ChatCompletionResponse to Anthropic message object
            try:
                data = response.json()
            except Exception as e:
                logger.error(f"Error parsing non-streaming response json: {e}")
                raise

            choice = (data.get("choices") or [{}])[0]
            openai_message = choice.get("message", {})

            stop_reason = map_stop_reason(choice.get("finish_reason"))
            tool_calls = openai_message.get("tool_calls") or []

            msg_id = data.get("id")

            content_blocks: List[Dict[str, Any]] = []
            content_text = openai_message.get("content")
            if isinstance(content_text, str):
                content_blocks.append({"text": content_text, "type": "text"})

            for tc in tool_calls:
                try:
                    args_raw = (((tc or {}).get("function") or {}).get("arguments"))
                    input_obj = json.loads(args_raw) if isinstance(args_raw, str) and args_raw else {}
                except Exception:
                    input_obj = {}
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc.get("id"),
                    "name": ((tc or {}).get("function") or {}).get("name"),
                    "input": input_obj,
                })

            usage = data.get("usage") or {}

            anthropic_response = {
                "content": content_blocks,
                "id": msg_id,
                "model": data.get("model"),
                "role": openai_message.get("role"),
                "stop_reason": stop_reason,
                "stop_sequence": None,
                "type": "message",
                "usage": {
                    "input_tokens": usage.get("prompt_tokens")
                    if usage
                    else 0,
                    "output_tokens": usage.get("completion_tokens")
                    if usage
                    else _approx_tokens_from_text(content_text or ""),
                },
            }
            return ClaudeChatCompletionResponse(**anthropic_response)

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
    def _transform_to_openai_format(cls, prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
                                       model_params: dict)-> dict:
        """
        Transform Anthropic request format to OpenAI format.
        """
        # Build messages array for the OpenAI payload.
        messages: List[Dict[str, Any]] = []
        payload = jsonable_encoder(prompt_messages, exclude_none=True)

        # System messages
        system_msgs = payload.get("system")
        if isinstance(system_msgs, list):
            sys_texts=[]
            for sys_msg in system_msgs:
                if isinstance(sys_msg, dict):
                    normalized = normalize_content(sys_msg.get("text") or sys_msg.get("content"))
                    if normalized:
                        sys_texts.append({"type": "text", "text": normalized})
                elif isinstance(sys_msg, str):
                    normalized = normalize_content(sys_msg)
                    if normalized:
                        sys_texts.append({"type": "text", "text": normalized})
            messages.append({"role": "system", "content": sys_texts})

        # User/assistant messages
        if isinstance(payload.get("messages"), list):
            for msg in payload["messages"]:
                if not isinstance(msg, dict):
                    continue

                content = msg.get("content")
                role = msg.get("role")

                # Extract tool calls from anthropic-like blocks
                tool_calls: List[Dict[str, Any]] = []
                msg_content_List = []
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "tool_result":
                            messages.append({
                                "role": "tool",
                                "content": normalize_content(item.get("content")),
                                "tool_call_id": item.get("tool_use_id"),
                            })
                        elif isinstance(item, dict) and item.get("type") == "tool_use":
                            tool_calls.append({
                                "type": "function",
                                "id": item.get("id"),
                                "function": {
                                    "name": item.get("name"),
                                    "arguments": json.dumps(item.get("input")),
                                },
                            })
                        elif isinstance(item, dict) and item.get("type") == "text":
                            msg_content_List.append({"type": "text", "text": normalize_content(item.get("text"))})
                        elif isinstance(content, str) and item.get("type") == "text":
                            msg_content_List.append({"type": "text", "text": normalize_content(item)})

                new_msg: Dict[str, Any] = {"role": role}
                if len(msg_content_List) > 0:
                    new_msg["content"] = msg_content_List

                if tool_calls:
                    new_msg["tool_calls"] = tool_calls

                messages.append(new_msg)

        # Tools mapping
        tools: List[Dict[str, Any]] = []
        for tool in payload.get("tools", []) or []:
            if isinstance(tool, dict) and tool.get("name") not in ("BatchTool",):
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.get("function").get("name"),
                        "description": tool.get("function").get("description"),
                        "parameters": remove_uri_format(tool.get("function").get("input_schema")),
                    },
                })

        openai_payload: Dict[str, Any] = {
            **payload,
            "model": prompt_messages.model,
            "messages": messages,
            "max_tokens": payload.get("max_tokens"),
            "temperature": payload.get("temperature"),
            "top_p": payload.get("top_p"),
            "top_k": payload.get("top_k"),
            "stream": payload.get("stream", False)
        }
        openai_payload.pop("system", None)
        openai_payload.pop("top_logprobs", None)
        openai_payload.pop("logit_bias", None)
        openai_payload.pop("logprobs", None)
        openai_payload.pop("n", None)
        if tools:
            openai_payload["tools"] = tools

        # Remove any Nones
        return {k: v for k, v in openai_payload.items() if v is not None}


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

