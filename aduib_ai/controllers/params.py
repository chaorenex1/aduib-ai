from typing import Optional, Sequence, Union, Mapping, Any, List

from pydantic import BaseModel, field_validator

from runtime.entities import PromptMessage, PromptMessageRole, UserPromptMessage, \
    AssistantPromptMessage, SystemPromptMessage, ToolPromptMessage
from runtime.entities.message_entities import PromptMessageFunction


class CompletionRequest(BaseModel):
    messages: Optional[list[PromptMessage]] = None
    model: str
    tools: Optional[list[PromptMessageFunction]] = None
    stream: bool = None
    top_p: Optional[float] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stop: Optional[Union[str, Sequence[str]]] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    response_format: Optional[Union[Mapping[str, Any], str]]= None

    @field_validator("messages", mode="before")
    @classmethod
    def convert_prompt_messages(cls, v):
        if not isinstance(v, list):
            raise ValueError("prompt_messages must be a list")

        for i in range(len(v)):
            if v[i]["role"] == PromptMessageRole.USER.value:
                v[i] = UserPromptMessage(**v[i])
            elif v[i]["role"] == PromptMessageRole.ASSISTANT.value:
                v[i] = AssistantPromptMessage(**v[i])
            elif v[i]["role"] == PromptMessageRole.SYSTEM.value:
                v[i] = SystemPromptMessage(**v[i])
            elif v[i]["role"] == PromptMessageRole.TOOL.value:
                v[i] = ToolPromptMessage(**v[i])
            else:
                v[i] = PromptMessage(**v[i])

        return v


class EmbeddingRequest(BaseModel):
    prompt: str
    model: str

class EmbeddingsResponse(BaseModel):
    embedding: Optional[List[float]] = None



class CreateModelRequest(BaseModel):
    model_name: str
    provider_name: str
    model_type: str
    max_tokens: int
    input_price: float | None = 0.0
    output_price: float | None = 0.0
    model_configs: dict[str, Any]| None = {}
    model_feature: list[str] | None = []


class CreateProviderRequest(BaseModel):
    provider_name: str
    supported_model_types: list[str]
    provider_type: str
    provider_config: dict[str, Any]