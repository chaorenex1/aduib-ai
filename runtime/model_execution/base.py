from typing import Any, Optional, Union

from pydantic import BaseModel, Field

from service.model_service import ModelService
from utils import message_uuid

from ..entities import PromptMessage
from ..entities.anthropic_entities import AnthropicMessageRequest
from ..entities.llm_entities import ChatCompletionRequest, CompletionRequest
from ..entities.model_entities import AIModelEntity
from ..entities.provider_entities import ProviderEntity
from ..entities.response_entities import ResponseRequest


class AiModel(BaseModel):
    model_type: str = Field(description="Model type")
    provider_name: str = Field(description="Provider name")
    model_provider: ProviderEntity = Field(description="Model provider")
    started_at: float = Field(description="Invoke start time", default=0)
    model_params: dict = Field(description="Model parameters", default_factory=dict)
    credentials: dict = Field(description="Model credentials", default_factory=dict)

    def get_messages(self, req: Any) -> Optional[Union[list[PromptMessage], str]]:
        """Extract messages from various request types.

        Supports:
        - ChatCompletionRequest: returns messages list
        - CompletionRequest: returns prompt
        - AnthropicMessageRequest: returns messages list
        - ResponseRequest: returns input items converted to messages
        """
        from runtime.protocol import ProtocolConverter

        if isinstance(req, ChatCompletionRequest):
            return req.messages
        elif isinstance(req, CompletionRequest):
            return req.prompt
        elif isinstance(req, AnthropicMessageRequest):
            return ProtocolConverter.anthropic_to_openai(req).messages
        elif isinstance(req, ResponseRequest):
            return ProtocolConverter.responses_to_openai(req).messages
        return None

    def get_model_schema(self, model: Optional[str] = None) -> Optional[AIModelEntity]:
        """
        Get model schema
        :param model: model name
        :return: model schema or None if not found
        :rtype: Optional[AIModelEntity]
        """
        return ModelService.get_ai_model(model)

    def get_message_id(self) -> str:
        """
        Get message id
        :return: message id
        """
        return message_uuid()

    def get_max_context_length(self, model: str) -> int:
        """
        Get max context length for the model
        :param model: model name
        :return: max context length
        """
        model_schema = self.get_model_schema(model)
        if model_schema and hasattr(model_schema, "model_properties"):
            return model_schema.model_properties.get("max_context_length", 0)
        return 0
