from typing import Union, Optional

from pydantic import BaseModel, Field

from controllers.params import ChatCompletionRequest, CompletionRequest
from service.model_service import ModelService
from ..entities import PromptMessage
from ..entities.model_entities import AIModelEntity
from ..entities.provider_entities import ProviderEntity


class AiModel(BaseModel):
    model_type: str=Field(description="Model type")
    provider_name: str=Field(description="Provider name")
    model_provider: ProviderEntity=Field(description="Model provider")
    started_at: float = Field(description="Invoke start time", default=0)


    def get_messages(self, prompt_messages) -> Union[list[PromptMessage], str]:
        messages: Union[list[PromptMessage], str]
        if isinstance(prompt_messages, ChatCompletionRequest):
            messages = prompt_messages.messages
        elif isinstance(prompt_messages, CompletionRequest):
            messages = prompt_messages.prompt
        return messages


    def get_model_schema(self,model: Optional[str] = None) -> Optional[AIModelEntity]:
        """
        Get model schema
        :param model: model name
        :return: model schema or None if not found
        :rtype: Optional[AIModelEntity]
        """
        return ModelService.get_ai_model(model)