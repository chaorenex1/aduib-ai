import logging
from json import JSONDecodeError
from typing import Union, Any

from runtime.entities.llm_entities import ChatCompletionRequest, CompletionRequest, ChatCompletionResponseChunk
from runtime.transformation import AnthropicTransformation

logger = logging.getLogger(__name__)


class OpenRouterTransformation(AnthropicTransformation):
    """
    Translates from openrouter API to provider-specific API.
    """

    provider_type = "openrouter"

    @classmethod
    def setup_model_parameters(cls, credentials: dict, model_params: dict[str, Any],
                               prompt_messages: Union[ChatCompletionRequest, CompletionRequest]):
        parameters = super().setup_model_parameters(credentials, model_params, prompt_messages)
        return parameters

    @classmethod
    def setup_environment(cls, credentials, params=None):
        environment = super().setup_environment(credentials, params)
        return environment

    @classmethod
    def transform_to_anthropic_format(cls, prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
                                      model_params: dict, credentials: dict,) -> dict:
        anthropic_format = super().transform_to_anthropic_format(prompt_messages, model_params, credentials)
        return anthropic_format

    @classmethod
    def transform_to_openai_format(cls, prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
                                   model_params: dict,credentials: dict) -> dict:
        from utils import jsonable_encoder
        openai_format = jsonable_encoder(prompt_messages, exclude_none=True)
        order_providers = model_params.get("order_providers",[])
        if len(order_providers) > 0:
            openai_format["provider"]={
                            'order': order_providers,
                            'allow_fallbacks': False,
                            "data_collection":"deny"}
        return openai_format

    @classmethod
    def handle_non_anthropic_response(cls, response, stream):
        if stream:
            def response_generator():
                for line in response.iter_lines():
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if line and line != "" and line != ": OPENROUTER PROCESSING":
                        if line == "[DONE]":
                            yield ChatCompletionResponseChunk(done=True)  # type: ignore
                        else:
                            # logger.debug(f"Parsing line: {line}")
                            try:
                                import json
                                chunk = json.loads(line)
                                yield ChatCompletionResponseChunk(**chunk)
                            except JSONDecodeError as e:
                                logger.debug(f"Error parsing line: {line}, error: {e}")
                                # raise e
            return response_generator()
        else:
            return ChatCompletionResponse(**response.json())  # type: ignore




